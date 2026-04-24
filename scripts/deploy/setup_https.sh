#!/usr/bin/env bash
# setup_https.sh — Configure HTTPS on the Azure VM using an Azure DNS label.
#
# Does the following:
#   1. Resolves the FQDN — either from a short label via Azure CLI,
#      or uses a full FQDN directly if you already set it in the portal
#   2. Writes the FQDN into the VM's .env as DOCCANO_DOMAIN
#   3. Opens ports 80 + 443 in the Azure NSG, removes port 8000
#   4. Denies port 8000 on the VM firewall (ufw) — defence in depth
#   5. Restarts the stack — Caddy auto-provisions the Let's Encrypt certificate
#
# Prerequisites:
#   - Azure CLI installed locally (only needed if passing a short label):
#       macOS:   brew install azure-cli
#       Linux:   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
#       Windows: winget install Microsoft.AzureCLI
#   - Logged in: az login  (only needed if passing a short label)
#   - bootstrap_vm.sh has already been run
#
# Usage:
#   ./scripts/deploy/setup_https.sh <ssh-host> <dns-label-or-fqdn> [ssh-user] [resource-group] [ip-resource-name]
#
# Arguments:
#   ssh-host              Public IP of the VM
#   dns-label-or-fqdn     Either:
#                           Short label:  "hp-ner"
#                             → script calls az to set it and reads back the FQDN
#                           Full FQDN:    "hp-ner.swedencentral.cloudapp.azure.com"
#                             → DNS already set in portal, Azure CLI step is skipped
#   ssh-user              SSH username (default: azureuser)
#   resource-group        Azure resource group (default: hp-ner)
#   ip-resource-name      Azure public IP resource name (default: doccano-ip)
#
# Examples:
#   # DNS label already set in Azure portal — pass full FQDN directly:
#   ./scripts/deploy/setup_https.sh 135.116.56.22 hp-ner.swedencentral.cloudapp.azure.com
#
#   # Let the script set the label via Azure CLI:
#   ./scripts/deploy/setup_https.sh 135.116.56.22 hp-ner
#   ./scripts/deploy/setup_https.sh 135.116.56.22 hp-ner azureuser hp-ner doccano-ip

set -euo pipefail

SSH_HOST="${1:?Usage: $0 <ssh-host> <dns-label-or-fqdn> [ssh-user] [resource-group] [ip-resource-name]}"
DNS_ARG="${2:?Usage: $0 <ssh-host> <dns-label-or-fqdn> [ssh-user] [resource-group] [ip-resource-name]}"
SSH_USER="${3:-azureuser}"
RESOURCE_GROUP="${4:-hp-ner}"
IP_RESOURCE="${5:-doccano-ip}"
REMOTE_DIR="/home/${SSH_USER}/hp-ner"

echo "==> HP-NER HTTPS Setup"
echo "    VM:             ${SSH_USER}@${SSH_HOST}"
echo "    DNS arg:        ${DNS_ARG}"
echo ""

# ── 1. Resolve FQDN ──────────────────────────────────────────────────────────
if [[ "${DNS_ARG}" == *.* ]]; then
    FQDN="${DNS_ARG}"
    echo "==> [1/5] FQDN provided directly — skipping Azure CLI DNS setup."
    echo "    FQDN: ${FQDN}"
else
    echo "==> [1/5] Short label detected — setting DNS label via Azure CLI ..."

    if ! command -v az &>/dev/null; then
        echo "ERROR: Azure CLI not found. Install it:"
        echo "  macOS:   brew install azure-cli"
        echo "  Linux:   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash"
        echo "  Windows: winget install Microsoft.AzureCLI"
        exit 1
    fi

    if ! az account show &>/dev/null; then
        echo "Not logged in. Running az login ..."
        az login
    fi

    echo "    Subscription: $(az account show --query "name" -o tsv)"

    az network public-ip update \
        --resource-group "${RESOURCE_GROUP}" \
        --name "${IP_RESOURCE}" \
        --dns-name "${DNS_ARG}" \
        --output none

    FQDN=$(az network public-ip show \
        --resource-group "${RESOURCE_GROUP}" \
        --name "${IP_RESOURCE}" \
        --query "dnsSettings.fqdn" \
        -o tsv)

    echo "    FQDN: ${FQDN}"
fi

# ── 2. Update Azure NSG rules ─────────────────────────────────────────────────
echo ""
echo "==> [2/5] Updating Azure Network Security Group ..."

if ! command -v az &>/dev/null || ! az account show &>/dev/null 2>/dev/null; then
    echo "    Azure CLI not available or not logged in — skipping NSG update."
    echo "    Open ports 80 and 443 manually in the Azure portal:"
    echo "    VM → Networking → Add inbound port rule → 80 (HTTP)"
    echo "    VM → Networking → Add inbound port rule → 443 (HTTPS)"
    echo "    VM → Networking → Delete Allow-Doccano rule (port 8000)"
