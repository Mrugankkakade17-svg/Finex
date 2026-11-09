[CmdletBinding()]
param([string]$Python, [string]$TestedSha)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $repositoryRoot 'backend/.venv/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Run scripts/bootstrap.ps1 -Component Backend first, or supply -Python with your existing venv interpreter.'
}
$oldPythonPath = $env:PYTHONPATH
Push-Location (Join-Path $repositoryRoot 'backend')
try {
    $env:PYTHONPATH = $repositoryRoot
    $arguments = @('verify_s2_risk.py')
    if ($TestedSha) { $arguments += @('--tested-sha', $TestedSha) }
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Sprint 2 release evaluation failed.' }
}
finally {
    $env:PYTHONPATH = $oldPythonPath
    Pop-Location
}
