# Shared by the checkout helpers (status, stop, update, dev). Dot-source it; it defines functions and
# sets the console's output encoding.
# Program (the code, its .venv, node_modules and dist), the checkout above it, and the Windows folder of
# double-click scripts beside it.
$CompanionRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$CheckoutRoot = Split-Path -Parent $CompanionRoot
$WindowsFolder = Join-Path $CheckoutRoot 'Windows'
$DungeonAppId = 'prospero-dungeon'
# npm, Vite and Python write UTF-8; decode their captured output as UTF-8 so symbols such as the
# build's checkmark render instead of mojibake. A host without a console may refuse; that is fine.
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch { }

function Get-CompanionHealth {
    # The health answer on the port, or $null when nothing answers. Ignores any system proxy.
    param([int]$Port)
    try {
        $request = [System.Net.WebRequest]::Create("http://127.0.0.1:$Port/api/health")
        $request.Proxy = $null
        $request.Timeout = 1500
        $response = $request.GetResponse()
        try {
            $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
            return $reader.ReadToEnd() | ConvertFrom-Json
        } finally { $response.Close() }
    } catch [System.Net.WebException] {
        if ($_.Exception.Response) { return @{ app_id = '' } }
        return $null
    } catch {
        return @{ app_id = '' }
    }
}

function Get-PortOwner {
    # The process id listening on 127.0.0.1:<Port>, or $null.
    param([int]$Port)
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -in @('127.0.0.1', '0.0.0.0', '::', '::1') } | Select-Object -First 1
    if ($listener) { return [int]$listener.OwningProcess }
}

function Get-DungeonState {
    # 'running' (this app answers), 'foreign' (another program holds the port) or 'stopped'.
    param([int]$Port)
    $health = Get-CompanionHealth $Port
    if ($health -and $health.app_id -eq $DungeonAppId) {
        return @{ State = 'running'; Version = $health.version; ProcessId = Get-PortOwner $Port }
    }
    $owner = Get-PortOwner $Port
    if ($health -or $owner) { return @{ State = 'foreign'; ProcessId = $owner } }
    return @{ State = 'stopped' }
}
