@echo off
:: ============================================================
::  TROUBLESHOOT ALL  --  health-check every folder + keys
:: ============================================================
title Troubleshoot ALL - Multi-API Batch Processor
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

python "%~dp0troubleshoot.py"

echo.
pause
