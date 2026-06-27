#!/usr/bin/env bash
# ============================================================
#  NEW FOLDER  --  scaffold the next api_call_NN station(s) (Mac/Linux)
#    ./NEW_FOLDER.sh        make the next one (11, then 12, ...)
#    ./NEW_FOLDER.sh 5      make the next five at once
# ============================================================
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
    echo "ERROR: python3 not found."
    exit 1
fi
"$PY" "$(pwd)/new_folder.py" "$@"
