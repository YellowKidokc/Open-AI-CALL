@echo off
:: ============================================================
::  RUN ALL  --  process every folder's inbox in one go
:: ============================================================
title RUN ALL - Multi-API Batch Processor
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download it from https://www.python.org/downloads/
    pause
    exit /b 1
)

python "%~dp0run_all.py" %*

echo.
echo ============================================================
echo   All folders processed. Check each folder's outbox\.
echo ============================================================
pause
