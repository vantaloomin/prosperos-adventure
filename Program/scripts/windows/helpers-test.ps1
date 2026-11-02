<#
.SYNOPSIS
Exercises the checkout helpers (status, stop, create-shortcut, dev, update) after install.ps1. Used by CI.

.DESCRIPTION
Runs each helper through its .bat wrapper where it can, so the wrappers are tested too. Expects
install.ps1 to have finished and DUNGEON_DATA_DIR to point at a scratch workspace. The update
check rewires this checkout's origin to a local repository, so run it on a throwaway checkout only.
#>
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location -LiteralPath $CompanionRoot

function Check([bool]$condition, [string]$message) {
  if (-not $condition) { throw $message }
  Write-Host "ok  $message"
}

function Invoke-Bat([string]$Name, [string[]]$Arguments) {
  & cmd.exe /d /c (Join-Path $WindowsFolder $Name) -NoPause @Arguments | Out-Host
  return $LASTEXITCODE
}

function Wait-State([string]$Expected, [int]$Port = 8785) {
  foreach ($attempt in 1..120) {
    if ((Get-DungeonState $Port).State -eq $Expected) { return $true }
    Start-Sleep -Milliseconds 250
  }
  return $false
}

function Get-Page([string]$Url) {
  $request = [System.Net.WebRequest]::Create($Url)
  $request.Proxy = $null
  $request.Timeout = 3000
  $response = $request.GetResponse()
  try { return (New-Object System.IO.StreamReader($response.GetResponseStream())).ReadToEnd() } finally { $response.Close() }
}

$temp = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }

# status and stop
Check ((Invoke-Bat 'status.bat') -eq 1) 'status.bat reports a stopped Dungeon with exit code 1'
Check ((Invoke-Bat 'stop.bat') -eq 0) 'stop.bat with nothing running succeeds and stops nothing'
# Captured output, as when another program starts it: the server's log lines on stderr must not stop it.
$app = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'launch.ps1'), '-NoBrowser', '-NoPause' -PassThru -RedirectStandardOutput (Join-Path $temp 'launch-out.txt') -RedirectStandardError (Join-Path $temp 'launch-err.txt')
try {
  Check (Wait-State 'running') 'launch answers on 8785'
  Check ((Invoke-Bat 'status.bat') -eq 0) 'status.bat reports the running Dungeon with exit code 0'
  Check ((Invoke-Bat 'stop.bat') -eq 0) 'stop.bat stops the running Dungeon'
  Check ((Get-DungeonState 8785).State -eq 'stopped') 'port 8785 is free after stop.bat'
} finally { if (-not $app.HasExited) { & taskkill.exe /PID $app.Id /T /F | Out-Null } }

# Another program on the port is reported and never stopped.
$python = Join-Path $CompanionRoot '.venv\Scripts\python.exe'
$foreign = Start-Process -FilePath $python -ArgumentList '-m', 'http.server', '8790', '--bind', '127.0.0.1' -PassThru -WindowStyle Hidden
try {
  Check (Wait-State 'foreign' 8790) 'a foreign server holds 8790'
  Check ((Invoke-Bat 'status.bat' @('-Port', '8790')) -eq 2) 'status.bat reports a port held by another program with exit code 2'
  Check ((Invoke-Bat 'stop.bat' @('-Port', '8790')) -eq 1) 'stop.bat refuses to stop another program'
  Check (-not $foreign.HasExited) 'the other program is still running'
} finally { if (-not $foreign.HasExited) { Stop-Process -Id $foreign.Id -Force } }

