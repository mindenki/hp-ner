#!/usr/bin/env bash
# deploy_annotation.sh — Sync data to VM and run the full annotation setup remotely.
#
# Does the following over SSH:
#   1. Rsyncs local data/selected/gold/ → VM
#   2. Runs setup_team.py on the VM (user creation + project setup + data import)
#
# Run this after bootstrap_vm.sh and after generating your JSONL batch files locally.
#
# Usage:
#   ./scripts/deploy/deploy_annotation.sh <ssh-host> [ssh-user] [options]
#
# Examples:
#   ./scripts/deploy/deploy_annotation.sh 20.123.45.67
#   ./scripts/deploy/deploy_annotation.sh 20.123.45.67 azureuser
#   ./scripts/deploy/deploy_annotation.sh 20.123.45.67 azureuser --skip-users
#   ./scripts/deploy/deploy_annotation.sh 20.123.45.67 azureuser --skip-import

set -euo pipefail

SSH_HOST="${1:?Usage: $0 <ssh-host> [ssh-user] [-- setup_team args...]}"
SSH_USER="${2:-azureuser}"
# Pass any remaining args to setup_team.py (e.g. --skip-users, --skip-import)
shift 2 || true
EXTRA_ARGS="${*:-}"

REMOTE_DIR="/home/${SSH_USER}/hp-ner"
LOCAL_DATA_DIR="data/selected/gold"
REMOTE_DATA_DIR="${REMOTE_DIR}/data/selected/gold"

# ── 1. Verify local data exists ────────────────────────────────────────────────
echo "==> Checking local data in ${LOCAL_DATA_DIR}/ ..."
if [ ! -d "${LOCAL_DATA_DIR}" ]; then
    echo "ERROR: ${LOCAL_DATA_DIR}/ not found."
    echo "Run the data preparation pipeline first:"
    echo "  uv run python scripts/annotation/prepare_annotation_data.py"
    exit 1
fi

JSONL_COUNT=$(find "${LOCAL_DATA_DIR}" -name "*.jsonl" | wc -l)
echo "    Found ${JSONL_COUNT} JSONL files."
if [ "${JSONL_COUNT}" -eq 0 ]; then
    echo "ERROR: No JSONL files found in ${LOCAL_DATA_DIR}/."
    exit 1
fi

# ── 2. Rsync data to VM ────────────────────────────────────────────────────────
echo ""
echo "==> Syncing data to ${SSH_USER}@${SSH_HOST}:${REMOTE_DATA_DIR}/ ..."
ssh "${SSH_USER}@${SSH_HOST}" "mkdir -p ${REMOTE_DATA_DIR}"
rsync -avz --progress \
    "${LOCAL_DATA_DIR}/" \
    "${SSH_USER}@${SSH_HOST}:${REMOTE_DATA_DIR}/"
echo "    Sync complete."

# ── 3. Pull latest code on VM ─────────────────────────────────────────────────
echo ""
echo "==> Pulling latest code on VM ..."
ssh "${SSH_USER}@${SSH_HOST}" "cd ${REMOTE_DIR} && git pull origin HEAD"

# ── 4. Run setup_team.py on the VM ────────────────────────────────────────────
echo ""
echo "==> Running setup_team.py on VM (--local mode, talks to localhost:8000) ..."
ssh "${SSH_USER}@${SSH_HOST}" bash -s << EOF
set -euo pipefail
export PATH="\$HOME/.local/bin:\$PATH"
cd ${REMOTE_DIR}

uv run python scripts/annotation/setup_team.py \
    --base-url http://localhost:8000 \
    --local \
    --data-dir data/selected/gold \
    ${EXTRA_ARGS}
EOF

echo ""
echo "==> Annotation setup complete."
echo "    Doccano is live at: http://${SSH_HOST}:8000"
echo "    Share this URL with your team."
