@echo off
setlocal
rem SETLOCAL also restores the starting folder when this script ends.
cd /d "%~dp0..\Program" || exit /b 1
rem One block, so cmd has read all of it before a ZIP update replaces this file. A bare "exit /b"
rem can lose the exit code under "cmd /c", so it is given explicitly (update.ps1 exits 0 or 1).
(
    powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\Program\scripts\windows\update.ps1" %* && exit /b 0
    exit /b 1
)
