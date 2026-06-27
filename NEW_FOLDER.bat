@echo off
:: ============================================================
::  NEW FOLDER  --  scaffold another api_call_NN station
:: ============================================================
::  Examples:
::    NEW_FOLDER.bat
::    NEW_FOLDER.bat --provider anthropic
::    NEW_FOLDER.bat --provider deepseek --model deepseek-reasoner
:: ============================================================
title New Folder - Multi-API Batch Processor
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

python "%~dp0new_folder.py" %*

echo.
pause
