@echo off
:: ============================================================
::  OpenAI Direct-Call  —  Double-click this file to run
:: ============================================================
title OpenAI Direct-Call
cd /d "%~dp0"

echo.
echo ============================================================
echo   OpenAI Direct-Call
echo ============================================================
echo.
echo   1.  Edit config.txt   — paste your API key
echo   2.  Edit prompt.txt   — write what you want
echo   3.  Drop files into   input\   (optional)
echo   4.  Run this script!
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

:: Install openai package if missing
python -c "import openai" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing OpenAI Python package ...
    pip install openai
    echo.
)

:: Run the script
python "%~dp0call_openai.py"

echo.
echo ============================================================
echo   Done!  Check the output\ folder for saved responses.
echo ============================================================
pause
