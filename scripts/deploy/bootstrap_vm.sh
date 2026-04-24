#!/usr/bin/env bash
# bootstrap_vm.sh — One-time VM setup via SSH.
#
# Installs Docker, clones the repo, restores data files, configures Doccano
# with Caddy HTTPS reverse proxy, and starts the stack.
#
# The domain is read from doccano/.env.example (DOCCANO_DOMAIN).
# Set it there before running this script, or pass it as an argument.
#
# Prerequisites:
#   - Azure NSG has ports 22, 80, 443 open
#   - DOCCANO_DOMAIN is set in doccano/.env.example
#
# Usage:
#   ./scripts/deploy/bootstrap_vm.sh <ssh-host> [ssh-user]
#
# Examples:
#   ./scripts/deploy/bootstrap_vm.sh 135.116.56.22
#   ./scripts/deploy/bootstrap_vm.sh 135.116.56.22 azureuser

set -euo pipefail

SSH_HOST="${1:?Usage: $0 <ssh-host> [ssh-user]}"
SSH_USER="${2:-azureuser}"
REPO_URL="https://github.com/mindenki/hp-ner.git"
BRANCH="phase2-peter"
DATA_COMMIT="cce3b08"
REMOTE_DIR="/home/${SSH_USER}/hp-ner"

echo "==> Bootstrapping ${SSH_USER}@${SSH_HOST} ..."
echo ""

ssh "${SSH_USER}@${SSH_HOST}" bash -s << ENDSSH
set -euo pipefail

echo "--- Installing Docker ---"
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker \$USER
    newgrp docker || true
else
    echo "Docker already installed, skipping."
fi
sudo apt-get install -y docker-compose-plugin 2>/dev/null || true

echo "--- Cloning repo ---"
if [ -d "${REMOTE_DIR}" ]; then
    echo "Repo already exists, pulling latest."
    cd "${REMOTE_DIR}"
    git fetch origin
    git checkout ${BRANCH}
    git pull origin ${BRANCH}
else
    git clone --branch ${BRANCH} ${REPO_URL} "${REMOTE_DIR}"
fi
cd "${REMOTE_DIR}"

echo "--- Restoring data files from phase1 snapshot (commit ${DATA_COMMIT}) ---"
git fetch origin integration/phase1
git checkout ${DATA_COMMIT} -- \
    data/selected/gold/ \
    data/silver/ \
    data/clean/ \
    data/raw/ || echo "Some data paths not found in commit, continuing."
echo "Restored JSONL files:"
find data/ -name "*.jsonl" 2>/dev/null | sort || echo "(none found)"

echo "--- Configuring Doccano .env ---"
cd "${REMOTE_DIR}/doccano"
if [ ! -f .env ]; then
    cp .env.example .env
fi

# Verify DOCCANO_DOMAIN is set
DOMAIN=\$(grep "^DOCCANO_DOMAIN=" .env | cut -d= -f2 || echo "")
if [ -z "\$DOMAIN" ] || [ "\$DOMAIN" = "YOUR_DOMAIN_HERE" ]; then
    echo ""
    echo "ERROR: DOCCANO_DOMAIN is not set in doccano/.env"
    echo "Set it to your Azure DNS FQDN, e.g.:"
    echo "  DOCCANO_DOMAIN=hp-ner-doccano.swedencentral.cloudapp.azure.com"
    echo "Then re-run this script."
    exit 1
fi
echo "  DOCCANO_DOMAIN=\$DOMAIN"

echo "--- Starting Doccano + Caddy ---"
docker compose down 2>/dev/null || true
docker compose up -d

echo "--- Waiting for Doccano to be ready ---"
for i in \$(seq 1 30); do
    if curl -sf http://localhost:8000 -o /dev/null 2>/dev/null; then
        echo "Doccano is up."
        break
    fi
    echo "  Waiting... (\$i/30)"
    sleep 5
done

echo "--- Installing uv + Python deps ---"
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="\$HOME/.local/bin:\$PATH"
fi
cd "${REMOTE_DIR}"
uv sync

echo ""
echo "Bootstrap complete."
echo "  HTTPS (annotators): https://\$DOMAIN"
echo "  SSH tunnel (admin): ssh -L 8000:localhost:8000 ${SSH_USER}@${SSH_HOST}"
echo "  Then open:          http://localhost:8000"
ENDSSH

echo ""
echo "==> VM bootstrap done."
echo ""
echo "Next steps:"
echo "  1. Run setup_https.sh to open NSG ports + harden firewall:"
echo "     ./scripts/deploy/setup_https.sh ${SSH_HOST} <fqdn>"
echo "  2. Run: ./scripts/deploy/deploy_annotation.sh ${SSH_HOST} ${SSH_USER}"
echo "  3. Set up daily sync: ./scripts/deploy/sync_annotations.sh --setup-cron ${SSH_HOST} ${SSH_USER}"