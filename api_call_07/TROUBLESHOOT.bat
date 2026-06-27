@echo off
:: ============================================================
::  Troubleshoot THIS folder (config, keys, queue, errors)
:: ============================================================
title Troubleshoot - %~nx0
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

:: Pass this folder's name so troubleshoot.py checks only this folder.
for %%I in ("%~dp0.") do set "FOLDERNAME=%%~nxI"
python "%~dp0..\troubleshoot.py" "%FOLDERNAME%"

echo.
pause
