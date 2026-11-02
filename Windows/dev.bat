@echo off
setlocal
pushd "%~dp0..\Program" || exit /b 1
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\Program\scripts\windows\dev.ps1" %*
set "result=%ERRORLEVEL%"
popd
exit /b %result%
