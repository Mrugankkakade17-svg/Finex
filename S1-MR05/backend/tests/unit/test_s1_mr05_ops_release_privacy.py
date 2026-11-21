"""Unit & Contract tests for S1-MR05: Ops, release sign-offs, privacy with admin role.

AUTHORITATIVE ACCEPTANCE CRITERIA:
- Task ID: S1-MR05 (Issue #29)
- app/routers/ops_hardening.py, release_handover.py, privacy.py secured behind principal
- Non-admin toggle returns 403 Forbidden
- Admin role successfully toggles ops flags and submits UAT sign-offs
- Unauthenticated requests to all three routers rejected with HTTP 401 Unauthorized
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token
from app.auth.principal import Principal, require_admin_role
from app.main import app

client = TestClient(app)


def _admin_headers() -> dict[str, str]:
    token = create_access_token(
        data={"sub": "admin@finex.test", "user_id": 999, "roles": ["admin"]}
    )
    return {"Authorization": f"Bearer {token}"}


def _user_headers() -> dict[str, str]:
    token = create_access_token(data={"sub": "user@finex.test", "user_id": 100, "roles": ["user"]})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Direct Dependency Unit Tests for require_admin_role
# ---------------------------------------------------------------------------
class TestRequireAdminRoleDependency:
    """Test require_admin_role dependency directly."""

    @pytest.mark.asyncio
    async def test_admin_principal_passes(self):
        admin = Principal(user_id="adm-1", is_synthetic=False, roles=["admin", "user"])
        result = await require_admin_role(admin)
        assert result.user_id == "adm-1"
        assert "admin" in result.roles

    @pytest.mark.asyncio
    async def test_non_admin_principal_raises_403(self):
        non_admin = Principal(user_id="usr-1", is_synthetic=False, roles=["user"])
        with pytest.raises(Exception) as exc_info:
            await require_admin_role(non_admin)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin role required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_synthetic_learner_raises_403(self):
        learner = Principal(user_id="learner-a", is_synthetic=True, roles=["user", "learner"])
        with pytest.raises(Exception) as exc_info:
            await require_admin_role(learner)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin role required" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 2. Ops Hardening Router Authorization & Acceptance Criteria Tests
# ---------------------------------------------------------------------------
class TestOpsHardeningAuthorization:
    """Validate /api/v1/ops endpoints under authentication and admin role enforcement."""

    def test_ops_observability_unauthenticated_returns_401(self):
        resp = client.get("/api/v1/ops/observability")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_ops_observability_authenticated_user_returns_200(self):
        resp = client.get("/api/v1/ops/observability", headers=_user_headers())
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["healthy"] is True
        assert "active_feature_flags" in data["data"]

    def test_ops_flags_unauthenticated_returns_401(self):
        resp = client.get("/api/v1/ops/flags")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_ops_flags_authenticated_user_returns_200(self):
        resp = client.get("/api/v1/ops/flags", headers=_user_headers())
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert len(data["data"]) >= 3

    def test_ops_flags_toggle_unauthenticated_returns_401(self):
        resp = client.post(
            "/api/v1/ops/flags/FEATURE_AI_ASSISTANT/toggle",
            params={"enabled": "false"},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_ops_flags_toggle_non_admin_returns_403(self):
        """Authoritative acceptance criteria: Non-admin toggle returns 403."""
        resp = client.post(
            "/api/v1/ops/flags/FEATURE_AI_ASSISTANT/toggle",
            params={"enabled": "false"},
            headers=_user_headers(),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin role required" in resp.json().get("detail", "")

    def test_ops_flags_toggle_admin_succeeds(self):
        """Admin can toggle flags successfully."""
        # Toggle to False
        resp = client.post(
            "/api/v1/ops/flags/FEATURE_AI_ASSISTANT/toggle",
            params={"enabled": "false"},
            headers=_admin_headers(),
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["enabled"] is False

        # Reset back to True
        resp = client.post(
            "/api/v1/ops/flags/FEATURE_AI_ASSISTANT/toggle",
            params={"enabled": "true"},
            headers=_admin_headers(),
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["data"]["enabled"] is True

    def test_ops_flags_toggle_nonexistent_flag_returns_404(self):
        resp = client.post(
            "/api/v1/ops/flags/FEATURE_DOES_NOT_EXIST/toggle",
            params={"enabled": "true"},
            headers=_admin_headers(),
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_ops_preflight_unauthenticated_returns_401(self):
        resp = client.get("/api/v1/ops/preflight")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_ops_preflight_authenticated_user_returns_200(self):
        resp = client.get("/api/v1/ops/preflight", headers=_user_headers())
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["data"]["ready_for_promotion"] is True


# ---------------------------------------------------------------------------
# 3. Release Handover Router Authorization Tests
# ---------------------------------------------------------------------------
class TestReleaseHandoverAuthorization:
    """Validate /api/v1/release endpoints under authentication and admin role enforcement."""

    def test_release_manifest_unauthenticated_returns_401(self):
        resp = client.get("/api/v1/release/manifest")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_release_manifest_authenticated_user_returns_200(self):
        resp = client.get("/api/v1/release/manifest", headers=_user_headers())
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["version"] == "1.0.0"
        assert resp.json()["status"] == "GA_READY"

    def test_release_uat_signoffs_list_unauthenticated_returns_401(self):
        resp = client.get("/api/v1/release/uat-signoffs")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_release_uat_signoffs_list_authenticated_returns_200(self):
        resp = client.get("/api/v1/release/uat-signoffs", headers=_user_headers())
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.json(), list)

    def test_submit_uat_signoff_unauthenticated_returns_401(self):
        payload = {
            "stakeholder_name": "Test Signer",
            "role": "QA Lead",
            "decision": "APPROVED",
            "comments": "Sprint signoff verified",
            "checklist_verified": True,
        }
        resp = client.post("/api/v1/release/uat-signoffs", json=payload)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_submit_uat_signoff_non_admin_returns_403(self):
        """Non-admin cannot submit UAT sign-off."""
        payload = {
            "stakeholder_name": "Unauthorized User",
            "role": "Junior Tester",
            "decision": "APPROVED",
            "comments": "Attempting signoff without admin rights",
            "checklist_verified": True,
        }
        resp = client.post(
            "/api/v1/release/uat-signoffs",
            json=payload,
            headers=_user_headers(),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert "Admin role required" in resp.json().get("detail", "")

    def test_submit_uat_signoff_admin_succeeds(self):
        """Admin role successfully submits UAT sign-off."""
        payload = {
            "stakeholder_name": "Release Admin",
            "role": "Release Engineering Lead",
            "decision": "APPROVED",
            "comments": "Authoritative S1-MR05 verification signoff",
            "checklist_verified": True,
        }
        resp = client.post(
            "/api/v1/release/uat-signoffs",
            json=payload,
            headers=_admin_headers(),
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["stakeholder_name"] == "Release Admin"
        assert data["decision"] == "APPROVED"
        assert data["verified"] is True

    def test_release_dr_drill_unauthenticated_returns_401(self):
        resp = client.get("/api/v1/release/dr-drill")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_release_dr_drill_authenticated_user_returns_200(self):
        resp = client.get("/api/v1/release/dr-drill", headers=_user_headers())
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["result"] == "SUCCESS"

    def test_release_handover_unauthenticated_returns_401(self):
        resp = client.get("/api/v1/release/handover")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_release_handover_authenticated_user_returns_200(self):
        resp = client.get("/api/v1/release/handover", headers=_user_headers())
        assert resp.status_code == status.HTTP_200_OK
        assert "runbook_guides" in resp.json()


# ---------------------------------------------------------------------------
# 4. Privacy Router Authorization Tests
# ---------------------------------------------------------------------------
class TestPrivacyAuthorization:
    """Validate /api/v1/privacy endpoints under authentication."""

    def test_privacy_consent_unauthenticated_returns_401(self):
        resp = client.get("/api/v1/privacy/consent")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_privacy_consent_authenticated_user_returns_200(self):
        resp = client.get("/api/v1/privacy/consent", headers=_user_headers())
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["current_consent_version"] == "v1.0"

    def test_privacy_action_unauthenticated_returns_401(self):
        resp = client.post(
            "/api/v1/privacy/action",
            json={"action": "EXPORT", "confirm_explicit": True},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_privacy_action_missing_explicit_confirmation_returns_400(self):
        resp = client.post(
            "/api/v1/privacy/action",
            json={"action": "EXPORT", "confirm_explicit": False},
            headers=_user_headers(),
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_privacy_action_export_authenticated_returns_200(self):
        resp = client.post(
            "/api/v1/privacy/action",
            json={"action": "EXPORT", "confirm_explicit": True},
            headers=_user_headers(),
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["action"] == "EXPORT"
        assert data["data"]["status"] == "COMPLETED"
        assert "download_url" in data["data"]

    def test_privacy_action_revoke_consent_authenticated_returns_200(self):
        resp = client.post(
            "/api/v1/privacy/action",
            json={"action": "REVOKE_CONSENT", "confirm_explicit": True},
            headers=_user_headers(),
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["action"] == "REVOKE_CONSENT"
