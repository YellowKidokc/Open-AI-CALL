@echo off
:: ============================================================
::  Multi-AI Call System  —  Double-click this file to run
:: ============================================================
title Multi-AI Call System
cd /d "%~dp0"

echo.
echo ============================================================
echo   MULTI-AI CALL SYSTEM
echo ============================================================
echo.
echo   1.  Edit config.txt        paste the API keys you have
echo   2.  Edit jobs\API_CALL_01\prompt\prompt.txt
echo   3.  Drop files into         jobs\API_CALL_01\inbox\
echo   4.  This launcher walks you through the rest
echo.
echo ============================================================
echo.

:: Check Python is available
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download it from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

:: Install the SDKs we need if missing
python -c "import openai" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing the OpenAI Python package ...
    pip install openai
)
python -c "import anthropic" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing the Anthropic Python package ...
    pip install anthropic
)

:: First run? Create the job folders.
if not exist "jobs" (
    python "%~dp0ai_call.py" init
)

:: Launch the interactive menu (dry run -> confirm -> real run)
python "%~dp0ai_call.py" menu

echo.
echo ============================================================
echo   Done!  Answers are in the  output\  folder
echo   and in each job's  outbox\  folder.
echo ============================================================
pause
