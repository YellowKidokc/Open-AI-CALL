@echo off
:: ============================================================
::  DRY RUN ALL  --  estimate the cost, make NO API calls
:: ============================================================
::  Shows, for every folder, how many calls would run and an
::  estimated price -- then a grand total. Spends nothing.
:: ============================================================
title Dry Run (Price Estimate) - Multi-API Batch Processor
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

python "%~dp0run_all.py" --dry-run %*

echo.
pause
