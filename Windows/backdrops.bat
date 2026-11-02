@echo off
rem Makes the worlds' default location backdrops with ChatGPT images (Program\scripts\art\backdrops.py).
rem Needs the Codex CLI signed in to ChatGPT: npm i -g @openai/codex, then codex login.
rem At most 60 images an hour by default. Extra options pass through, for example:
rem   backdrops.bat --world havenbrooke     backdrops.bat --only smithy tavern
rem   backdrops.bat --per-hour 30           backdrops.bat --list
setlocal
pushd "%~dp0..\Program" || exit /b 1
set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Dependencies are missing. Double-click install.bat first.
  goto fail
)
where codex >nul 2>nul
if errorlevel 1 (
  echo The Codex CLI was not found. Install it with: npm i -g @openai/codex
  goto fail
)
if not defined CODEX_HOME set "CODEX_HOME=%USERPROFILE%\.codex"
if not exist "%CODEX_HOME%\auth.json" (
  echo Codex is not signed in. Run: codex login
  goto fail
)
rem Pillow saves the pictures as WebP. The app does not need it, so it goes in Program\.tools, not the app's .venv.
set "PYTHONPATH=%CD%\.tools\pillow"
"%PY%" -c "import PIL" >nul 2>nul
if errorlevel 1 (
  echo Installing Pillow into Program\.tools\pillow...
  "%PY%" -m pip install --disable-pip-version-check --no-input --quiet --target "%CD%\.tools\pillow" pillow
  if errorlevel 1 goto fail
)
"%PY%" scripts\art\backdrops.py %*
set "result=%ERRORLEVEL%"
popd
pause
exit /b %result%

:fail
popd
pause
exit /b 1
