#!/usr/bin/env bash
# ============================================================
#  INSTALL  --  one-time setup: install the Python packages
# ============================================================
cd "$(dirname "$0")"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
    echo "ERROR: python3 not found. Install Python 3.8+ first."
    exit 1
fi
echo "Installing required packages (openai, anthropic, openpyxl) ..."
"$PY" -m pip install -r "$(pwd)/requirements.txt"
echo ""
echo "Done. Next: copy keys.example.txt -> keys.txt, then ./TROUBLESHOOT_ALL.sh"
