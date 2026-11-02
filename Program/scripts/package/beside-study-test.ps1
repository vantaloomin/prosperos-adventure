<#
.SYNOPSIS
Runs the installed Adventure beside a running Prospero's Study (PRD "Standalone delivery").

.DESCRIPTION
Starts the Study from its checkout on its own port 8765, installs Adventure setup, and checks
that the two never collide: an Adventure pointed at the Study's port refuses and stops nothing, the
Adventure launches on 8805 while the Study keeps answering, each keeps its data in its own place,
and the Study's database never gains Adventure's identity marker. Used by CI.
#>
param(
  [Parameter(Mandatory = $true)][string]$Setup,
  [Parameter(Mandatory = $true)][string]$Study
)
$ErrorActionPreference = 'Stop'
$Setup = (Resolve-Path -LiteralPath $Setup).Path
$Study = (Resolve-Path -LiteralPath $Study).Path
$installed = Join-Path $env:LOCALAPPDATA 'Programs\Prospero Adventure'
$workspace = Join-Path $env:LOCALAPPDATA 'ProsperoAdventure'
$studyData = Join-Path $Study 'data'

function Check([bool]$condition, [string]$message) {
  if (-not $condition) { throw $message }
  Write-Host "ok  $message"
}

function StudyHealth {
  try { return Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 2 } catch { return $null }
}

$studyLog = Join-Path ([System.IO.Path]::GetTempPath()) 'study.log'
$studyErrors = Join-Path ([System.IO.Path]::GetTempPath()) 'study-errors.log'
# Started the way the Study's own start.ps1 does, as a module from its checkout.
$studyApp = Start-Process -FilePath (Join-Path $Study '.venv\Scripts\python.exe') -ArgumentList '-m', 'scripts.launch_interface', '--no-browser' `
  -WorkingDirectory $Study -RedirectStandardOutput $studyLog -RedirectStandardError $studyErrors -PassThru -WindowStyle Hidden
try {
  $health = $null
  foreach ($attempt in 1..120) {
    $health = StudyHealth
    if ($health -or $studyApp.HasExited) { break }
    Start-Sleep -Milliseconds 500
  }
  if (-not $health) {
    Get-Content -LiteralPath $studyLog, $studyErrors -ErrorAction SilentlyContinue
    throw 'The Study did not start.'
  }
  Check ($health.application -eq 'Roleplay') "Prospero's Study runs on 8765"

  $process = Start-Process -FilePath $Setup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER' -PassThru -Wait
  Check ($process.ExitCode -eq 0) 'Adventure installs while the Study runs'

  $launcher = Join-Path $installed 'Prospero Adventure.cmd'
  $refused = & $env:ComSpec /d /c "`"$launcher`" --port 8765 --no-browser" 2>&1 | Out-String
  Check ($LASTEXITCODE -ne 0 -and $refused -match 'Nothing was stopped') 'an Adventure pointed at the Study port refuses and stops nothing'
  Check ((StudyHealth).application -eq 'Roleplay') 'the Study still answers after that refusal'

  & (Join-Path $PSHOME 'pwsh.exe') -NoProfile -File (Join-Path $PSScriptRoot 'smoke-test.ps1') -Bundle $installed -StudyRunning
  if ($LASTEXITCODE -ne 0) { throw 'Adventure failed its smoke test beside the Study.' }

  Check (Test-Path -LiteralPath (Join-Path $studyData 'roleplay.sqlite3')) "the Study keeps its database in its own data folder"
  $studyFiles = @(Get-ChildItem -LiteralPath $studyData -Recurse -File | ForEach-Object { $_.Name })
  Check (-not ($studyFiles | Where-Object { $_ -like 'adventure*' })) "the Study's data folder holds no Adventure files"
  $adventureFiles = @(Get-ChildItem -LiteralPath $workspace -Recurse -File | ForEach-Object { $_.Name })
  Check (-not ($adventureFiles | Where-Object { $_ -like 'roleplay*' })) "Adventure's workspace holds no Study files"
  $probe = "import sqlite3,sys; c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro', uri=True); " +
           "print(','.join(r[0] for r in c.execute(`"SELECT name FROM sqlite_master WHERE type='table'`")))"
  $tables = & (Join-Path $installed 'runtime\python.exe') -I -c $probe (Join-Path $studyData 'roleplay.sqlite3')
  Check ($LASTEXITCODE -eq 0 -and $tables -and $tables -notmatch 'app_identity') "the Study's database never gains Adventure marker"
} finally {
  if (-not $studyApp.HasExited) { & "$env:SystemRoot\System32\taskkill.exe" /T /F /PID $studyApp.Id | Out-Null }
}
Write-Host 'Beside-the-Study test passed.'
