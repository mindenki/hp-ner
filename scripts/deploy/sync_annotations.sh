#!/usr/bin/env bash
# sync_annotations.sh — Pull annotation progress from VM to local machine.
#
# Designed to be run periodically (e.g. every 24h via cron) so you always
# have a local snapshot of the team's annotation progress without manual steps.
#
# Does the following:
#   1. SSHes into the VM and runs export_annotations.py (writes JSONL to VM)
#   2. Rsyncs data/annotated/ from VM to local machine
#   3. Logs a summary (sentence counts per annotator) to logs/sync.log
#
# Usage:
#   # One-time manual run:
#   ./scripts/deploy/sync_annotations.sh <ssh-host> [ssh-user]
#
#   # Set up automatic 24h cron job:
#   ./scripts/deploy/sync_annotations.sh --setup-cron <ssh-host> [ssh-user]
#
# Examples:
#   ./scripts/deploy/sync_annotations.sh 20.123.45.67
#   ./scripts/deploy/sync_annotations.sh --setup-cron 20.123.45.67 azureuser

set -euo pipefail

# ── Argument parsing ───────────────────────────────────────────────────────────
SETUP_CRON=false
if [ "${1:-}" = "--setup-cron" ]; then
    SETUP_CRON=true
    shift
fi

SSH_HOST="${1:?Usage: $0 [--setup-cron] <ssh-host> [ssh-user]}"
SSH_USER="${2:-azureuser}"

REMOTE_DIR="/home/${SSH_USER}/hp-ner"
LOCAL_OUTPUT_DIR="data/annotated"
LOG_DIR="logs"
LOG_FILE="${LOG_DIR}/sync.log"
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# ── Cron setup mode ───────────────────────────────────────────────────────────
if [ "${SETUP_CRON}" = true ]; then
    echo "==> Setting up daily sync cron job ..."
    echo "    Script: ${SCRIPT_PATH}"
    echo "    Runs:   every day at 09:00"
    echo ""

    CRON_CMD="0 9 * * * cd ${REPO_ROOT} && ${SCRIPT_PATH} ${SSH_HOST} ${SSH_USER} >> ${REPO_ROOT}/${LOG_FILE} 2>&1"

    # Check if already in crontab
    if crontab -l 2>/dev/null | grep -qF "${SCRIPT_PATH}"; then
        echo "  Cron job already exists. Replacing ..."
        crontab -l 2>/dev/null | grep -vF "${SCRIPT_PATH}" | crontab -
    fi

    # Add new cron entry
    ( crontab -l 2>/dev/null; echo "${CRON_CMD}" ) | crontab -

    echo "  Cron job added:"
    echo "  ${CRON_CMD}"
    echo ""
    echo "  To verify: crontab -l"
    echo "  To remove: crontab -l | grep -v '${SCRIPT_PATH}' | crontab -"
    echo ""
    echo "  Logs will be written to: ${REPO_ROOT}/${LOG_FILE}"
    exit 0
fi

# ── Sync run ───────────────────────────────────────────────────────────────────
mkdir -p "${LOCAL_OUTPUT_DIR}" "${LOG_DIR}"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo ""
echo "════════════════════════════════════════════"
echo "  Annotation sync — ${TIMESTAMP}"
echo "  VM: ${SSH_USER}@${SSH_HOST}"
echo "════════════════════════════════════════════"

# Step 1: Export on VM
echo ""
echo "==> [1/3] Running export on VM ..."
ssh "${SSH_USER}@${SSH_HOST}" bash -s << REMOTE
set -euo pipefail
export PATH="\$HOME/.local/bin:\$PATH"
cd ${REMOTE_DIR}
uv run python scripts/annotation/export_annotations.py \
    --base-url http://localhost:8000 \
    --output-dir data/annotated \
    --export-scope both
REMOTE

# Step 2: Rsync annotated files to local
echo ""
echo "==> [2/3] Pulling annotations to local machine ..."
rsync -az --delete --progress \
    "${SSH_USER}@${SSH_HOST}:${REMOTE_DIR}/data/annotated/" \
    "${LOCAL_OUTPUT_DIR}/"

# Step 3: Print summary
echo ""
echo "==> [3/3] Annotation summary:"
echo ""

TOTAL_OVERLAP=0
TOTAL_PERSONAL=0

for f in "${LOCAL_OUTPUT_DIR}"/*_personal.jsonl; do
    [ -f "$f" ] || continue
    COUNT=$(wc -l < "$f" | tr -d ' ')
    NAME=$(basename "$f" | sed 's/_personal\.jsonl//' | sed 's/hp-ner_gold_-_//' | sed 's/_-.*//')
    printf "    %-30s %4d sentences (personal)\n" "${NAME}" "${COUNT}"
    TOTAL_PERSONAL=$((TOTAL_PERSONAL + COUNT))
done

echo ""
for f in "${LOCAL_OUTPUT_DIR}"/*_overlap.jsonl; do
    [ -f "$f" ] || continue
    COUNT=$(wc -l < "$f" | tr -d ' ')
    NAME=$(basename "$f" | sed 's/_overlap\.jsonl//' | sed 's/hp-ner_gold_-_//' | sed 's/_-.*//')
    printf "    %-30s %4d sentences (overlap)\n" "${NAME}" "${COUNT}"
    TOTAL_OVERLAP=$((TOTAL_OVERLAP + COUNT))
done

echo ""
echo "    ─────────────────────────────────────────"
echo "    Personal annotations total : ${TOTAL_PERSONAL}"
echo "    Overlap annotations total  : ${TOTAL_OVERLAP}"
echo ""
echo "    Files in ${LOCAL_OUTPUT_DIR}/:"
ls -lh "${LOCAL_OUTPUT_DIR}/"
echo ""
echo "  Sync complete: ${TIMESTAMP}"
