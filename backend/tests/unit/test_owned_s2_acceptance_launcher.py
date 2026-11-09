"""Launcher-only unit seams; fake reports below are never native acceptance proof."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.test_s1_acceptance_launcher import ps_literal

POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
WRAPPER = Path(__file__).resolve().parents[3] / "scripts/verify-owned-s2.ps1"
OPTIONS = (
    "PYTHONPATH",
    "FINEX_LOCAL_S1_CORPUS",
    "FINEX_REQUIRE_LOCAL_S1_CORPUS",
    "FINEX_LOCAL_S2_RISK_CORPUS",
    "FINEX_LOCAL_S2_RISK_REPORT",
    "FINEX_LOCAL_S2_PORTFOLIO_CORPUS",
    "FINEX_LOCAL_S2_PORTFOLIO_REPORT",
    "FINEX_REQUIRE_LOCAL_S2_CORPUS",
    "CI",
    "PATH",
)
SHA = "1" * 40
TREE = "2" * 40


def invoke(command: str, *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        cwd=cwd,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable on this unit-test host")
def test_missing_python_fails_before_native_execution(tmp_path: Path) -> None:
    command = (
        "$ErrorActionPreference='Stop'; "
        f"try {{ & {ps_literal(str(WRAPPER))} -Python "
        f"{ps_literal(str(tmp_path / 'missing-python.exe'))} }} "
        "catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
    )
    result = invoke(command)
    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr.strip() == (
        "Bootstrap Backend first, or supply -Python with an existing venv interpreter."
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable on this unit-test host")
def test_explicit_node_is_not_silently_ignored_before_proof() -> None:
    result = invoke(
        f"try {{ & {ps_literal(str(WRAPPER))} -Python {ps_literal(sys.executable)} "
        f"-Node {ps_literal(sys.executable)} }} "
        "catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
    )
    assert result.returncode != 0
    assert "-Node requires -NpmCli" in result.stderr


def isolated_launcher(tmp_path: Path, fault: str) -> Path:
    """Copy only the launcher; isolated Python stubs test order and fail-closed handling."""
    scripts = tmp_path / "scripts"
    backend = tmp_path / "backend"
    scripts.mkdir()
    backend.mkdir()
    wrapper = scripts / WRAPPER.name
    shutil.copyfile(WRAPPER, wrapper)
    stub = (
        "import argparse, hashlib, json\n"
        "from pathlib import Path\n"
        "p=argparse.ArgumentParser()\n"
        "for n in ('report','corpus','tested-sha','tested-tree','format'): p.add_argument('--'+n)\n"
        "a=p.parse_args(); kind=Path(__file__).name\n"
        "marker=Path(__file__).parent/'unit-only-order.jsonl'\n"
        "with marker.open('a', encoding='utf-8') as f: f.write(json.dumps(kind)+'\\n')\n"
        "risk='saved_risk' in kind; portfolio='manual_portfolio' in kind\n"
        "schema=('finex.local_s2.saved_risk.acceptance.v1' if risk else "
        "'finex.local_s2.manual_portfolio.acceptance.v1' if portfolio else "
        "'finex.local_s1.acceptance.v1')\n"
        "corpus={'provenance':{'kind':'native_tcp_capture','tested_commit':a.tested_sha,"
        "'tested_tree':a.tested_tree}}\n"
        "data=(json.dumps(corpus, indent=2, ensure_ascii=False, allow_nan=False)+'\\n')"
        ".encode('utf-8')\n"
        "report={'schema_version':schema,'success':True,'mode':'owned_native_tcp',"
        "'tested_commit':a.tested_sha,'tested_tree':a.tested_tree,'working_tree_dirty':False,"
        "'tracked_dirty':False,'failures':[],"
        "'native_process':{'child_reaped':True,'temporary_directory_removed':True},"
        "'corpus_sha256':hashlib.sha256(data).hexdigest()}\n"
        "if not (risk or portfolio): report.pop('corpus_sha256')\n"
        f"fault={fault!r}\n"
        "if portfolio and fault=='native_failure': raise SystemExit(7)\n"
        "if portfolio and fault=='failed_report': report['success']=False\n"
        "if portfolio and fault=='string_success': report['success']='true'\n"
        "if portfolio and fault=='wrong_mode': report['mode']='unit_fixture'\n"
        "if portfolio and fault=='dirty_checkout': report['working_tree_dirty']=True\n"
        "if portfolio and fault=='failed_checks': report['failures']=[{'code':'unit-only'}]\n"
        "if portfolio and fault=='unclean': report['native_process']['child_reaped']=False\n"
        "if portfolio and fault=='missing_cleanup': "
        "report['native_process'].pop('temporary_directory_removed')\n"
        "if portfolio and fault=='wrong_sha': report['tested_commit']='3'*40\n"
        "if portfolio and fault=='wrong_corpus_sha': "
        "corpus['provenance']['tested_commit']='3'*40; "
        "data=(json.dumps(corpus)+'\\n').encode('utf-8'); "
        "report['corpus_sha256']=hashlib.sha256(data).hexdigest()\n"
        "if portfolio and fault=='wrong_tree': corpus['provenance']['tested_tree']='3'*40; "
        "data=(json.dumps(corpus)+'\\n').encode('utf-8'); "
        "report['corpus_sha256']=hashlib.sha256(data).hexdigest()\n"
        "if portfolio and fault=='wrong_digest': report['corpus_sha256']='0'*64\n"
        "if not(portfolio and fault=='missing_corpus'): Path(a.corpus).write_bytes(data)\n"
        "if portfolio and fault=='malformed_report': "
        "Path(a.report).write_text('{unit-secret-sentinel-not-a-real-token', encoding='utf-8')\n"
        "else: Path(a.report).write_text(json.dumps(report), encoding='utf-8')\n"
    )
    for name in (
        "verify_s1_application.py",
        "verify_s2_saved_risk.py",
        "verify_s2_manual_portfolio.py",
    ):
        (backend / name).write_text(stub, encoding="utf-8")
    # This mock models the validator process boundary only. Its documents are
    # intentionally incomplete unit seams, never evidence of native acceptance.
    guard_stub = (
        "import argparse, json\n"
        "from pathlib import Path\n"
        "p=argparse.ArgumentParser()\n"
        "for n in ('risk-report','risk-corpus','portfolio-report','portfolio-corpus',"
        "'tested-sha','tested-tree'): p.add_argument('--'+n, required=True)\n"
        "a=p.parse_args()\n"
        "marker=Path(__file__).parent/'unit-only-order.jsonl'\n"
        "with marker.open('a', encoding='utf-8') as f: "
        "f.write(json.dumps(Path(__file__).name)+'\\n')\n"
        f"assert a.tested_sha=={SHA!r} and a.tested_tree=={TREE!r}\n"
        "for n in ('risk_report','risk_corpus','portfolio_report','portfolio_corpus'): "
        "assert Path(getattr(a,n)).is_file()\n"
        f"if {fault!r}=='passive_guard_failure': raise SystemExit(9)\n"
    )
    (backend / "verify_s2_evidence_pair.py").write_text(guard_stub, encoding="utf-8")
    return wrapper


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell unavailable on this unit-test host")
@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "native_failure",
        "failed_report",
        "string_success",
        "wrong_mode",
        "dirty_checkout",
        "failed_checks",
        "unclean",
        "missing_cleanup",
        "wrong_sha",
        "wrong_corpus_sha",
        "wrong_tree",
        "wrong_digest",
        "missing_corpus",
        "malformed_report",
        "passive_guard_failure",
    ],
)
@pytest.mark.parametrize("seeded", [False, True])
def test_all_native_slices_run_serially_fail_closed_and_restore_process_options(
    tmp_path: Path, fault: str, seeded: bool
) -> None:
    wrapper = isolated_launcher(tmp_path, fault)
    command = (
        "$ErrorActionPreference='Stop'; "
        f"$names=@({','.join(ps_literal(n) for n in OPTIONS)}); "
        "$before=@{}; $present=@{}; "
        "foreach ($n in $names) { "
        + (
            "if ($n -ne 'PATH') { $v=if($n -eq 'CI'){''}else{'unit-original-'+$n}; "
            "[Environment]::SetEnvironmentVariable($n, $v, 'Process') }; "
            if seeded
            else "if ($n -ne 'PATH') { Remove-Item -LiteralPath ('Env:'+$n) "
            "-ErrorAction SilentlyContinue }; "
        )
        + "$before[$n]=[Environment]::GetEnvironmentVariable($n,'Process'); "
        "$present[$n]=Test-Path -LiteralPath ('Env:'+$n) }; "
        "function git { $global:LASTEXITCODE=0; "
        f"if ($args -contains 'HEAD') {{ '{SHA}' }} "
        f"elseif ($args -contains 'HEAD^{{tree}}') {{ '{TREE}' }} }}; "
        "$failed=$false; "
        f"try {{ & {ps_literal(str(wrapper))} -Component Backend "
        f"-Python {ps_literal(sys.executable)} }} catch {{ $failed=$true; "
        "[Console]::Error.WriteLine('unit-observed-failure') }; "
        f"if ($failed -ne ${str(fault != 'none').lower()}) {{ throw 'Unit outcome mismatch' }}; "
        "foreach ($n in $names) { "
        "if ((Test-Path -LiteralPath ('Env:'+$n)) -ne $present[$n] -or "
        "[Environment]::GetEnvironmentVariable($n,'Process') -cne $before[$n]) { "
        "throw 'Unit process option restore mismatch' } }; exit 0"
    )
    result = invoke(command, cwd=tmp_path)
    assert result.returncode == 0, "Launcher unit order/failure/env controls must pass."
    assert "unit-secret-sentinel-not-a-real-token" not in result.stdout + result.stderr
    marker = tmp_path / "backend/unit-only-order.jsonl"
    assert marker.is_file(), "The actual launcher did not execute its native-driver commands."
    expected_order = [
        "verify_s1_application.py",
        "verify_s2_saved_risk.py",
        "verify_s2_manual_portfolio.py",
    ]
    if fault in {"none", "passive_guard_failure"}:
        expected_order.append("verify_s2_evidence_pair.py")
    assert [json.loads(line) for line in marker.read_text(encoding="utf-8").splitlines()] == (
        expected_order
    )
    assert ("S2 selected technical checks passed" in result.stdout) is (fault == "none")