# create-shortcut
$desktop = Join-Path $temp 'desktop'
New-Item -ItemType Directory -Force -Path $desktop | Out-Null
Check ((Invoke-Bat 'create-shortcut.bat' @('-Destination', $desktop)) -eq 0) 'create-shortcut.bat succeeds'
$link = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Prospero Dungeon.lnk'))
Check ($link.TargetPath -eq (Join-Path $WindowsFolder 'launch.bat')) 'the shortcut starts this checkout''s launch.bat'
$other = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Prospero Dungeon.lnk'))
$other.TargetPath = "$env:SystemRoot\System32\notepad.exe"
$other.Save()
Check ((Invoke-Bat 'create-shortcut.bat' @('-Destination', $desktop)) -eq 0) 'create-shortcut.bat succeeds beside an installed app''s shortcut'
Check ((New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Prospero Dungeon.lnk')).TargetPath -like '*notepad.exe') 'the existing shortcut is left alone'
Check (Test-Path -LiteralPath (Join-Path $desktop 'Prospero Dungeon (checkout).lnk')) 'the checkout shortcut gets its own name'

# dev: backend plus Vite, with /api forwarded to the backend
$dev = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'dev.ps1'), '-NoBrowser' -PassThru -RedirectStandardOutput (Join-Path $temp 'dev-out.txt') -RedirectStandardError (Join-Path $temp 'dev-err.txt')
try {
  Check (Wait-State 'running') 'dev mode starts the backend on 8785'
  $page = $null
  foreach ($attempt in 1..120) {
    try { $page = Get-Page 'http://127.0.0.1:5177/'; break } catch { Start-Sleep -Milliseconds 500 }
  }
  Check ($page -match 'Prospero Dungeon') 'Vite serves the interface on 5177'
  Check ((Get-Page 'http://127.0.0.1:5177/api/health' | ConvertFrom-Json).app_id -eq $DungeonAppId) 'Vite forwards /api to the backend'
} finally { & taskkill.exe /PID $dev.Id /T /F | Out-Null }
Check (Wait-State 'stopped') 'closing dev mode stops its backend'

# update: fast-forward from a local origin, then reinstall. CI checkouts are shallow, so the
# local origin accepts shallow pushes.
function Invoke-TestGit([string[]]$Arguments) {
  & git @Arguments | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed" }
}
Invoke-TestGit @('config', '--global', 'user.email', 'ci@example.invalid')
Invoke-TestGit @('config', '--global', 'user.name', 'CI')
$remote = Join-Path $temp 'update-origin.git'
$clone = Join-Path $temp 'update-clone'
Invoke-TestGit @('init', '--quiet', '--bare', $remote)
Invoke-TestGit @('-C', $remote, 'config', 'receive.shallowUpdate', 'true')
Invoke-TestGit @('checkout', '--quiet', '-B', 'main')
Invoke-TestGit @('push', '--quiet', $remote, 'HEAD:refs/heads/main')
Invoke-TestGit @('clone', '--quiet', '--branch', 'main', $remote, $clone)
Set-Content -LiteralPath (Join-Path $clone 'update-marker.txt') -Value 'pulled'
Invoke-TestGit @('-C', $clone, 'add', 'update-marker.txt')
Invoke-TestGit @('-C', $clone, 'commit', '--quiet', '-m', 'Marker for the update test')
Invoke-TestGit @('-C', $clone, 'push', '--quiet', 'origin', 'main')
Invoke-TestGit @('remote', 'set-url', 'origin', $remote)
Check ((Invoke-Bat 'update.bat') -eq 0) 'update.bat pulls main and reinstalls'
Check (Test-Path -LiteralPath (Join-Path $CheckoutRoot 'update-marker.txt')) 'the new commit was pulled'
Check (Test-Path -LiteralPath 'dist\index.html') 'the interface was rebuilt'
# A main that diverged from origin (as after a squash merge) is backed up to a branch, then reset.
Set-Content -LiteralPath (Join-Path $CheckoutRoot 'local-only.txt') -Value 'local'
Invoke-TestGit @('-C', $CheckoutRoot, 'add', 'local-only.txt')
Invoke-TestGit @('-C', $CheckoutRoot, 'commit', '--quiet', '-m', 'Local commit GitHub never got')
Set-Content -LiteralPath (Join-Path $clone 'squashed.txt') -Value 'squashed'
Invoke-TestGit @('-C', $clone, 'add', 'squashed.txt')
Invoke-TestGit @('-C', $clone, 'commit', '--quiet', '-m', 'Squash merge on GitHub')
Invoke-TestGit @('-C', $clone, 'push', '--quiet', 'origin', 'main')
Check ((Invoke-Bat 'update.bat') -eq 0) 'update.bat updates a main that diverged from origin'
Check (Test-Path -LiteralPath (Join-Path $CheckoutRoot 'squashed.txt')) 'main now matches origin'
Check (-not (Test-Path -LiteralPath (Join-Path $CheckoutRoot 'local-only.txt'))) 'the local-only commit left main'
$backups = @(& git branch --list 'backup/main-*' --format '%(refname:short)')
Check ($backups.Count -eq 1) 'the local-only commit was kept on a backup branch'
& git cat-file -e "$($backups[0]):local-only.txt" 2>$null
Check ($LASTEXITCODE -eq 0) 'the backup branch has the local-only file'
# A host that captures stderr (a terminal tool, a scheduled task) must not turn npm's notices into
# failures: Windows PowerShell 5.1 wraps captured native stderr as errors. npm logs to stderr.
$env:npm_config_loglevel = 'http'
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& cmd.exe /d /c (Join-Path $WindowsFolder 'update.bat') -NoPause 2>&1 | ForEach-Object { "$_" } | Out-Host
$code = $LASTEXITCODE
Check ($code -eq 0) 'update.bat succeeds when its stderr is captured and npm writes to it'
# Calling the script directly with its errors redirected (as terminal tools do) makes Windows
# PowerShell 5.1 hand every native stderr line to the script as an error record.
& powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '$(Join-Path $PSScriptRoot 'update.ps1')' -NoPause 2>&1 | ForEach-Object { `"`$_`" }; exit `$LASTEXITCODE" | Out-Host
$code = $LASTEXITCODE
$ErrorActionPreference = $previous
Remove-Item Env:npm_config_loglevel
Check ($code -eq 0) 'update.ps1 succeeds when called with its error stream redirected'
$app = Start-Process -FilePath $python -ArgumentList '-m', 'dungeon.launch', '--no-browser' -PassThru -NoNewWindow
try {
  Check (Wait-State 'running') 'the Dungeon launches after updating'
  Check ((Invoke-Bat 'update.bat') -eq 1) 'update.bat refuses while the Dungeon runs'
} finally { & taskkill.exe /PID $app.Id /T /F | Out-Null }
Invoke-TestGit @('checkout', '--quiet', '-b', 'elsewhere')
Check ((Invoke-Bat 'update.bat') -eq 1) 'update.bat refuses a branch other than main'

# update from a ZIP download: a copy without .git gets main's ZIP (here a local one) copied over it.
# Files an earlier ZIP update listed and main no longer has are removed; anything else stays.
$zip = Join-Path $temp 'update-main.zip'
Invoke-TestGit @('-C', $CheckoutRoot, 'archive', '--format=zip', '--prefix=prosperos-dungeon-main/', '--output', $zip, 'HEAD')
Remove-Item -LiteralPath (Join-Path $WindowsFolder 'README.txt')
Set-Content -LiteralPath (Join-Path $CheckoutRoot 'stale-from-zip.txt') -Value 'stale'
Set-Content -LiteralPath (Join-Path $CheckoutRoot 'my-own-file.txt') -Value 'mine'
Set-Content -LiteralPath (Join-Path $CheckoutRoot '.zip-update-files') -Value 'stale-from-zip.txt'
$gitAside = "$CheckoutRoot.git-aside"
Move-Item -LiteralPath (Join-Path $CheckoutRoot '.git') -Destination $gitAside
$env:DUNGEON_UPDATE_ZIP = $zip
try { $code = Invoke-Bat 'update.bat' } finally {
  Remove-Item Env:DUNGEON_UPDATE_ZIP
  Move-Item -LiteralPath $gitAside -Destination (Join-Path $CheckoutRoot '.git')
}
Check ($code -eq 0) 'update.bat updates a copy downloaded as a ZIP'
Check (Test-Path -LiteralPath (Join-Path $WindowsFolder 'README.txt')) 'the ZIP was copied in'
Check (-not (Test-Path -LiteralPath (Join-Path $CheckoutRoot 'stale-from-zip.txt'))) 'a file the last ZIP update listed and main dropped is removed'
Check (Test-Path -LiteralPath (Join-Path $CheckoutRoot 'my-own-file.txt')) 'a file of your own is kept'
Check ((Get-Content -LiteralPath (Join-Path $CheckoutRoot '.zip-update-files')) -contains 'Windows/update.bat') 'the new file list was written'
Check (Test-Path -LiteralPath 'dist\index.html') 'the interface was rebuilt after the ZIP update'

# A .venv without pip (as when the Python it was made from changes under it) is rebuilt.
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $python -m pip uninstall --yes --quiet pip 2>&1 | ForEach-Object { "$_" } | Out-Host
& $python -m pip --version 2>&1 | Out-Null
$code = $LASTEXITCODE
$ErrorActionPreference = $previous
Check ($code -ne 0) 'the test .venv has lost pip'
Check ((Invoke-Bat 'install.bat') -eq 0) 'install.bat rebuilds a .venv without pip'
& $python -m pip --version | Out-Host
Check ($LASTEXITCODE -eq 0) 'the rebuilt .venv has pip'

# Earlier checks expect exit code 1 from update.bat; don't let one become this script's result.
Write-Host 'All checkout helper checks passed.'
exit 0
