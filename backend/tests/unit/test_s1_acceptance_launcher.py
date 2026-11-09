"""The native acceptance wrapper rejects unusable tools before starting proof."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
WRAPPER = Path(__file__).resolve().parents[3] / "scripts" / "verify-s1.ps1"


def node_tools() -> tuple[Path, Path] | None:
    """Use installed tools only; this unit check must not install npm or Node."""
    node = os.environ.get("FINEX_TEST_NODE") or shutil.which("node")
    npm = os.environ.get("FINEX_TEST_NPM_CLI")
    if node is None:
        return None
    if npm is None:
        npm_command = shutil.which("npm")
        if npm_command is None:
            return None
        npm_path = Path(npm_command)
        candidates = (
            npm_path.resolve(),
            npm_path.parent / "node_modules/npm/bin/npm-cli.js",
        )
        npm = next((str(path) for path in candidates if path.name == "npm-cli.js"), None)
    if npm is None or not Path(node).is_file() or not Path(npm).is_file():
        return None
    return Path(node), Path(npm)


def ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def isolated_wrapper(tmp_path: Path) -> Path:
    """An explicitly stubbed native proof isolates the npm-launcher boundary."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    wrapper = scripts / WRAPPER.name
    shutil.copyfile(WRAPPER, wrapper)
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "verify_s1_application.py").write_text(
        "import argparse, json\n"
        "from pathlib import Path\n"
        "p = argparse.ArgumentParser()\n"
        "for name in ('report', 'corpus', 'tested-sha', 'tested-tree', 'format'):\n"
        "    p.add_argument('--' + name)\n"
        "a = p.parse_args()\n"
        "Path(a.report).write_text(json.dumps({'success': True, 'unit_stub': True}))\n"
        "Path(a.corpus).write_text(json.dumps({'unit_stub': True}))\n",
        encoding="utf-8",
    )
    (tmp_path / "frontend-react").mkdir()
    return wrapper


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable on this test host")
@pytest.mark.parametrize("native_fails", [False, True])
def test_absent_process_options_are_absent_after_success_or_failure(
    tmp_path: Path, native_fails: bool
) -> None:
    """A null-to-empty restore must not contaminate a subsequent client command."""
    wrapper = isolated_wrapper(tmp_path)
    if native_fails:
        (tmp_path / "backend/verify_s1_application.py").write_text(
            "raise SystemExit(7)\n", encoding="utf-8"
        )
    command = (
        "$names = @('PYTHONPATH','FINEX_LOCAL_S1_CORPUS',"
        "'FINEX_REQUIRE_LOCAL_S1_CORPUS','CI'); "
        "foreach ($name in $names) { Remove-Item -LiteralPath ('Env:' + $name) "
        "-ErrorAction SilentlyContinue }; "
        "function git { $global:LASTEXITCODE = 0; '" + "1" * 40 + "' }; "
        "$failed = $false; "
        f"try {{ & {ps_literal(str(wrapper))} -Component Backend "
        f"-Python {ps_literal(sys.executable)} }} catch {{ $failed = $true }}; "
        f"if ($failed -ne ${str(native_fails).lower()}) {{ "
        "throw 'Native-stub outcome did not match the control.' }; "
        "foreach ($name in $names) { if (Test-Path -LiteralPath ('Env:' + $name)) { "
        "throw 'A previously absent process option was left present.' } }; "
        "$global:LASTEXITCODE = 0; exit 0"
    )
    result = subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        cwd=tmp_path,
    )
    assert result.returncode == 0, "Absent process options must remain absent on both outcomes."


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable on this test host")
@pytest.mark.parametrize("native_fails", [False, True])
def test_present_process_options_keep_exact_values_after_success_or_failure(
    tmp_path: Path, native_fails: bool
) -> None:
    """Explicit empty and nonempty options are preserved, not treated as absent."""
    wrapper = isolated_wrapper(tmp_path)
    if native_fails:
        (tmp_path / "backend/verify_s1_application.py").write_text(
            "raise SystemExit(7)\n", encoding="utf-8"
        )
    command = (
        "$seed = @{ PYTHONPATH = 'original-unit-import-path'; "
        "FINEX_LOCAL_S1_CORPUS = 'original-unit-corpus.json'; "
        "FINEX_REQUIRE_LOCAL_S1_CORPUS = '0'; CI = '' }; "
        "$before = @{}; $present = @{}; "
        "foreach ($name in $seed.Keys) { "
        "[Environment]::SetEnvironmentVariable($name, $seed[$name], 'Process'); "
        "$before[$name] = [Environment]::GetEnvironmentVariable($name, 'Process'); "
        "$present[$name] = Test-Path -LiteralPath ('Env:' + $name) }; "
        "function git { $global:LASTEXITCODE = 0; '" + "1" * 40 + "' }; "
        "$failed = $false; "
        f"try {{ & {ps_literal(str(wrapper))} -Component Backend "
        f"-Python {ps_literal(sys.executable)} }} catch {{ $failed = $true }}; "
        f"if ($failed -ne ${str(native_fails).lower()}) {{ "
        "throw 'Native-stub outcome did not match the control.' }; "
        "foreach ($name in $before.Keys) { "
        "if ((Test-Path -LiteralPath ('Env:' + $name)) -ne $present[$name] -or "
        "[Environment]::GetEnvironmentVariable($name, 'Process') -cne $before[$name]) { "
        "throw 'An explicit process option was not restored exactly.' } }; "
        "$global:LASTEXITCODE = 0; exit 0"
    )
    result = subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        cwd=tmp_path,
    )
    assert result.returncode == 0, "Explicit process options must retain their exact values."


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable on this test host")
def test_node_override_alone_is_not_silently_ignored(tmp_path: Path) -> None:
    wrapper = isolated_wrapper(tmp_path)
    command = (
        "function git { $global:LASTEXITCODE = 0; '" + "1" * 40 + "' }; "
        f"& {ps_literal(str(wrapper))} -Python {ps_literal(sys.executable)} "
        f"-Node {ps_literal(sys.executable)}"
    )
    result = subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode != 0
    assert "-Node requires -NpmCli" in result.stdout + result.stderr
    assert "technical checks passed" not in result.stdout


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable on this test host")
@pytest.mark.parametrize("relative_tools", ["none", "python", "node_and_npm"])
def test_selected_node_runs_npm_lifecycle_and_restores_path(
    tmp_path: Path, relative_tools: str
) -> None:
    installed = node_tools()
    if installed is None:
        pytest.skip("An existing Node/npm CLI pair is unavailable on this test host")
    node, npm = installed
    wrapper = isolated_wrapper(tmp_path)
    frontend = tmp_path / "frontend-react"
    # This is a genuine npm lifecycle child, not the native/API acceptance proof.
    script = (
        "const fs=require('fs');"
        "fs.writeFileSync('selected-node.json',JSON.stringify({execPath:process.execPath}));"
    )
    (frontend / "package.json").write_text(
        json.dumps({"name": "finex-launcher-unit", "scripts": {"test": f'node -e "{script}" --'}}),
        encoding="utf-8",
    )
    misleading = tmp_path / "wrong-node"
    misleading.mkdir()
    if os.name == "nt":
        (misleading / "node.cmd").write_text("@exit /b 86\n", encoding="utf-8")
    else:
        fake_node = misleading / "node"
        fake_node.write_text("#!/bin/sh\nexit 86\n", encoding="utf-8")
        fake_node.chmod(0o700)
    python_argument = (
        os.path.relpath(sys.executable, tmp_path) if relative_tools == "python" else sys.executable
    )
    node_argument = (
        os.path.relpath(node, tmp_path) if relative_tools == "node_and_npm" else str(node)
    )
    npm_argument = os.path.relpath(npm, tmp_path) if relative_tools == "node_and_npm" else str(npm)
    command = (
        f"$env:PATH = {ps_literal(str(misleading))} + [IO.Path]::PathSeparator + $env:PATH; "
        "$before = $env:PATH; "
        "function git { $global:LASTEXITCODE = 0; '" + "1" * 40 + "' }; "
        f"& {ps_literal(str(wrapper))} -Component React -Python {ps_literal(python_argument)} "
        f"-Node {ps_literal(node_argument)} -NpmCli {ps_literal(npm_argument)}; "
        "if ($env:PATH -ne $before) { throw 'Process PATH was not restored.' }"
    )
    result = subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        cwd=tmp_path,
    )
    assert result.returncode == 0, "The selected Node/npm lifecycle must finish successfully."
    marker = frontend / "selected-node.json"
    assert marker.is_file(), "The genuine npm lifecycle did not execute."
    actual = json.loads(marker.read_text(encoding="utf-8"))["execPath"]
    assert Path(actual).resolve() == node.resolve()


