"""S3 documentation assertions, not provider/native/client acceptance."""

from pathlib import Path

import pytest

from tests.support.local_s3_client import LISTS, MARKET, application


def test_s3_openapi_documents_the_actual_five_key_error_envelope(tmp_path: Path) -> None:
    specification = application(tmp_path / "no-openapi-db.sqlite3").openapi()
    operation = specification["paths"][MARKET + "/instruments"]["get"]
    reference = operation["responses"]["401"]["content"]["application/json"]["schema"]["$ref"]
    schema = specification["components"]["schemas"][reference.rsplit("/", 1)[1]]
    assert set(schema["properties"]) == {"success", "message", "error_code", "error", "detail"}
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize(
    "method,path",
    [
        ("delete", LISTS + "/{watchlist_id}"),
        ("put", LISTS + "/{watchlist_id}/items/{instrument_id}"),
        ("delete", LISTS + "/{watchlist_id}/items/{instrument_id}"),
    ],
)
def test_s3_openapi_documents_optional_empty_only_mutation_body(
    tmp_path: Path, method: str, path: str
) -> None:
    specification = application(tmp_path / "no-body-doc-db.sqlite3").openapi()
    operation = specification["paths"][path][method]
    request_body = operation.get("requestBody")
    assert type(request_body) is dict
    assert request_body.get("required", False) is False
    schema = request_body["content"]["application/json"]["schema"]
    if "$ref" in schema:
        schema = specification["components"]["schemas"][schema["$ref"].rsplit("/", 1)[1]]
    assert schema["type"] == "object"
    assert schema["properties"] == {} and schema["additionalProperties"] is False
