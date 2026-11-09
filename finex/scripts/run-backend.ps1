[CmdletBinding()]
param(
    [string]$BindAddress = '127.0.0.1',
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [switch]$Reload
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repositoryRoot 'backend\.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    throw 'Backend virtual environment is missing. Run .\scripts\bootstrap.ps1 -Component Backend first.'
}

$uvicornArguments = @(
    '-m', 'uvicorn', 'app.main:app',
    '--app-dir', 'backend',
    '--host', $BindAddress,
    '--port', $Port
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

Push-Location $repositoryRoot
try {
    & $venvPython @uvicornArguments
    if ($LASTEXITCODE -ne 0) {
        throw 'FinEx backend stopped with an error.'
    }
}
finally {
    Pop-Location
}
