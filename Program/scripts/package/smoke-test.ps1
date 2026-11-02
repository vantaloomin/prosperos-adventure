<#
.SYNOPSIS
Launches an installed or unpacked Prospero Dungeon bundle on a machine without Python or Node.

.DESCRIPTION
Verifies every file against bundle.json, hides any Python or Node from PATH and poisons the Python
environment variables, then starts the bundle's launcher and checks that it answers on its own
port, serves the interface, runs on its bundled runtime, keeps its own data directory, reuses the
running copy on a second launch and stays clear of Prospero's Study port. Used by CI.
#>
param(
  [Parameter(Mandatory = $true)][string]$Bundle,
  [string]$DataDir = (Join-Path $env:LOCALAPPDATA 'ProsperoDungeon'),
  # Prospero's Study is already running on 8765; check it instead of holding the port ourselves.
  [switch]$StudyRunning
)
$ErrorActionPreference = 'Stop'
$Bundle = (Resolve-Path -LiteralPath $Bundle).Path
$launcher = Join-Path $Bundle 'Prospero Dungeon.cmd'

function Check([bool]$condition, [string]$message) {
  if (-not $condition) { throw $message }
  Write-Host "ok  $message"
}

# Integrity: every shipped file matches the digest recorded at build time.
$manifest = Get-Content -LiteralPath (Join-Path $Bundle 'bundle.json') -Raw | ConvertFrom-Json
$mismatched = @()
foreach ($entry in $manifest.files.PSObject.Properties) {
  $path = Join-Path $Bundle $entry.Name
  if (-not (Test-Path -LiteralPath $path) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower() -ne $entry.Value) {
    $mismatched += $entry.Name
  }
}
Check ($mismatched.Count -eq 0) "all $(@($manifest.files.PSObject.Properties).Count) bundle files match bundle.json $($mismatched -join ', ')"

# A clean machine: no developer toolchain on PATH, and Python variables that would break a
# runtime that read them. C:\Windows stays off PATH because the runner keeps the py launcher there.
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot\System32\WindowsPowerShell\v1.0"
$env:PYTHONPATH = 'C:\nonexistent\pythonpath'
$env:PYTHONHOME = 'C:\nonexistent\pythonhome'
Remove-Item Env:DUNGEON_DATA_DIR, Env:DUNGEON_DB -ErrorAction SilentlyContinue
$toolchain = @(Get-Command python, python3, py, node, npm -CommandType Application -ErrorAction SilentlyContinue)
Check ($toolchain.Count -eq 0) "no Python or Node on PATH $($toolchain.Source -join ', ')"

# Prospero's Study's port is taken, as it would be with the Study running beside the Dungeon.
$study = $null
if (-not $StudyRunning) {
  $study = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 8765)
  $study.Start()
}
$log = Join-Path ([System.IO.Path]::GetTempPath()) 'dungeon-smoke.log'
$app = Start-Process -FilePath $env:ComSpec -ArgumentList '/d', '/c', "`"`"$launcher`" --no-browser > `"$log`" 2>&1`"" -PassThru -WindowStyle Hidden
try {
  $health = $null
  foreach ($attempt in 1..120) {
    try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8785/api/health' -TimeoutSec 2; break } catch { Start-Sleep -Milliseconds 500 }
  }
  if (-not $health) { Get-Content -LiteralPath $log -ErrorAction SilentlyContinue; throw 'The Dungeon did not answer on port 8785.' }
  Check ($health.app_id -eq 'prospero-dungeon' -and $health.version -eq $manifest.version) "answers as $($health.app_id) $($health.version)"
  $page = Invoke-WebRequest -Uri 'http://127.0.0.1:8785/' -UseBasicParsing
  Check ($page.Content -match 'Prospero Dungeon') 'serves the interface'

  $runtime = Join-Path $Bundle 'runtime\python.exe'
  $server = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -match 'dungeon\.launch' }
  Check ($server -and ($server | Select-Object -First 1).ExecutablePath -eq $runtime) "runs on the bundled runtime $runtime"
  # Saved API keys go to Windows Credential Manager through keyring; its backend must load here.
  $vault = & $runtime -I -c 'import keyring; print(type(keyring.get_keyring()).__name__)'
  Check ($vault -eq 'WinVaultKeyring') "finds the Windows credential store ($vault)"

  Check (Test-Path -LiteralPath (Join-Path $DataDir 'dungeon.sqlite3')) "keeps its workspace in $DataDir"
  $backup = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8785/api/backups' -Headers @{ 'x-dungeon-client' = 'workspace' }
  Check ((Test-Path -LiteralPath $backup.path) -and $backup.path.StartsWith($DataDir)) "writes backups inside its workspace: $($backup.path)"

  $second = & $env:ComSpec /d /c "`"$launcher`" --no-browser" 2>&1 | Out-String
  Check ($LASTEXITCODE -eq 0 -and $second -match 'already running') 'a second launch reuses the running copy'
  if ($StudyRunning) {
    $studyHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 5
    Check ($studyHealth.application -eq 'Roleplay') "Prospero's Study still answers on 8765"
  } else {
    Check ($study.Server.IsBound) "Prospero Study's port 8765 is left alone"
  }
} finally {
  & "$env:SystemRoot\System32\taskkill.exe" /T /F /PID $app.Id | Out-Null
  if ($study) { $study.Stop() }
}
Write-Host 'Smoke test passed.'
