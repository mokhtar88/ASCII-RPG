@echo off
REM Inkbound Realms - one-click updater.
REM Run this (double-click) after new updates land here, and it mirrors the
REM game code to your play copy, WITHOUT touching your worlds or books.
REM Your stuff that is never overwritten/deleted: saves/, books/,
REM config.json, run.log, legacy world.json.

set "TARGET=E:\ascii_rpg"
set "SRC=%~dp0"
REM trailing backslash breaks robocopy dest parsing when quoted - strip it
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"

if not exist "%TARGET%" (
    echo [*] Creating play folder at %TARGET%
    mkdir "%TARGET%" 2>nul
    if errorlevel 1 (
        echo [!] Cannot create %TARGET%. Edit TARGET= at the top of this file.
        pause
        exit /b 1
    )
)

REM cheap insurance: back up your worlds before touching anything
if exist "%TARGET%\saves" (
    echo [*] Backing up your saves...
    robocopy "%TARGET%\saves" "%TARGET%_saves_backup" /E /NFL /NDL /NJH /NJS >nul
)

echo [*] Syncing game code to %TARGET% ...
robocopy "%SRC%" "%TARGET%" /E ^
    /XD saves books __pycache__ .git ^
    /XF update.bat config.json run.log world.json *.log *.pyc
if errorlevel 8 (
    echo [!] Sync hit errors, robocopy code is %errorlevel%. Nothing was deleted.
    pause
    exit /b 1
)

echo(
echo [OK] Updated. Your saves, books and settings were left alone.
echo      Play copy: %TARGET%\run.bat
pause
