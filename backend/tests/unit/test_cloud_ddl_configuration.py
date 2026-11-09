"""Legacy cloud utility must not embed credentials or need cloud SDK on import."""

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[3] / "scripts/run_ddl.py"


def utility():
    spec = importlib.util.spec_from_file_location("finex_ddl", PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missing_configuration_fails_without_connection(monkeypatch):
    for key in ("DATABRICKS_TOKEN", "DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_HTTP_PATH"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match="Missing local configuration"):
        utility().configuration()


def test_values_are_only_read_from_environment(monkeypatch):
    monkeypatch.setenv("DATABRICKS_TOKEN", "invalid-synthetic-test-value")
    monkeypatch.setenv("DATABRICKS_SERVER_HOSTNAME", "example.invalid")
    monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/synthetic")
    config = utility().configuration()
    assert config["server_hostname"] == "example.invalid"
    assert config["access_token"] == "invalid-synthetic-test-value"


def test_cloud_command_is_disabled_by_default(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["run_ddl.py"])
    assert utility().main() == 0
    assert "Cloud DDL disabled" in capsys.readouterr().out
