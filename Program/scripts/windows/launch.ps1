# Adapted from prosperos-study start.ps1 at bbcbde4: Dungeon launcher module and port.
param([switch]$NoBrowser, [switch]$NoPause, [ValidateRange(1024, 65535)][int]$Port = 8785)
$ErrorActionPreference = 'Stop'
# common.ps1 also sets the console to UTF-8 so npm, Vite and Python output renders.
. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location -LiteralPath $CompanionRoot
$result = 0
try {
    $python = Join-Path $CompanionRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Dependencies are missing. Double-click install.bat first.' }
    if (-not (Test-Path -LiteralPath 'dist\index.html')) { throw 'The interface is not built. Double-click install.bat first.' }
    $arguments = @('-m', 'dungeon.launch', '--port', [string]$Port)
    if ($NoBrowser) { $arguments += '--no-browser' }
    # The server logs to stderr; judge it by exit code, not by what it writes (see install.ps1).
    $ErrorActionPreference = 'Continue'
    & $python @arguments
    $result = $LASTEXITCODE
} catch {
    Write-Host "Launch failed: $($_.Exception.Message)" -ForegroundColor Red
    $result = 1
}
if ($result -ne 0 -and -not $NoPause) { Read-Host 'Press Enter to close' | Out-Null }
exit $result