else
    NSG_NAME=$(az network nsg list \
        --resource-group "${RESOURCE_GROUP}" \
        --query "[0].name" -o tsv 2>/dev/null || echo "")

    if [ -z "${NSG_NAME}" ]; then
        echo "    WARNING: Could not auto-detect NSG in '${RESOURCE_GROUP}'."
        echo "    Open ports 80 and 443 manually in the Azure portal."
    else
        echo "    NSG: ${NSG_NAME}"

        az network nsg rule create \
            --resource-group "${RESOURCE_GROUP}" --nsg-name "${NSG_NAME}" \
            --name Allow-HTTP --priority 320 \
            --destination-port-ranges 80 --protocol Tcp --access Allow \
            --output none 2>/dev/null || \
        az network nsg rule update \
            --resource-group "${RESOURCE_GROUP}" --nsg-name "${NSG_NAME}" \
            --name Allow-HTTP --destination-port-ranges 80 --output none
        echo "    + Allow-HTTP  (port 80)"

        az network nsg rule create \
            --resource-group "${RESOURCE_GROUP}" --nsg-name "${NSG_NAME}" \
            --name Allow-HTTPS --priority 330 \
            --destination-port-ranges 443 --protocol Tcp --access Allow \
            --output none 2>/dev/null || \
        az network nsg rule update \
            --resource-group "${RESOURCE_GROUP}" --nsg-name "${NSG_NAME}" \
            --name Allow-HTTPS --destination-port-ranges 443 --output none
        echo "    + Allow-HTTPS (port 443)"

        az network nsg rule delete \
            --resource-group "${RESOURCE_GROUP}" --nsg-name "${NSG_NAME}" \
            --name Allow-Doccano --output none 2>/dev/null && \
            echo "    - Allow-Doccano (port 8000 removed)" || \
            echo "    - Allow-Doccano (already absent, skipping)"
    fi
fi

# ── 3. SSH into VM: write domain, harden ufw, restart stack ──────────────────
echo ""
echo "==> [3/5] Configuring VM over SSH ..."

ssh "${SSH_USER}@${SSH_HOST}" FQDN="${FQDN}" REMOTE_DIR="${REMOTE_DIR}" bash -s << 'ENDSSH'
set -euo pipefail

echo "--- Writing DOCCANO_DOMAIN to .env ---"
cd "${REMOTE_DIR}/doccano"

if grep -q "^DOCCANO_DOMAIN=" .env 2>/dev/null; then
    sed -i "s|^DOCCANO_DOMAIN=.*|DOCCANO_DOMAIN=${FQDN}|" .env
else
    echo "DOCCANO_DOMAIN=${FQDN}" >> .env
fi
echo "  DOCCANO_DOMAIN=${FQDN}"

echo ""
echo "--- Hardening firewall (ufw) ---"
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8000/tcp
sudo ufw --force enable
sudo ufw status

echo ""
echo "--- Restarting Doccano stack ---"
docker compose down
docker compose up -d

echo ""
echo "--- Waiting for Caddy to obtain TLS certificate (up to 60s) ---"
for i in $(seq 1 24); do
    CODE=$(curl -o /dev/null -s -w "%{http_code}" --max-time 5 "https://${FQDN}" 2>/dev/null || echo "000")
    if [ "${CODE}" = "200" ] || [ "${CODE}" = "302" ]; then
        echo "  HTTPS live (HTTP ${CODE})."
        break
    fi
    echo "  Attempt ${i}/24 — HTTP ${CODE}"
    sleep 5
done

docker compose ps
ENDSSH

# ── 4. Verify HTTPS from local machine ────────────────────────────────────────
echo ""
echo "==> [4/5] Verifying HTTPS from local machine ..."
CODE=$(curl -o /dev/null -s -w "%{http_code}" --max-time 10 "https://${FQDN}" 2>/dev/null || echo "000")
if [ "${CODE}" = "200" ] || [ "${CODE}" = "302" ]; then
    echo "    HTTPS reachable from local machine (HTTP ${CODE}). All good."
else
    echo "    WARNING: Got HTTP ${CODE} from local machine."
    echo "    DNS propagation may still be in progress — try again in a few minutes."
fi

echo ""
echo "==> [5/5] Done."
echo ""
echo "  Annotator URL : https://${FQDN}"
echo "  Admin scripts : SSH tunnel → http://localhost:8000"
echo ""
echo "  Share this URL with your team:"
echo "    https://${FQDN}"
echo ""
echo "  To run admin scripts via SSH tunnel:"
echo "    ssh -L 8000:localhost:8000 ${SSH_USER}@${SSH_HOST} -N &"
echo "    uv run python scripts/annotation/setup_team.py --base-url http://localhost:8000"
echo "    kill %1"