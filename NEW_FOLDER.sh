#!/usr/bin/env bash
# ============================================================
#  NEW FOLDER  --  scaffold another api_call_NN station (Mac/Linux)
# ============================================================
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
    echo "ERROR: python3 not found."
    exit 1
fi
"$PY" "$(pwd)/new_folder.py" "$@"
