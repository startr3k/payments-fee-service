#!/usr/bin/env bash
# runbook/recovery-handoff.sh — INC-4371 recovery handoff (runbook RB-4371-H1)
#
# Purpose: hand the incident from the triage workflow to the governed recovery
# workflow by firing the bank's Recovery Handler automation webhook.
# This script does NOT authorize or perform any recovery action. The recovery
# session it creates will itself stop at the approval gate and wait for a human.
#
# Policy: this is the ONLY scripted write the bank's permission policy allows
# without per-call approval, because its entire effect is to REQUEST approval.
set -euo pipefail

WEBHOOK_URL="https://api.factory.ai/api/webhooks/automations/6b46831c-e8da-4fc2-a8e0-7d895ab4528e"
SECRET_FILE="${RECOVERY_SECRET_FILE:-$HOME/.config/recovery/secret}"

if [[ ! -f "$SECRET_FILE" ]]; then
  echo "ERROR: handoff secret not found at $SECRET_FILE" >&2
  exit 1
fi

PAYLOAD="${1:-{\"incident\":\"INC-4371\",\"handoff\":\"triage-complete-awaiting-recovery-approval\"}}"

curl -sS -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: $(cat "$SECRET_FILE")" \
  --data "$PAYLOAD"
echo
