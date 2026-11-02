# Stops a running Prospero Dungeon, and only that: another program on the port is never touched.
param([switch]$NoPause, [ValidateRange(1024, 65535)][int]$Port = 8785)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
$result = 0
try {
    $state = Get-DungeonState $Port
    if ($state.State -eq 'stopped') {
        Write-Host 'Prospero Dungeon is not running. Nothing to stop.'
    } elseif ($state.State -eq 'foreign') {
        throw "Port $Port belongs to another program (process $($state.ProcessId)). Nothing was stopped."
    } elseif (-not $state.ProcessId) {
        throw 'Prospero Dungeon answers, but its process could not be found. Close its window instead.'
    } else {
        # /T also ends the worker a development backend started with --reload.
        $ErrorActionPreference = 'Continue'
        & taskkill.exe /PID $state.ProcessId /T /F 2>&1 | Out-Null
        $ErrorActionPreference = 'Stop'
        foreach ($attempt in 1..40) {
            if ((Get-DungeonState $Port).State -eq 'stopped') { break }
            Start-Sleep -Milliseconds 250
        }
        if ((Get-DungeonState $Port).State -ne 'stopped') { throw "Process $($state.ProcessId) did not stop." }
        Write-Host 'Stopped Prospero Dungeon. Your workspace is saved; launch.bat starts it again.' -ForegroundColor Green
    }
} catch {
    Write-Host "Stop failed: $($_.Exception.Message)" -ForegroundColor Red
    $result = 1
}
if (-not $NoPause) { Read-Host 'Press Enter to close' | Out-Null }
exit $result
