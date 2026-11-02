# Adapted from prosperos-study install.ps1 at bbcbde4: Dungeon name and dependency checks.
param([switch]$NoPause, [switch]$CheckOnly, [string]$Desktop = [Environment]::GetFolderPath('Desktop'))
$ErrorActionPreference = 'Stop'
# common.ps1 also sets the console to UTF-8 so npm, Vite and Python output renders.
. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location -LiteralPath $CompanionRoot

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    # Judge tools by exit code. When this window's stderr is captured, Windows PowerShell 5.1 turns
    # npm and pip notices into errors, which 'Stop' would make fatal.
    $ErrorActionPreference = 'Continue'
    & $Executable @Arguments 2>&1 | ForEach-Object { "$_" } | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE. Fix the error above and rerun install.bat." }
}

function Find-Executable {
    param([string]$Name)
    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { return $command.Source }
}

function Test-Python {
    param([string]$Executable, [string[]]$Prefix = @())
    $ErrorActionPreference = 'Continue'
    if (-not $Executable -or -not (Test-Path -LiteralPath $Executable)) { return }
    if ($Executable -match 'Microsoft\\WindowsApps\\python[0-9.]*\.exe$') { return }
    try {
        $result = & $Executable @Prefix -c 'import sys; sys.exit(1) if sys.version_info < (3,12) else print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0) { return [string]$result }
    } catch { return }
}

function Test-Pip {
    param([string]$Executable)
    $ErrorActionPreference = 'Continue'
    try { & $Executable -m pip --version 2>$null | Out-Null; return $LASTEXITCODE -eq 0 } catch { return $false }
}

