@echo off
:: ============================================================
::  INSTALL  --  one-time setup: install the Python packages
:: ============================================================
title Install - Multi-API Batch Processor
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download it from https://www.python.org/downloads/
    echo Be sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo Installing required packages (openai, anthropic, openpyxl) ...
python -m pip install -r "%~dp0requirements.txt"

echo.
echo ============================================================
echo   Done. Next:
echo     1. Copy keys.example.txt to keys.txt and paste your keys
echo     2. Run TROUBLESHOOT_ALL.bat to check everything
echo     3. Drop files into the api_call_* inboxes and RUN_ALL.bat
echo ============================================================
pause
