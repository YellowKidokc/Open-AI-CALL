@echo off
:: ============================================================
::  Process THIS folder's inbox  --  double-click to run
:: ============================================================
title API Call - %~nx0
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download it from https://www.python.org/downloads/
    pause
    exit /b 1
)

python "%~dp0..\core\worker.py" "%~dp0"

echo.
echo ============================================================
echo   Done. Answers are in this folder's  outbox\
echo   Any failures are in  wait\  (with a .error.txt).
echo ============================================================
pause
