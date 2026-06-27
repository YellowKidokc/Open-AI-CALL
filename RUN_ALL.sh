#!/usr/bin/env bash
# ============================================================
#  RUN ALL  --  process every folder's inbox (Mac / Linux)
# ============================================================
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
    echo "ERROR: python3 not found. Install Python 3.8+ first."
    exit 1
fi
# Default to 4 calls at a time. Override, e.g.:  ./RUN_ALL.sh --workers 8
"$PY" "$(pwd)/run_all.py" --workers 4 "$@"
