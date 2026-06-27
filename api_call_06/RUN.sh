#!/usr/bin/env bash
# ============================================================
#  Process THIS folder's inbox  (Mac / Linux)
# ============================================================
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
    echo "ERROR: python3 not found. Install Python 3.8+ first."
    exit 1
fi
"$PY" "$(pwd)/../core/worker.py" "$(pwd)"
echo ""
echo "Done. Answers are in this folder's outbox/  (failures in wait/)."
