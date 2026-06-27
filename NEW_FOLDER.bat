@echo off
:: ============================================================
::  NEW FOLDER  --  scaffold another api_call_NN station
:: ============================================================
::  Always continues in order from the highest existing folder.
::  Examples:
::    NEW_FOLDER.bat                 (make the next one: 11, then 12, ...)
::    NEW_FOLDER.bat 5               (make the next FIVE at once)
::    NEW_FOLDER.bat --provider anthropic
::    NEW_FOLDER.bat 3 --provider deepseek
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
