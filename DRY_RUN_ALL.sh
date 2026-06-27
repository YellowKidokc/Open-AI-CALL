#!/usr/bin/env bash
# ============================================================
#  DRY RUN ALL  --  estimate the cost, make NO API calls
# ============================================================
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
    echo "ERROR: python3 not found."
    exit 1
fi
"$PY" "$(pwd)/run_all.py" --dry-run "$@"