function Find-Python {
    $candidates = @(
        (Join-Path $CompanionRoot '.venv\Scripts\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Find-Executable 'python.exe')
    )
    foreach ($candidate in $candidates) {
        $found = Test-Python $candidate
        if ($found) { return $found }
    }
    return Test-Python (Find-Executable 'py.exe') @('-3.12')
}

function Find-Node {
    $executable = Find-Executable 'node.exe'
    if (-not $executable) { return }
    $ErrorActionPreference = 'Continue'
    try {
        $version = & $executable -p 'process.versions.node' 2>$null
        if ($LASTEXITCODE -eq 0 -and [version]$version -ge [version]'22.13.0') { return $executable }
    } catch { return }
}

function Install-Prerequisite {
    param([string]$PackageId)
    $winget = Find-Executable 'winget.exe'
    if (-not $winget) {
        throw 'WinGet is unavailable. Install App Installer from Microsoft Store, or install Python 3.12+ and Node.js 22.13+ manually, then rerun install.bat.'
    }
    Write-Host "Installing missing prerequisite: $PackageId. Windows may request administrator approval."
    Invoke-Checked $winget @('install', '--exact', '--id', $PackageId, '--source', 'winget', '--silent', '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity')
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath;$env:Path"
}

function Get-Prerequisites {
    $python = Find-Python
    if (-not $python -and -not $CheckOnly) { Install-Prerequisite 'Python.Python.3.12'; $python = Find-Python }
    if (-not $python) { throw 'Python 3.12+ was not found. Reopen this installer after installing Python.' }
    $node = Find-Node
    if (-not $node -and -not $CheckOnly) { Install-Prerequisite 'OpenJS.NodeJS.LTS'; $node = Find-Node }
    if (-not $node) { throw 'Node.js 22.13+ was not found. Reopen this installer after installing Node.js.' }
    $npm = Join-Path (Split-Path -Parent $node) 'npm.cmd'
    if (-not (Test-Path -LiteralPath $npm)) { throw 'npm.cmd is missing beside Node.js. Repair the Node.js installation and retry.' }
    return @{ Python = $python; Npm = $npm }
}

function Test-ProjectInstallation {
    param([string]$Python, [string]$Npm)
    if (-not (Test-Path -LiteralPath $Python)) { throw 'The project environment is missing. Run install.bat first.' }
    Invoke-Checked $Python @('-m', 'pip', 'check')
    Invoke-Checked $Python @('-c', 'import fastapi, uvicorn, httpx, pydantic, keyring')
    Invoke-Checked $Npm @('ls', '--depth=0')
    if (-not (Test-Path -LiteralPath 'dist\index.html')) { throw 'The interface has not been built. Run install.bat.' }
}

function Install-Project {
    param([hashtable]$Runtime)
    $python = Join-Path $CompanionRoot '.venv\Scripts\python.exe'
    # .venv only holds installed packages, so a broken one is rebuilt. It breaks when the Python it was
    # made from is upgraded or removed, which can leave it without pip or its packages.
    if ((Test-Path -LiteralPath '.venv') -and -not ((Test-Python $python) -and (Test-Pip $python))) {
        Write-Host 'The project environment (.venv) is broken or was made by a Python that has since changed. Rebuilding it.' -ForegroundColor Yellow
        try { Remove-Item -LiteralPath '.venv' -Recurse -Force } catch { throw "Could not remove $CompanionRoot\.venv ($($_.Exception.Message)). Delete that folder and rerun install.bat." }
        $Runtime.Python = Find-Python
        if (-not $Runtime.Python) { throw 'Python 3.12+ was not found. Reopen this installer after installing Python.' }
    }
    if (-not (Test-Path -LiteralPath '.venv')) { Invoke-Checked $Runtime.Python @('-m', 'venv', '.venv') }
    Invoke-Checked $python @('-m', 'pip', 'install', '--disable-pip-version-check', '--no-input', '-r', 'requirements.lock.txt')
    Invoke-Checked $Runtime.Npm @('ci', '--no-audit', '--no-fund')
    Invoke-Checked $Runtime.Npm @('run', 'build')
    Test-ProjectInstallation $python $Runtime.Npm
}

function Remove-OldItem {
    param([string]$Path)
    try { Remove-Item -LiteralPath $Path -Recurse -Force; return $true }
    catch { Write-Host "Could not remove $Path ($($_.Exception.Message)). It is no longer used; delete it when you can." -ForegroundColor Yellow }
}

function Move-FromOldLayout {
    # Until October 2026 the double-click scripts and the code sat together at the top of the checkout.
    # Tidies what an install from then left there, so the top holds only Windows, Mac and Program.
    if (-not (Test-Path -LiteralPath (Join-Path $WindowsFolder 'install.bat'))) { return }
    $changed = $false
    $oldCities = Join-Path $CheckoutRoot 'private-cities'
    $newCities = Join-Path $CompanionRoot 'private-cities'
    if ((Test-Path -LiteralPath $oldCities) -and -not (Test-Path -LiteralPath $newCities)) {
        Move-Item -LiteralPath $oldCities -Destination $newCities
        Write-Host 'Moved your private-cities folder into Program.'
        $changed = $true
    }
    # The old install's environment, packages and build; this install makes its own inside Program.
    foreach ($name in '.venv', 'node_modules', 'dist') {
        $old = Join-Path $CheckoutRoot $name
        if ((Test-Path -LiteralPath $old) -and (Remove-OldItem $old)) { $changed = $true }
    }
    # Code folders git emptied when they moved, kept alive only by Python's caches.
    foreach ($name in 'companion', 'tests', 'scripts', 'src', 'public', 'docs') {
        $old = Join-Path $CheckoutRoot $name
        if (-not (Test-Path -LiteralPath $old)) { continue }
        $kept = Get-ChildItem -LiteralPath $old -Recurse -File -Force | Where-Object { $_.FullName -notmatch '\\__pycache__\\' }
        if (-not $kept -and (Remove-OldItem $old)) { $changed = $true }
    }
    # Desktop shortcuts that create-shortcut.bat made for the old launch.bat.
    $oldLaunch = Join-Path $CheckoutRoot 'launch.bat'
    $shell = New-Object -ComObject WScript.Shell
    foreach ($link in Get-ChildItem -LiteralPath $Desktop -Filter 'Prospero Dungeon*.lnk' -ErrorAction SilentlyContinue) {
        $shortcut = $shell.CreateShortcut($link.FullName)
        if ($shortcut.TargetPath -ne $oldLaunch) { continue }
        $shortcut.TargetPath = Join-Path $WindowsFolder 'launch.bat'
        $shortcut.WorkingDirectory = $CompanionRoot
        $shortcut.Save()
        Write-Host "Pointed the desktop shortcut $($link.BaseName) at Windows\launch.bat."
        $changed = $true
    }
    if ($changed) {
        Write-Host 'The double-click scripts now live in the Windows folder (Mac ones in Mac), and the code in Program.' -ForegroundColor Green
    }
}

$result = 0
try {
    Write-Host "Prospero Dungeon - dependency setup"
    $runtime = Get-Prerequisites
    if ($CheckOnly) {
        Test-ProjectInstallation (Join-Path $CompanionRoot '.venv\Scripts\python.exe') $runtime.Npm
    } else {
        Move-FromOldLayout
        Install-Project $runtime
    }
    Write-Host 'Ready. Double-click launch.bat in the Windows folder to open Prospero Dungeon.' -ForegroundColor Green
    Write-Host 'Connect a model in Settings inside the app. Nothing is downloaded until you choose to.'
    # What this computer can run locally (dungeon/hardware.py). Advice only: it never fails setup.
    try {
        Write-Host ''
        & (Join-Path $CompanionRoot '.venv\Scripts\python.exe') -m dungeon.hardware
    } catch { }
} catch {
    Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    $result = 1
}
if (-not $NoPause) { Read-Host 'Press Enter to close' | Out-Null }
exit $result
