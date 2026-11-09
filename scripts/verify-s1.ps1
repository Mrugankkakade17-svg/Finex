[CmdletBinding()]
param(
    [ValidateSet('Backend', 'React', 'Flutter', 'All')][string]$Component = 'Backend',
    [string]$Python,
    [string]$Node,
    [string]$NpmCli,
    [string]$Flutter
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $repositoryRoot 'backend/.venv/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Bootstrap Backend first, or supply -Python with an existing venv interpreter.'
}
$Python = (Resolve-Path -LiteralPath $Python).ProviderPath
if ($Node -and -not $NpmCli) {
    throw '-Node requires -NpmCli; an explicit interpreter must not be silently ignored.'
}
if ($NpmCli -and (-not $Node -or -not (Test-Path -LiteralPath $NpmCli -PathType Leaf))) {
    throw '-NpmCli requires an existing npm CLI file and an explicit -Node interpreter.'
}
if ($Component -in @('React', 'All')) {
    if ($NpmCli) {
        if (-not (Test-Path -LiteralPath $Node -PathType Leaf)) {
            throw 'The selected Node interpreter is missing.'
        }
        # Resolve relative overrides while still in the caller's directory.
        $Node = (Resolve-Path -LiteralPath $Node).ProviderPath
        $NpmCli = (Resolve-Path -LiteralPath $NpmCli).ProviderPath
    } elseif (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw 'Bootstrap React first; npm is missing.'
    }
}
if ($Component -in @('Flutter', 'All')) {
    if (-not $Flutter) { $Flutter = (Get-Command flutter -ErrorAction Stop).Source }
    if (-not (Test-Path -LiteralPath $Flutter -PathType Leaf)) {
        throw 'Bootstrap Flutter first; the selected Flutter executable is missing.'
    }
    $Flutter = (Resolve-Path -LiteralPath $Flutter).ProviderPath
}

function RepositoryGit([string[]]$Arguments) {
    $value = & git -c "safe.directory=$repositoryRoot" -C $repositoryRoot @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Cannot identify the checked-out repository safely.' }
    return ($value -join "`n").Trim()
}

$testedSha = RepositoryGit @('rev-parse', 'HEAD')
$testedTree = RepositoryGit @('rev-parse', 'HEAD^{tree}')
if ($testedSha -notmatch '^[a-f0-9]{40}$' -or $testedTree -notmatch '^[a-f0-9]{40}$') {
    throw 'Use an exact, identifiable Git checkout; a supplied label is not provenance.'
}
# This directory holds sanitized proof only. The Python harness owns a different
# internally created temporary database, never a developer's configured database.
$proofDirectory = Join-Path ([IO.Path]::GetTempPath()) ('finex-s1-proof-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $proofDirectory
$reportPath = Join-Path $proofDirectory 's1-owned-proof.json'
$corpusPath = Join-Path $proofDirectory 's1-owned-corpus.json'
$names = @('PYTHONPATH', 'FINEX_LOCAL_S1_CORPUS', 'FINEX_REQUIRE_LOCAL_S1_CORPUS', 'CI', 'PATH')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    if ($Node -and $Component -in @('React', 'All')) {
        # npm's lifecycle shims resolve `node` from PATH, not npm's process.execPath.
        # Keep both the CLI and its children on the selected existing interpreter.
        $selectedNodeDirectory = Split-Path -Parent ([IO.Path]::GetFullPath($Node))
        $env:PATH = $selectedNodeDirectory + [IO.Path]::PathSeparator + $previous['PATH']
    }
    $env:PYTHONPATH = $repositoryRoot
    Push-Location (Join-Path $repositoryRoot 'backend')
    try {
        & $Python 'verify_s1_application.py' '--report' $reportPath '--corpus' $corpusPath '--tested-sha' $testedSha '--tested-tree' $testedTree '--format' 'text'
        if ($LASTEXITCODE -ne 0) { throw 'Owned S1 native proof failed; no client or release acceptance is claimed.' }
    } finally { Pop-Location }
    if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf) -or -not (Test-Path -LiteralPath $corpusPath -PathType Leaf)) {
        throw 'The successful verifier did not produce both required safe artifacts.'
    }
    $proof = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    if ($proof.success -ne $true) { throw 'The native report did not confirm every required check.' }
    $env:FINEX_LOCAL_S1_CORPUS = $corpusPath
    $env:FINEX_REQUIRE_LOCAL_S1_CORPUS = '1'
    $env:CI = 'true'
    if ($Component -in @('React', 'All')) {
        Push-Location (Join-Path $repositoryRoot 'frontend-react')
        try {
            $testArgs = @('test', '--', '--watchAll=false', '--runInBand', '--no-cache', '--runTestsByPath', 'src/services/localS1ContractParity.test.ts')
            if ($NpmCli) { & $Node $NpmCli @testArgs } else { & npm @testArgs }
            if ($LASTEXITCODE -ne 0) { throw 'React native-corpus parity failed.' }
        } finally { Pop-Location }
    }
    if ($Component -in @('Flutter', 'All')) {
        Push-Location (Join-Path $repositoryRoot 'frontend_flutter')
        try {
            & $Flutter test --no-pub 'test/local_contract_parity_test.dart'
            if ($LASTEXITCODE -ne 0) { throw 'Flutter native-corpus parity failed.' }
        } finally { Pop-Location }
    }
    Write-Output "S1 selected technical checks passed: $Component. Sanitized evidence: $proofDirectory"
    Write-Output 'Run applicable full suites/builds and independent review before release acceptance. This is not human UAT, browser E2E, a fresh-laptop or native-device certificate.'
} finally {
    foreach ($name in $names) {
        if ($null -eq $previous[$name]) {
            # Some installed runtimes turn a null .NET value into a present empty
            # option. Restore absence explicitly so later commands see no corpus.
            Remove-Item -LiteralPath ('Env:' + $name) -ErrorAction SilentlyContinue
        } else {
            [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
        }
    }
}
