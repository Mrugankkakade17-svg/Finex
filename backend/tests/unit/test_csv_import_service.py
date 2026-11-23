from contextlib import closing
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.principal import Principal, get_current_principal
from app.routers.spending import router as spending_router
from app.services import csv_import_service as service


def test_import_persists_only_to_authenticated_user_and_masks_description(tmp_path, monkeypatch):
    database = tmp_path / "spending.sqlite3"
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(local_db_path=str(database), app_persistence="sqlite"),
    )
    content = b"date,description,amount,category\n2026-11-01,STORE 12345678 #abc,12.50,Food\n"

    summary = service.import_spending_csv(content, "spending.csv", "user-a")

    assert summary.total_rows_imported == 1
    assert summary.quarantined_rows == 0
    assert summary.total_spend_amount == 12.5
    with closing(service.sqlite3.connect(database)) as connection:
        row = connection.execute(
            "SELECT user_id, description_masked FROM spending_transactions"
        ).fetchone()
    assert row == ("user-a", "STORE **** #***")
    service.import_spending_csv(content, "spending.csv", "user-b")
    with closing(service.sqlite3.connect(database)) as connection:
        owners = connection.execute(
            "SELECT user_id, COUNT(*) FROM spending_transactions GROUP BY user_id ORDER BY user_id"
        ).fetchall()
    assert owners == [("user-a", 1), ("user-b", 1)]


def test_formula_prefixes_are_escaped_in_text_columns():
    rows, quarantined = service._parse_rows(
        b"date,description,amount,category\n2026-11-01,=1+1,2,@cmd\n"
    )

    assert quarantined == 0
    assert rows[0]["description_masked"] == "'=1+1"
    assert rows[0]["category"] == "'@cmd"


def test_invalid_rows_are_quarantined_without_failing_valid_rows():
    rows, quarantined = service._parse_rows(
        b"date,description,amount,category\n2026-11-01,Valid,1.25,Food\nnot-a-date,Bad,=2+2,Food\n"
    )

    assert len(rows) == 1
    assert quarantined == 1


@pytest.mark.parametrize("content", [b"", b"date,description,amount\n"])
def test_empty_or_missing_required_columns_are_rejected(content):
    with pytest.raises(service.CSVImportError):
        service._parse_rows(content)


def test_upload_size_limit_is_enforced():
    with pytest.raises(service.CSVImportError, match="5 MiB"):
        service._parse_rows(b"x" * (service.MAX_UPLOAD_BYTES + 1))


def test_row_limit_is_enforced():
    content = b"date,description,amount,category\n" + b"2026-11-01,A,1,Food\n" * (
        service.MAX_ROWS + 1
    )
    with pytest.raises(service.CSVImportError, match="row limit"):
        service._parse_rows(content)


def test_field_size_limit_quarantines_oversized_row():
    description = "a" * (service.MAX_FIELD_CHARS + 1)
    rows, quarantined = service._parse_rows(
        f"date,description,amount,category\n2026-11-01,{description},1,Food\n".encode()
    )
    assert rows == []
    assert quarantined == 1


def test_import_endpoint_returns_finex_envelope_and_requires_identity(tmp_path, monkeypatch):
    database = tmp_path / "endpoint.sqlite3"
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(local_db_path=str(database), app_persistence="sqlite"),
    )
    application = FastAPI()
    application.include_router(spending_router)

    with TestClient(application) as client:
        unauthenticated = client.post(
            "/api/v1/spending/imports",
            files={"file": ("spending.csv", b"date,description,amount,category\n")},
        )
        assert unauthenticated.status_code == 401

        application.dependency_overrides[get_current_principal] = lambda: Principal(
            user_id="user-a"
        )
        response = client.post(
            "/api/v1/spending/imports",
            files={
                "file": (
                    "spending.csv",
                    b"date,description,amount,category\n2026-11-01,Cafe,8.50,Food\n",
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Spending CSV imported"
    assert body["data"]["total_rows_imported"] == 1
    assert body["meta"]["correlationId"]
