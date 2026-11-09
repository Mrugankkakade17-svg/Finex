[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet('127.0.0.1', 'localhost', '::1')]
    [string]$BindAddress = '127.0.0.1',
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [switch]$Reload
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repositoryRoot 'backend\.venv\Scripts\python.exe'

$uvicornArguments = @(
    '-m', 'uvicorn', 'app.main:app',
    '--app-dir', 'backend',
    '--host', $BindAddress,
    '--port', $Port,
    # Local identities must use the actual peer, never forwarded headers.
    '--no-proxy-headers',
    # Legacy refresh accepts a query token; never log raw request URLs.
    '--no-access-log'
)

if ($Reload) {
    # Keep reload focused on Python source. Watching the whole repository can
    # consume needless resources on lower-memory developer machines.
    $uvicornArguments += @(
        '--reload',
        '--reload-dir', 'backend',
        '--reload-dir', 'ai'
    )
}

if (-not $PSCmdlet.ShouldProcess('Native loopback FinEx API', "Run Python $($uvicornArguments -join ' ')")) {
    return
}

if (-not (Test-Path $venvPython)) {
    throw 'Backend virtual environment is missing. Run .\scripts\bootstrap.ps1 -Component Backend first.'
}

$previousBindSetting = [Environment]::GetEnvironmentVariable('HOST', 'Process')
Push-Location $repositoryRoot
try {
    # Keep typed configuration consistent with the actual native launch binding.
    # Public deployment is a separate workflow; synthetic personas are local only.
    $env:HOST = $BindAddress
    & $venvPython @uvicornArguments
    if ($LASTEXITCODE -ne 0) {
        throw 'FinEx backend stopped with an error.'
    }
}
finally {
    [Environment]::SetEnvironmentVariable('HOST', $previousBindSetting, 'Process')
    Pop-Location
}
