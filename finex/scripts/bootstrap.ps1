[CmdletBinding()]
param(
    [ValidateSet('All', 'Backend', 'React', 'Flutter')]
    [string[]]$Component = @('All'),
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$requestedComponents = if ($Component -contains 'All') {
    @('Backend', 'React', 'Flutter')
}
else {
    $Component | Select-Object -Unique
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory)]
        [string]$FilePath,
        [string[]]$ArgumentList = @()
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($ArgumentList -join ' ')"
    }
}

function Get-Python313 {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw 'Python Launcher (py) was not found. Install Python 3.13, then rerun this script.'
    }

    $version = & py -3.13 --version 2>&1
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^Python 3\.13') {
        throw 'Python 3.13 is required. Install it with the Python Launcher enabled, then rerun this script.'
    }

    return (& py -3.13 -c 'import sys; print(sys.executable)').Trim()
}

function Assert-Node24 {
    if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw 'Node.js 24 LTS and npm are required for the React client.'
    }

    $version = (& node --version).Trim()
    if ($version -notmatch '^v24\.') {
        throw "Node.js 24 LTS is required; found $version. See .nvmrc."
    }
}

function Assert-Flutter347 {
    if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
        throw 'Flutter 3.47.2 is required for the Flutter client.'
    }

    $version = (& flutter --version 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '(?m)^Flutter 3\.47\.2') {
        throw 'Flutter 3.47.2 (Dart 3.13) is required. See frontend_flutter/.flutter-version.'
    }
}

Push-Location $repositoryRoot
try {
    if ($requestedComponents -contains 'Backend') {
        $python313 = Get-Python313
        $venvDirectory = Join-Path $repositoryRoot 'backend\.venv'
        $venvPython = Join-Path $venvDirectory 'Scripts\python.exe'

        if (-not $CheckOnly) {
            if (-not (Test-Path $venvPython)) {
                Invoke-Checked -FilePath $python313 -ArgumentList @('-m', 'venv', $venvDirectory)
            }
            Invoke-Checked -FilePath $venvPython -ArgumentList @('-m', 'pip', 'install', '--upgrade', 'pip')
            Invoke-Checked -FilePath $venvPython -ArgumentList @('-m', 'pip', 'install', '-r', 'backend\requirements.txt')
        }
        Write-Host 'Backend prerequisites are ready.'
    }

    if ($requestedComponents -contains 'React') {
        Assert-Node24
        if (-not $CheckOnly) {
            Push-Location (Join-Path $repositoryRoot 'frontend-react')
            try {
                Invoke-Checked -FilePath 'npm' -ArgumentList @('ci')
            }
            finally {
                Pop-Location
            }
        }
        Write-Host 'React prerequisites are ready.'
    }

    if ($requestedComponents -contains 'Flutter') {
        Assert-Flutter347
        if (-not $CheckOnly) {
            Push-Location (Join-Path $repositoryRoot 'frontend_flutter')
            try {
                Invoke-Checked -FilePath 'flutter' -ArgumentList @('pub', 'get')
            }
            finally {
                Pop-Location
            }
        }
        Write-Host 'Flutter prerequisites are ready.'
    }
}
finally {
    Pop-Location
}
