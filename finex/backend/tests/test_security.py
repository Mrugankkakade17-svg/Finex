from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.security import BearerTokenScheme, extract_token
from app.core.exceptions import AuthenticationException


def test_extract_token_success():
    token = extract_token("Bearer test-token-123")

    assert token == "test-token-123"


def test_extract_token_lowercase_bearer():
    token = extract_token("bearer test-token-456")

    assert token == "test-token-456"


def test_extract_token_missing_authorization():
    try:
        extract_token("")
        assert False
    except AuthenticationException as exc:
        assert exc.message == "Authorization header missing"


def test_extract_token_invalid_format():
    try:
        extract_token("InvalidToken")
        assert False
    except AuthenticationException as exc:
        assert exc.message == "Invalid authorization format"


def test_extract_token_invalid_scheme():
    try:
        extract_token("Basic abc123")
        assert False
    except AuthenticationException as exc:
        assert exc.message == "Invalid authorization format"


def test_extract_token_too_many_parts():
    try:
        extract_token("Bearer token extra")
        assert False
    except AuthenticationException as exc:
        assert exc.message == "Invalid authorization format"


def test_bearer_scheme_valid_token():
    app = FastAPI()
    security = BearerTokenScheme()

    @app.get("/protected")
    async def protected(
        credentials=Depends(security),
    ):
        return {"token": credentials.credentials}

    client = TestClient(app)

    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.json()["token"] == "valid-token"


def test_bearer_scheme_missing_header():
    app = FastAPI()
    security = BearerTokenScheme()

    @app.get("/protected")
    async def protected(
        credentials=Depends(security),
    ):
        return {"token": credentials.credentials}

    client = TestClient(app)

    response = client.get("/protected")

    assert response.status_code == 403


def test_bearer_scheme_empty_token():
    app = FastAPI()
    security = BearerTokenScheme()

    @app.get("/protected")
    async def protected(
        credentials=Depends(security),
    ):
        return {"token": credentials.credentials}

    client = TestClient(app)

    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer "},
    )

    assert response.status_code in (401, 403)
