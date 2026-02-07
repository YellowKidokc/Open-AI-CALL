@echo off
:: ============================================================
::  Dry Run — shows cost estimate without calling the API
:: ============================================================
title OpenAI Dry Run (Cost Estimate)
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

python "%~dp0call_openai.py" --dry-run

echo.
pause
