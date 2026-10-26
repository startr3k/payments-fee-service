#!/usr/bin/env bash
# runbook/execute-rollback.sh — RB-4371-R1: execute the APPROVED recovery action
#
# Precondition: the change advisory approval for INC-4371 has been granted and
# recorded on the incident ticket. This script performs exactly one approved
# change: rollback of build #4177 via the Jenkins rollback job. It never
# decides whether to act; the caller (an approved workflow) decides.
set -euo pipefail
curl -s -X POST http://localhost:8085/api/jobs/rollback-4177/run
echo
