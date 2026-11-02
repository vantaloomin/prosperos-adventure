# Updates this copy to the latest main, then reruns install.ps1 (locked dependencies and a fresh
# interface build). A Git clone pulls main; a copy downloaded as a ZIP downloads main's ZIP and copies
# it over.
param([switch]$NoPause)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location -LiteralPath $CompanionRoot

$UpdateZipUrl = 'https://github.com/vantaloomin/prosperos-dungeon/archive/refs/heads/main.zip'
# The files the last ZIP update copied in, so the next one can remove the ones main no longer has.
$UpdateManifest = Join-Path $CheckoutRoot '.zip-update-files'

function Invoke-Git {
    param([string[]]$Arguments)
    # Git reports progress on stderr; Windows PowerShell would treat that as a failure under 'Stop'.
    $ErrorActionPreference = 'Continue'
    $output = & git @Arguments 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed: $($output -join ' ')" }
    return $output
}

function Get-ProgramVersion([string]$Program) {
    return (Get-Content -Raw -LiteralPath (Join-Path $Program 'package.json') | ConvertFrom-Json).version
}

function Reset-DivergedMain([string]$Before, [string]$Latest) {
    # main has commits GitHub's main lacks, usually because a pull request was squash-merged: the
    # squash makes one new commit, so the local ones it replaced never fast-forward. They are kept on
    # a dated backup branch, then main is moved to match GitHub.
    $changed = Invoke-Git @('status', '--porcelain', '--untracked-files=no')
    if ($changed) {
        throw "main has changes GitHub's main does not have, and edited files that are not committed. Commit or stash them ('git stash'), then update again. Nothing was changed."
    }
    $backup = 'backup/main-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    $count = [string](Invoke-Git @('rev-list', '--count', "$Latest..$Before"))
    Invoke-Git @('branch', $backup, $Before) | Out-Null
    Invoke-Git @('reset', '--hard', $Latest) | Out-Null
    Write-Host "Your main had $count commit(s) that GitHub's main does not (usually left over from a squash merge)." -ForegroundColor Yellow
    Write-Host "They are saved on the branch $backup; main now matches GitHub. Delete that branch once you no longer need it." -ForegroundColor Yellow
}

function Update-WithGit {
    if (-not (Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue)) {
        throw 'Git was not found. Install Git for Windows, then update again.'
    }
    $branch = [string](Invoke-Git @('-C', $CheckoutRoot, 'rev-parse', '--abbrev-ref', 'HEAD'))
    if ($branch -ne 'main') { throw "This checkout is on '$branch'. update.bat only updates main; switch with 'git switch main' first." }
    $before = [string](Invoke-Git @('rev-parse', 'HEAD'))
    Invoke-Git @('fetch', 'origin', 'main') | Out-Host
    $latest = [string](Invoke-Git @('rev-parse', 'FETCH_HEAD'))
    # merge-base exits 1 for "not an ancestor", so it is run by hand rather than through Invoke-Git.
    $ErrorActionPreference = 'Continue'
    & git merge-base --is-ancestor $before $latest 2>&1 | Out-Null
    $fastForward = $LASTEXITCODE -eq 0
    $ErrorActionPreference = 'Stop'
    if ($fastForward) {
        Invoke-Git @('merge', '--ff-only', $latest) | Out-Host
    } else {
        Reset-DivergedMain $before $latest
    }
    $after = [string](Invoke-Git @('rev-parse', 'HEAD'))
    if ($before -eq $after) {
        Write-Host 'Already up to date. Reinstalling to make sure everything matches.'
    } else {
        Write-Host "Updated $($before.Substring(0, 7)) to $($after.Substring(0, 7)):"
        Invoke-Git @('log', '--oneline', '--no-decorate', "$before..$after") | Out-Host
    }
}

