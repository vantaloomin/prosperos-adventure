<#
.SYNOPSIS
Installs, upgrades and uninstalls the per-user setup on a machine without Python or Node.

.DESCRIPTION
Runs the setup silently without administrator rights, checks the install location, Start menu
shortcut and per-user uninstall entry, launches the installed app through smoke-test.ps1, installs
again over it as an upgrade (stale program files must go, the workspace must stay), launches again,
restores a backup with the installed launcher and launches the restored workspace, then
uninstalls and checks that the program files are gone while the workspace is kept. Used by CI.
#>
param([Parameter(Mandatory = $true)][string]$Setup)
$ErrorActionPreference = 'Stop'
$Setup = (Resolve-Path -LiteralPath $Setup).Path
$installed = Join-Path $env:LOCALAPPDATA 'Programs\Prospero Dungeon'
$workspace = Join-Path $env:LOCALAPPDATA 'ProsperoDungeon'
$shortcut = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Prospero Dungeon.lnk'
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{82941F85-FF26-49CE-80BA-9B592D72162F}_is1'
$smoke = Join-Path $PSScriptRoot 'smoke-test.ps1'

function Check([bool]$condition, [string]$message) {
  if (-not $condition) { throw $message }
  Write-Host "ok  $message"
}

function Install([string]$label) {
  $log = Join-Path ([System.IO.Path]::GetTempPath()) "dungeon-setup-$label.log"
  $process = Start-Process -FilePath $Setup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER', "/LOG=`"$log`"" -PassThru -Wait
  if ($process.ExitCode -ne 0) { Get-Content -LiteralPath $log -Tail 40; throw "Setup ($label) exited with $($process.ExitCode)." }
}

function Launch {
  # A separate process, because the smoke test strips PATH for itself.
  & (Join-Path $PSHOME 'pwsh.exe') -NoProfile -File $smoke -Bundle $installed
  if ($LASTEXITCODE -ne 0) { throw 'The installed app failed its smoke test.' }
}

Install 'first'
Check (Test-Path -LiteralPath (Join-Path $installed 'runtime\python.exe')) "installs per user into $installed"
Check (Test-Path -LiteralPath $shortcut) 'adds a Start menu shortcut'
$entry = Get-ItemProperty -LiteralPath $uninstallKey
Check ($entry.DisplayName -eq 'Prospero Dungeon') 'registers a per-user uninstall entry'
Launch

$stale = Join-Path $installed 'app\dungeon\removed_in_this_release.py'
Set-Content -LiteralPath $stale -Value '# left by an earlier release'
$database = Join-Path $workspace 'dungeon.sqlite3'
$before = (Get-Item -LiteralPath $database).Length
Install 'upgrade'
Check (-not (Test-Path -LiteralPath $stale)) 'an upgrade removes program files the new release does not ship'
Check ((Test-Path -LiteralPath $database) -and (Get-Item -LiteralPath $database).Length -ge $before) 'an upgrade keeps the workspace'
Launch

# Restore the newest backup through the installed launcher: the workspace it replaces is set aside.
$latest = Get-ChildItem -LiteralPath (Join-Path $workspace 'backups') -Filter 'dungeon-*.zip' | Sort-Object Name | Select-Object -Last 1
$restoreOutput = & $env:ComSpec /d /c "`"$(Join-Path $installed 'Prospero Dungeon.cmd')`" --restore `"$($latest.FullName)`"" 2>&1 | Out-String
Write-Host $restoreOutput
Check ($LASTEXITCODE -eq 0 -and $restoreOutput -match 'Restored') "restores $($latest.Name) with the installed launcher"
Check (@(Get-ChildItem -LiteralPath $workspace -Directory -Filter 'replaced-*').Count -ge 1) 'the replaced workspace is set aside, not deleted'
Launch

$uninstaller = ($entry.UninstallString -replace '"', '')
Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait
foreach ($attempt in 1..60) {
  if (-not (Test-Path -LiteralPath (Join-Path $installed 'runtime'))) { break }
  Start-Sleep -Milliseconds 500
}
Check (-not (Test-Path -LiteralPath (Join-Path $installed 'runtime'))) 'uninstall removes the program files'
Check (-not (Test-Path -LiteralPath $shortcut)) 'uninstall removes the Start menu shortcut'
Check (-not (Test-Path -LiteralPath $uninstallKey)) 'uninstall removes its uninstall entry'
Check (Test-Path -LiteralPath $database) "uninstall keeps the workspace in $workspace"
Write-Host 'Installer test passed.'
