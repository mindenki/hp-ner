#!/usr/bin/env bash
# deploy_annotation.sh — Run the full annotation setup on the VM.
#
# Data files are already on the VM (restored from git history by bootstrap_vm.sh).
# This script SSHes in and runs setup_team.py directly.
#
# Usage:
#   ./scripts/deploy/deploy_annotation.sh <ssh-host> [ssh-user] [setup_team args...]
#
# Examples:
#   ./scripts/deploy/deploy_annotation.sh 135.116.56.22
#   ./scripts/deploy/deploy_annotation.sh 135.116.56.22 azureuser --skip-users
#   ./scripts/deploy/deploy_annotation.sh 135.116.56.22 azureuser --import-scope personal --skip-users

set -euo pipefail

SSH_HOST="${1:?Usage: $0 <ssh-host> [ssh-user] [setup_team args...]}"
SSH_USER="${2:-azureuser}"
shift 2 || true

# Build the setup_team arguments — default to overlap-only on first run
if [ $# -eq 0 ]; then
    SETUP_ARGS="--import-scope overlap"
else
    SETUP_ARGS="$*"
fi

REMOTE_DIR="/home/${SSH_USER}/hp-ner"

# ── 1. Pull latest code ───────────────────────────────────────────────────────
echo "==> [1/3] Pulling latest code on VM ..."
ssh "${SSH_USER}@${SSH_HOST}" "cd ${REMOTE_DIR} && git pull origin HEAD"

# ── 2. Verify data exists on VM ───────────────────────────────────────────────
echo ""
echo "==> [2/3] Verifying data files on VM ..."
COUNT=$(ssh "${SSH_USER}@${SSH_HOST}" "find ${REMOTE_DIR}/data/selected/gold -name '*.jsonl' 2>/dev/null | wc -l")
echo "    Found ${COUNT} JSONL files."
if [ "${COUNT}" -eq 0 ]; then
    echo "ERROR: No data files on VM. Re-run bootstrap_vm.sh first."
    exit 1
fi

# ── 3. Run setup_team.py ──────────────────────────────────────────────────────
echo ""
echo "==> [3/3] Running setup_team.py on VM ..."
echo "    Args: ${SETUP_ARGS}"

ssh "${SSH_USER}@${SSH_HOST}" \
    "export PATH=\$HOME/.local/bin:\$PATH && \
     cd ${REMOTE_DIR} && \
     uv run python scripts/annotation/setup_team.py \
         --base-url http://localhost:8000 \
         --local \
         --data-dir data/selected/gold \
         ${SETUP_ARGS}"

echo ""
echo "==> Done. Annotators can log in at: https://${SSH_HOST}"