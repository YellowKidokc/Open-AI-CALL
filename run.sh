#!/usr/bin/env bash
# ============================================================
#  Multi-AI Call System  —  run this on Mac / Linux
# ============================================================
set -e
cd "$(dirname "$0")"

echo ""
echo "============================================================"
echo "  MULTI-AI CALL SYSTEM"
echo "============================================================"
echo ""
echo "  1.  Edit config.txt        paste the API keys you have"
echo "  2.  Edit jobs/API_CALL_01/prompt/prompt.txt"
echo "  3.  Drop files into         jobs/API_CALL_01/inbox/"
echo "  4.  This launcher walks you through the rest"
echo ""
echo "============================================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.8+ first."
    exit 1
fi

# Install the SDKs we need if missing
if ! python3 -c "import openai" 2>/dev/null; then
    echo "Installing the OpenAI Python package ..."
    pip3 install openai
fi
if ! python3 -c "import anthropic" 2>/dev/null; then
    echo "Installing the Anthropic Python package ..."
    pip3 install anthropic
fi

# First run? Create the job folders.
if [ ! -d "jobs" ]; then
    python3 ai_call.py init
fi

# Launch the interactive menu (dry run -> confirm -> real run)
python3 ai_call.py menu

echo ""
echo "============================================================"
echo "  Done!  Answers are in the  output/  folder"
echo "  and in each job's  outbox/  folder."
echo "============================================================"
