"""Native launcher must not accidentally expose public synthetic personas."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
LAUNCHER = Path(__file__).resolve().parents[2] / "scripts" / "run-backend.ps1"


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable on this test host")
@pytest.mark.parametrize("address", ["0.0.0.0", "192.168.0.15", "example.com"])
def test_local_launcher_rejects_nonloopback_before_starting_python(address: str) -> None:
    result = subprocess.run(
        [
            str(POWERSHELL),
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(LAUNCHER),
            "-BindAddress",
            address,
        ],
        capture_output=True,
        text=True,
        timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "127.0.0.1" in output
    assert "localhost" in output
    assert "Backend virtual environment is missing" not in output


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is unavailable on this test host")
def test_launcher_dry_run_disables_forwarded_peer_trust_and_access_logs() -> None:
    result = subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-File", str(LAUNCHER), "-WhatIf"],
        capture_output=True,
        text=True,
        timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0
    assert "--no-access-log" in output
    assert "--no-proxy-headers" in output
    assert "127.0.0.1" in output
