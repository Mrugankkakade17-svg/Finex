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
        # Resolve caller-relative overrides before changing working directories.
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

function RequireSafePair([string]$ReportPath, [string]$CorpusPath, [string]$Schema) {
    # Never print source documents or raw parser errors. This is a compatibility
    # preflight; the complete S2 pair is passively validated after all producers.
    try {
        if (-not (Test-Path -LiteralPath $ReportPath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $CorpusPath -PathType Leaf)) { throw 'missing' }
        $reportInfo = Get-Item -LiteralPath $ReportPath
        $corpusInfo = Get-Item -LiteralPath $CorpusPath
        if ($reportInfo.Length -gt 2097152 -or $corpusInfo.Length -gt 2097152 -or
            ($reportInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            ($corpusInfo.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'unsafe' }
        $proof = Get-Content -LiteralPath $ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $capture = Get-Content -LiteralPath $CorpusPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($proof.schema_version -cne $Schema -or
            $proof.success -isnot [bool] -or $proof.success -cne $true -or
            $proof.mode -cne 'owned_native_tcp' -or
            $proof.tested_commit -cne $testedSha -or $proof.tested_tree -cne $testedTree -or
            $proof.working_tree_dirty -isnot [bool] -or $proof.working_tree_dirty -cne $false -or
            $proof.tracked_dirty -isnot [bool] -or $proof.tracked_dirty -cne $false -or
            @($proof.failures).Count -ne 0 -or
            $proof.native_process.child_reaped -isnot [bool] -or
            $proof.native_process.child_reaped -cne $true -or
            $proof.native_process.temporary_directory_removed -isnot [bool] -or
            $proof.native_process.temporary_directory_removed -cne $true -or
            $capture.provenance.kind -cne 'native_tcp_capture' -or
            $capture.provenance.tested_commit -cne $testedSha -or
            $capture.provenance.tested_tree -cne $testedTree) { throw 'invalid' }
        # S1 has no corpus digest field; its existing contract remains unchanged.
        # Both S2 reports bind the exact exclusively written corpus file bytes.
        if ($Schema -cne 'finex.local_s1.acceptance.v1') {
            $digest = (Get-FileHash -LiteralPath $CorpusPath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($proof.corpus_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
                $proof.corpus_sha256 -cne $digest) { throw 'digest' }
        }
    } catch {
        throw 'Owned native artifacts are incomplete, altered or not from this clean checkout.'
    }
}

$testedSha = RepositoryGit @('rev-parse', 'HEAD')
$testedTree = RepositoryGit @('rev-parse', 'HEAD^{tree}')
if ($testedSha -cnotmatch '^[a-f0-9]{40}$' -or $testedTree -cnotmatch '^[a-f0-9]{40}$') {
    throw 'Use an exact, identifiable Git checkout; a supplied label is not provenance.'
}
if (RepositoryGit @('status', '--porcelain', '--untracked-files=normal')) {
    throw 'Commit the reviewed source before owned S2 acceptance; the checkout must be clean.'
}
# Proof is retained outside source. Each driver separately owns and cleans its
# internally created database; no developer-configured database is opened.
$proofDirectory = Join-Path ([IO.Path]::GetTempPath()) ('finex-s2-proof-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $proofDirectory
$slices = @(
    @{ Driver = 'verify_s1_application.py'; Prefix = 's1-owned'; Schema = 'finex.local_s1.acceptance.v1' },
    @{ Driver = 'verify_s2_saved_risk.py'; Prefix = 's2-saved-risk'; Schema = 'finex.local_s2.saved_risk.acceptance.v1' },
    @{ Driver = 'verify_s2_manual_portfolio.py'; Prefix = 's2-manual-portfolio'; Schema = 'finex.local_s2.manual_portfolio.acceptance.v1' }
)
$names = @(
    'PYTHONPATH', 'FINEX_LOCAL_S1_CORPUS', 'FINEX_REQUIRE_LOCAL_S1_CORPUS',
    'FINEX_LOCAL_S2_RISK_CORPUS', 'FINEX_LOCAL_S2_RISK_REPORT',
    'FINEX_LOCAL_S2_PORTFOLIO_CORPUS', 'FINEX_LOCAL_S2_PORTFOLIO_REPORT',
    'FINEX_REQUIRE_LOCAL_S2_CORPUS', 'CI', 'PATH'
)
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    if ($Node -and $Component -in @('React', 'All')) {
        $env:PATH = (Split-Path -Parent $Node) + [IO.Path]::PathSeparator + $previous['PATH']
    }
    $env:PYTHONPATH = $repositoryRoot
    foreach ($slice in $slices) {
        $reportPath = Join-Path $proofDirectory ($slice.Prefix + '-proof.json')
        $corpusPath = Join-Path $proofDirectory ($slice.Prefix + '-corpus.json')
        Push-Location (Join-Path $repositoryRoot 'backend')
        try {
            & $Python $slice.Driver '--report' $reportPath '--corpus' $corpusPath '--tested-sha' $testedSha '--tested-tree' $testedTree '--format' 'text'
            if ($LASTEXITCODE -ne 0) {
                throw 'Owned S1/S2 native proof failed; no full client or release acceptance is claimed.'
            }
        } finally { Pop-Location }
        RequireSafePair $reportPath $corpusPath $slice.Schema
    }
    # A producer exit zero and basic cleanup flags are not a complete S2 proof.
    # The read-only validator checks full schemas, ordered coverage, original
    # bytes, current source hashes and both pairs before any selected success.
    Push-Location (Join-Path $repositoryRoot 'backend')
    try {
        $pairArgs = @(
            'verify_s2_evidence_pair.py',
            '--risk-report', (Join-Path $proofDirectory 's2-saved-risk-proof.json'),
            '--risk-corpus', (Join-Path $proofDirectory 's2-saved-risk-corpus.json'),
            '--portfolio-report', (Join-Path $proofDirectory 's2-manual-portfolio-proof.json'),
            '--portfolio-corpus', (Join-Path $proofDirectory 's2-manual-portfolio-corpus.json'),
            '--tested-sha', $testedSha, '--tested-tree', $testedTree
        )
        & $Python @pairArgs
        if ($LASTEXITCODE -ne 0) {
            throw 'Complete current native S2 pair validation failed; no selected acceptance is claimed.'
        }
    } finally { Pop-Location }
    $env:FINEX_LOCAL_S1_CORPUS = Join-Path $proofDirectory 's1-owned-corpus.json'
    $env:FINEX_REQUIRE_LOCAL_S1_CORPUS = '1'
    $env:FINEX_LOCAL_S2_RISK_CORPUS = Join-Path $proofDirectory 's2-saved-risk-corpus.json'
    $env:FINEX_LOCAL_S2_RISK_REPORT = Join-Path $proofDirectory 's2-saved-risk-proof.json'
    $env:FINEX_LOCAL_S2_PORTFOLIO_CORPUS = Join-Path $proofDirectory 's2-manual-portfolio-corpus.json'
    $env:FINEX_LOCAL_S2_PORTFOLIO_REPORT = Join-Path $proofDirectory 's2-manual-portfolio-proof.json'
    $env:FINEX_REQUIRE_LOCAL_S2_CORPUS = '1'
    $env:CI = 'true'
    if ($Component -in @('React', 'All')) {
        Push-Location (Join-Path $repositoryRoot 'frontend-react')
        try {
            $testArgs = @('test', '--', '--watchAll=false', '--runInBand', '--no-cache', '--runTestsByPath', 'src/services/localS1ContractParity.test.ts', 'src/services/localS2NativeParity.test.ts')
            if ($NpmCli) { & $Node $NpmCli @testArgs } else { & npm @testArgs }
            if ($LASTEXITCODE -ne 0) { throw 'React mandatory native S1/S2 corpus parity failed.' }
        } finally { Pop-Location }
    }
    if ($Component -in @('Flutter', 'All')) {
        Push-Location (Join-Path $repositoryRoot 'frontend_flutter')
        try {
            & $Flutter test --no-pub 'test/local_contract_parity_test.dart' 'test/local_s2_corpus_loader_test.dart' 'test/local_s2_risk_contract_parity_test.dart' 'test/local_s2_portfolio_contract_parity_test.dart'
            if ($LASTEXITCODE -ne 0) { throw 'Flutter mandatory native S1/S2 corpus parity failed.' }
        } finally { Pop-Location }
    }
    if ((RepositoryGit @('rev-parse', 'HEAD')) -cne $testedSha -or
        (RepositoryGit @('rev-parse', 'HEAD^{tree}')) -cne $testedTree -or
        (RepositoryGit @('status', '--porcelain', '--untracked-files=normal'))) {
        throw 'Source changed during acceptance; the earlier reports do not certify this checkout.'
    }
    Write-Output "S2 selected technical checks passed: $Component. Sanitized evidence: $proofDirectory"
    Write-Output 'Run applicable full suites/builds, controlled client journeys and review before release acceptance. This is not human UAT, native-device, fresh-laptop or cloud acceptance.'
} finally {
    foreach ($name in $names) {
        if ($null -eq $previous[$name]) {
            Remove-Item -LiteralPath ('Env:' + $name) -ErrorAction SilentlyContinue
        } else {
            [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
        }
    }
}
