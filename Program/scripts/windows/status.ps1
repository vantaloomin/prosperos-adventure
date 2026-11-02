# Says whether Prospero Dungeon is running from this checkout's port. Exit 0 running, 1 stopped, 2 port taken.
param([switch]$NoPause, [ValidateRange(1024, 65535)][int]$Port = 8785)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
$state = Get-DungeonState $Port
switch ($state.State) {
    'running' {
        Write-Host "Prospero Dungeon $($state.Version) is running at http://127.0.0.1:$Port/ (process $($state.ProcessId))." -ForegroundColor Green
        $result = 0
    }
    'foreign' {
        Write-Host "Prospero Dungeon is not running, but another program (process $($state.ProcessId)) is using port $Port." -ForegroundColor Yellow
        $result = 2
    }
    default {
        Write-Host "Prospero Dungeon is not running. Double-click launch.bat to start it."
        $result = 1
    }
}
if (-not $NoPause) { Read-Host 'Press Enter to close' | Out-Null }
exit $result
