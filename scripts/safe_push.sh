#!/bin/sh
# Push main and a sprint tag only if the full leak gate passes. Usage: sh scripts/safe_push.sh sprint-N "message"
set -e
python scripts/leak_check.py            # non-zero exit (FAIL or crash) stops here because of set -e
git push origin main
if [ -n "$1" ]; then
  git tag -a "$1" -m "${2:-$1}"
  git push origin "$1"
fi