function Update-FromZip {
    $work = Join-Path ([IO.Path]::GetTempPath()) ("dungeon-update-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $work | Out-Null
    try {
        $zip = Join-Path $work 'main.zip'
        if ($env:DUNGEON_UPDATE_ZIP) {
            Copy-Item -LiteralPath $env:DUNGEON_UPDATE_ZIP -Destination $zip
        } else {
            Write-Host 'This copy was downloaded as a ZIP, so the latest version is downloaded the same way.'
            [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
            try {
                $ProgressPreference = 'SilentlyContinue'
                Invoke-WebRequest -UseBasicParsing -Uri $UpdateZipUrl -OutFile $zip
            } catch {
                throw "Could not download $UpdateZipUrl. Check the internet connection and try again. ($($_.Exception.Message))"
            }
        }
        $unpacked = Join-Path $work 'unpacked'
        try { Expand-Archive -LiteralPath $zip -DestinationPath $unpacked } catch { throw 'The downloaded ZIP could not be opened. Try again.' }
        # GitHub puts everything in one folder named after the repository and branch.
        $source = Get-ChildItem -LiteralPath $unpacked -Directory | Select-Object -First 1
        if (-not $source -or -not (Test-Path -LiteralPath (Join-Path $source.FullName 'Program\pyproject.toml')) -or
            -not (Test-Path -LiteralPath (Join-Path $source.FullName 'Windows\update.bat'))) {
            throw 'The downloaded ZIP does not look like Prospero Dungeon. Nothing was changed.'
        }
        $source = $source.FullName
        $before = Get-ProgramVersion $CompanionRoot
        $after = Get-ProgramVersion (Join-Path $source 'Program')
        $files = @(Get-ChildItem -LiteralPath $source -Recurse -File -Force |
            ForEach-Object { $_.FullName.Substring($source.Length + 1).Replace('\', '/') } | Sort-Object)
        # Remove what an earlier ZIP update put here that main no longer has. Only paths from that list
        # are touched, so files you added yourself (and .venv, node_modules, dist) stay.
        if (Test-Path -LiteralPath $UpdateManifest) {
            $current = @{}
            foreach ($file in $files) { $current[$file] = $true }
            foreach ($relative in Get-Content -LiteralPath $UpdateManifest) {
                if (-not $relative -or $relative.Contains('..') -or $relative.Contains(':') -or $relative.StartsWith('/') -or $current.ContainsKey($relative)) { continue }
                $stale = Join-Path $CheckoutRoot $relative
                if (Test-Path -LiteralPath $stale -PathType Leaf) { Remove-Item -LiteralPath $stale -Force }
            }
        }
        try {
            foreach ($relative in $files) {
                $target = Join-Path $CheckoutRoot $relative
                $folder = Split-Path -Parent $target
                if (-not (Test-Path -LiteralPath $folder)) { New-Item -ItemType Directory -Path $folder -Force | Out-Null }
                Copy-Item -LiteralPath (Join-Path $source $relative) -Destination $target -Force
            }
        } catch {
            throw "Copying the new version into this folder failed: $($_.Exception.Message) Run update.bat again to finish."
        }
        Set-Content -LiteralPath $UpdateManifest -Value $files -Encoding UTF8
        if ($before -eq $after) {
            Write-Host "Copied in the latest main (version $after). Reinstalling to make sure everything matches."
        } else {
            Write-Host "Updated version $before to $after."
        }
    } finally {
        Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$result = 0
try {
    Write-Host 'Prospero Dungeon - update'
    if ((Get-DungeonState 8785).State -eq 'running') {
        throw 'Prospero Dungeon is running. Close its window (or double-click stop.bat), then update again.'
    }
    if (Test-Path -LiteralPath (Join-Path $CheckoutRoot '.git')) { Update-WithGit } else { Update-FromZip }
    & (Join-Path $PSScriptRoot 'install.ps1') -NoPause
    if ($LASTEXITCODE -ne 0) { throw 'The reinstall failed; see above.' }
} catch {
    Write-Host "Update failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Your Dungeon data was not touched.'
    $result = 1
}
if (-not $NoPause) { Read-Host 'Press Enter to close' | Out-Null }
exit $result
