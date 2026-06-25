@echo off
:: ============================================================
::  Dry Run — shows the cost on every provider, calls nothing
:: ============================================================
title Multi-AI Dry Run (Cost Estimate)
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

if not exist "jobs" (
    python "%~dp0ai_call.py" init
)

:: Preview cost for ALL jobs across every configured provider
python "%~dp0ai_call.py" dry-run --jobs all

echo.
pause
