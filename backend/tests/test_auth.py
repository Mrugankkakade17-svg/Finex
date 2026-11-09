from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# Authentication Tests


def test_register():
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Shivraj",
            "email": "shivraj_test@gmail.com",
            "password": "Password@123",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert "access_token" in body["data"]
    assert "refresh_token" in body["data"]
    assert body["meta"]["apiVersion"] == "v1"
    assert body["meta"]["correlationId"]
    assert response.headers["x-correlation-id"] == body["meta"]["correlationId"]


def test_duplicate_email():
    # Register first
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "User One",
            "email": "duplicate@gmail.com",
            "password": "Password@123",
        },
    )
    # Try same email again
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "User Two",
            "email": "duplicate@gmail.com",
            "password": "Password@456",
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "EMAIL_EXISTS"
    assert body["error"]["message"]
    assert body["error"]["fieldErrors"] == []
    assert body["error"]["correlationId"]
    assert response.headers["x-correlation-id"] == body["error"]["correlationId"]


def test_login_success():
    # Register
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Login User",
            "email": "loginuser@gmail.com",
            "password": "Password@123",
        },
    )
    # Login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "loginuser@gmail.com",
            "password": "Password@123",
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert "data" in body
    assert "meta" in body
    assert "access_token" in body["data"]
    assert body["meta"]["apiVersion"] == "v1"
    assert body["meta"]["correlationId"]
    assert response.headers["x-correlation-id"] == body["meta"]["correlationId"]


def test_wrong_password():
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "loginuser@gmail.com",
            "password": "WrongPassword",
        },
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "INVALID_CREDENTIALS"


def test_invalid_email():
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Test",
            "email": "not_an_email",
            "password": "Password@123",
        },
    )
    assert response.status_code == 422


def test_protected_route():
    # Register and get token
    reg_response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Protected User",
            "email": "protected@gmail.com",
            "password": "Password@123",
        },
    )
    token = reg_response.json()["data"]["access_token"]

    # Access /me with token
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()

    assert "data" in body
    assert "meta" in body
    assert body["meta"]["apiVersion"] == "v1"
    assert body["meta"]["correlationId"]
    assert response.headers["x-correlation-id"] == body["meta"]["correlationId"]
    assert body["data"]["sub"] == "protected@gmail.com"


def test_protected_route_no_token():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 403


def test_refresh_token():
    # Register and get refresh token
    reg_response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Refresh User",
            "email": "refresh@gmail.com",
            "password": "Password@123",
        },
    )
    refresh_token = reg_response.json()["data"]["refresh_token"]

    # Refresh
    response = client.post(f"/api/v1/auth/refresh?token={refresh_token}")
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body["data"]


def test_logout():
    # Register and get token
    reg_response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Logout User",
            "email": "logout@gmail.com",
            "password": "Password@123",
        },
    )
    token = reg_response.json()["data"]["access_token"]

    # Logout
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()

    assert "data" in body
    assert "meta" in body
    assert body["data"] is None
    assert body["meta"]["apiVersion"] == "v1"
    assert body["meta"]["correlationId"]
    assert response.headers["x-correlation-id"] == body["meta"]["correlationId"]
