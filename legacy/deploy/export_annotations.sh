#!/usr/bin/env bash
# export_annotations.sh — Run export on the VM and pull results to local machine.
#
# Does the following over SSH:
#   1. Runs export_annotations.py on the VM (writes JSONL to data/annotated/ on VM)
#   2. Rsyncs data/annotated/ back to your local machine
#
# Usage:
#   ./scripts/deploy/export_annotations.sh <ssh-host> [ssh-user]
#
# Examples:
#   ./scripts/deploy/export_annotations.sh 20.123.45.67
#   ./scripts/deploy/export_annotations.sh 20.123.45.67 azureuser

set -euo pipefail

SSH_HOST="${1:?Usage: $0 <ssh-host> [ssh-user]}"
SSH_USER="${2:-azureuser}"

REMOTE_DIR="/home/${SSH_USER}/hp-ner"
LOCAL_OUTPUT_DIR="data/annotated"

# ── 1. Run export on VM ────────────────────────────────────────────────────────
echo "==> Running export_annotations.py on VM ..."
ssh "${SSH_USER}@${SSH_HOST}" bash -s << EOF
set -euo pipefail
export PATH="\$HOME/.local/bin:\$PATH"
cd ${REMOTE_DIR}

uv run python scripts/annotation/export_annotations.py \
    --base-url http://localhost:8000 \
    --output-dir data/annotated
EOF

# ── 2. Pull annotated files back to local machine ─────────────────────────────
echo ""
echo "==> Pulling annotations from VM to ${LOCAL_OUTPUT_DIR}/ ..."
mkdir -p "${LOCAL_OUTPUT_DIR}"
rsync -avz --progress \
    "${SSH_USER}@${SSH_HOST}:${REMOTE_DIR}/data/annotated/" \
    "${LOCAL_OUTPUT_DIR}/"

echo ""
echo "==> Export complete."
echo "    Files written to ${LOCAL_OUTPUT_DIR}/"
echo ""
echo "Next steps:"
echo "  uv run python scripts/postprocess/compute_iaa.py"
echo "  uv run python scripts/postprocess/merge_annotations.py"
echo "  uv run python scripts/postprocess/prepare_bert_split.py"
