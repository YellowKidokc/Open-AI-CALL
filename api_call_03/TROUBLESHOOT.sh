#!/usr/bin/env bash
# ============================================================
#  Troubleshoot THIS folder (Mac / Linux)
# ============================================================
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
    echo "ERROR: python3 not found."
    exit 1
fi
"$PY" "$(pwd)/../troubleshoot.py" "$(basename "$(pwd)")"