def invoke(*arguments: str) -> subprocess.CompletedProcess[str]:
    # Catch the real error in the test process, not PowerShell's terminal renderer.
    # Keep the full exception message and nonzero exit; do not weaken the guards.
    parameters = "; ".join(
        f"{ps_literal(name.lstrip('-'))} = {ps_literal(value)}"
        for name, value in zip(arguments[::2], arguments[1::2], strict=True)
    )
    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"$parameters = @{{ {parameters} }}; "
        f"try {{ & {ps_literal(str(WRAPPER))} @parameters }} "
        "catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }; exit 0"
    )
    return subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable on this test host")
def test_preflight_error_is_an_unformatted_exception_message(tmp_path: Path) -> None:
    """Diagnostic assertions must not depend on terminal colors or line wrapping."""
    result = invoke("-Python", str(tmp_path / "missing-python.exe"))
    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr.strip() == (
        "Bootstrap Backend first, or supply -Python with an existing venv interpreter."
    )


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable on this test host")
def test_missing_python_fails_before_git_or_native_proof(tmp_path: Path) -> None:
    result = invoke("-Python", str(tmp_path / "missing-python.exe"))
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "existing venv interpreter" in output
    assert "Cannot identify" not in output
    assert "technical checks passed" not in output


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable on this test host")
def test_npm_override_requires_explicit_existing_node_before_proof(tmp_path: Path) -> None:
    result = invoke("-Python", sys.executable, "-NpmCli", str(tmp_path / "missing-npm.js"))
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "explicit -Node" in output
    assert "Cannot identify" not in output
    assert "technical checks passed" not in output


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable on this test host")
def test_component_typo_cannot_silently_skip_client_validation() -> None:
    result = invoke("-Python", sys.executable, "-Component", "Everything")
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "ValidateSet" in output or "does not belong" in output
    assert "technical checks passed" not in output
