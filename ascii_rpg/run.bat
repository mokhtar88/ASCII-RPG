@echo off
REM Inkbound Realms - double-click to play. Installs what's missing, then launches.
REM If anything goes wrong, the window stays open and the error is saved to run.log.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if not errorlevel 1 set "PY=py -3"
)
%PY% --version >run.log 2>&1
if errorlevel 1 (
    echo [!] Python 3.10+ not found. Install it from https://www.python.org/downloads/
    echo     Tick "Add python.exe to PATH" during install, then double-click this again.
    echo     Details saved to run.log
    pause
    exit /b 1
)
%PY% -c "import pygame, pypdf, numpy" >>run.log 2>&1
if errorlevel 1 (
    echo [*] First run: installing game libraries, this needs internet...
    %PY% -m pip install -r requirements.txt >>run.log 2>&1
    if errorlevel 1 (
        echo [!] Install failed. Details in run.log. Try in a terminal:
        echo     %PY% -m pip install --user -r requirements.txt
        pause
        exit /b 1
    )
)
echo [*] Starting Inkbound Realms...
%PY% main.py >>run.log 2>&1
if errorlevel 1 (
    echo [!] The game crashed. Details in run.log - send its last lines for help.
    pause
    exit /b 1
)
