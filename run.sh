#!/usr/bin/env bash
# ============================================================
#  OpenAI Direct-Call  —  Run this on Mac / Linux
# ============================================================
set -e
cd "$(dirname "$0")"

echo ""
echo "============================================================"
echo "  OpenAI Direct-Call"
echo "============================================================"
echo ""
echo "  1.  Edit config.txt   — paste your API key"
echo "  2.  Edit prompt.txt   — write what you want"
echo "  3.  Drop files into   input/   (optional)"
echo "  4.  Run this script!"
echo ""
echo "============================================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.8+ first."
    exit 1
fi

# Install openai if missing
if ! python3 -c "import openai" 2>/dev/null; then
    echo "Installing OpenAI Python package ..."
    pip3 install openai
    echo ""
fi

# Run
python3 call_openai.py

echo ""
echo "============================================================"
echo "  Done!  Check the output/ folder for saved responses."
echo "============================================================"
