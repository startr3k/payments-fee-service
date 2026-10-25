#!/usr/bin/env bash
# Initialize the payments-fee-service git repo with baseline + BAD commit (a1b9c2f story).
set -euo pipefail
cd "$(dirname "$0")"
git init -q 2>/dev/null || true
git add -A
git -c user.email=dev@ocbc.example -c user.name="OCBC Dev" commit -qm "v2.13.9: fee lookup via indexed equality path" || true
git tag v2.13.9 2>/dev/null || true
# BAD commit: the deploy that caused PAY-4377/4371
python3 - <<'EOF'
import re, pathlib
p = pathlib.Path("fee_service.py"); s = p.read_text()
s = s.replace('return os.environ.get("FEE_LIKE_ROLLOUT", "off") == "on"',
              'return os.environ.get("FEE_LIKE_ROLLOUT", "on") == "on"')
p.write_text(s)
EOF
git add fee_service.py
git -c user.email=dev@ocbc.example -c user.name="OCBC Dev" commit -qm "v2.14.0: roll out LIKE-based rule lookup for flexible rule keys (build 4177)" || true
git log --oneline
