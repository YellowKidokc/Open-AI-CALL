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

:: Default to 4 calls at a time. Override by passing your own, e.g.:
::   RUN_ALL.bat --workers 8
::   RUN_ALL.bat --max-cost 5.00 --workers 6
python "%~dp0run_all.py" --workers 4 %*

echo.
echo ============================================================
echo   All folders processed. Check each folder's outbox\.
echo ============================================================
pause
