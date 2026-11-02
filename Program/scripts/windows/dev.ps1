# Development mode: the backend (reloading on Python changes) in its own window, and Vite on 5177 in this one.
param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location -LiteralPath $CompanionRoot
$backend = $null
$result = 0
try {
    $python = Join-Path $CompanionRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Dependencies are missing. Double-click install.bat first.' }
    if (-not (Test-Path -LiteralPath 'node_modules')) { throw 'Interface packages are missing. Double-click install.bat first.' }
    $npm = Get-Command npm.cmd -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $npm) { throw 'npm was not found. Double-click install.bat first.' }
    if (Get-PortOwner 5177) { throw 'Port 5177 is in use, probably by another dev window. Close it and retry.' }

    $state = Get-DungeonState 8785
    if ($state.State -eq 'foreign') { throw "Port 8785 belongs to another program (process $($state.ProcessId)). Nothing was stopped." }
    if ($state.State -eq 'running') {
        Write-Host 'Using the Prospero Dungeon backend that is already running on 8785 (it will not reload on changes).'
    } else {
        $arguments = @('-m', 'uvicorn', 'dungeon.main:create_app', '--factory', '--host', '127.0.0.1', '--port', '8785',
            '--reload', '--reload-dir', 'dungeon')
        $backend = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $CompanionRoot -PassThru
        foreach ($attempt in 1..120) {
            if ((Get-DungeonState 8785).State -eq 'running') { break }
            if ($backend.HasExited) { throw 'The backend stopped while starting; run it by hand to see why.' }
            Start-Sleep -Milliseconds 250
        }
        if ((Get-DungeonState 8785).State -ne 'running') { throw 'The backend did not answer on 8785.' }
        Write-Host "Backend running on http://127.0.0.1:8785 in its own window (process $($backend.Id))."
    }
    $stopping = if ($backend) { 'Press Ctrl+C here to stop both.' } else { 'Press Ctrl+C here to stop it.' }
    Write-Host "Interface: http://127.0.0.1:5177 (reloads as you edit src/). $stopping"
    Write-Host 'Dev mode uses your real workspace. Set DUNGEON_DATA_DIR to a scratch folder to keep it apart.' -ForegroundColor Yellow
    $viteArguments = @('run', 'dev')
    if (-not $NoBrowser) { $viteArguments += @('--', '--open') }
    # Vite and npm may write notices to stderr; judge them by exit code (see install.ps1).
    $ErrorActionPreference = 'Continue'
    & $npm.Source @viteArguments
} catch {
    Write-Host "Dev mode failed: $($_.Exception.Message)" -ForegroundColor Red
    $result = 1
} finally {
    if ($backend -and -not $backend.HasExited) {
        $ErrorActionPreference = 'Continue'
        & taskkill.exe /PID $backend.Id /T /F 2>&1 | Out-Null
        Write-Host 'Stopped the development backend.'
    }
}
if ($result -ne 0) { Read-Host 'Press Enter to close' | Out-Null }
exit $result
