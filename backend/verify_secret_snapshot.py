"""Free, redacted Gitleaks gate over the exact tracked Git snapshot, not history.

Ignored .env files and local runtimes are intentionally not uploaded or scanned
by CI. This gate cannot establish whether old history ever contained a secret.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile


def _scan(binary: Path, source: Path, report: Path) -> tuple[int, list[dict]]:
    result = subprocess.run(
        [
            str(binary.resolve()),
            "dir",
            str(source),
            "--redact=100",
            "--no-banner",
            "--ignore-gitleaks-allow",
            "--log-level",
            "fatal",
            "--report-format",
            "json",
            "--report-path",
            str(report),
        ],
        capture_output=True,
        check=False,
    )
    findings = json.loads(report.read_text(encoding="utf-8")) if report.exists() else []
    return result.returncode, findings


def verify(binary: Path, repository: Path) -> dict:
    """First prove detection with an invalid synthetic token; then scan HEAD."""
    head = subprocess.check_output(
        ["git", "-c", f"safe.directory={repository}", "-C", str(repository), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    with tempfile.TemporaryDirectory(prefix="finex-secret-gate-") as scratch:
        temporary = Path(scratch)
        probe = temporary / "probe"
        probe.mkdir()
        # This is a format-only, nonexistent credential, not a usable PAT.
        synthetic = "ghp_" + hashlib.sha256(b"FinEx nonexistent detector probe").hexdigest()[:36]
        (probe / "probe.txt").write_text(f"token={synthetic}\n", encoding="utf-8")
        red_code, red_findings = _scan(binary, probe, temporary / "probe-report.json")
        detection = red_code == 1 and len(red_findings) > 0
        redacted = synthetic not in json.dumps(red_findings)
        archive = temporary / "snapshot.zip"
        with archive.open("wb") as output:
            subprocess.run(
                [
                    "git",
                    "-c",
                    f"safe.directory={repository}",
                    "-C",
                    str(repository),
                    "archive",
                    "--format=zip",
                    "HEAD",
                ],
                stdout=output,
                check=True,
            )
        snapshot = temporary / "snapshot"
        snapshot.mkdir()
        with ZipFile(archive) as zipped:
            for member in zipped.namelist():
                if not (snapshot / member).resolve().is_relative_to(snapshot.resolve()):
                    raise ValueError("Unsafe archive member")
            zipped.extractall(snapshot)
        code, findings = _scan(binary, snapshot, temporary / "snapshot-report.json")
        clean = code == 0 and not findings
        return {
            "schema_version": "r0-secret-snapshot/v1",
            "status": "PASS" if detection and redacted and clean else "FAIL",
            "tested_commit_sha": head,
            "scope": "tracked_HEAD_snapshot_not_history_or_ignored_local_secrets",
            "synthetic_red_probe_detected": detection,
            "probe_report_redacted": redacted,
            "snapshot_clean": clean,
            "findings": [
                {"rule": row["RuleID"], "file": row["File"], "line": row["StartLine"]}
                for row in findings
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gitleaks", required=True, type=Path)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    report = verify(args.gitleaks, args.repository.resolve())
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
