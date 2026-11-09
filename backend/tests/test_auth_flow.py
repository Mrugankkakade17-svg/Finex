"""
End-to-end authentication flow test.

Register → Hash Password → Store User → Login → Verify Password →
Generate JWT → Call Protected API → Verify JWT → Return User →
Refresh Token → Logout
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_full_auth_flow():
    # 1. Register → Hash Password → Store User
    reg_response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Flow Test User",
            "email": "flowtest@finex.com",
            "password": "SecurePass@123",
        },
    )
    assert reg_response.status_code == 200
    reg_data = reg_response.json()

    assert "data" in reg_data
    assert "meta" in reg_data
    assert reg_data["meta"]["apiVersion"] == "v1"
    assert reg_data["meta"]["correlationId"]
    assert "access_token" in reg_data["data"]
    assert "refresh_token" in reg_data["data"]

    # 2. Login → Verify Password → Generate JWT
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "flowtest@finex.com",
            "password": "SecurePass@123",
        },
    )
    assert login_response.status_code == 200
    login_data = login_response.json()

    assert "data" in login_data
    assert "meta" in login_data
    assert login_data["meta"]["apiVersion"] == "v1"
    assert login_data["meta"]["correlationId"]

    access_token = login_data["data"]["access_token"]
    refresh_token = login_data["data"]["refresh_token"]

    # 3. Call Protected API → Verify JWT → Return User
    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert "data" in me_data
    assert "meta" in me_data
    assert me_data["meta"]["apiVersion"] == "v1"
    assert me_data["meta"]["correlationId"]
    assert me_data["data"]["sub"] == "flowtest@finex.com"

    # 4. Refresh Token
    refresh_response = client.post(f"/api/v1/auth/refresh?token={refresh_token}")
    assert refresh_response.status_code == 200
    refresh_data = refresh_response.json()

    assert "data" in refresh_data
    assert "meta" in refresh_data
    assert refresh_data["meta"]["apiVersion"] == "v1"
    assert refresh_data["meta"]["correlationId"]
    assert "access_token" in refresh_data["data"]

    new_token = refresh_data["data"]["access_token"]

    # 5. Use new token on protected route
    me_response2 = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert me_response2.status_code == 200

    # 6. Logout
    logout_response = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert logout_response.status_code == 200
    logout_data = logout_response.json()
    assert "data" in logout_data
    assert "meta" in logout_data
    assert logout_data["meta"]["apiVersion"] == "v1"
    assert logout_data["meta"]["correlationId"]
