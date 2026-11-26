"""
Comprehensive Security Regression Tests for Google OAuth (PR #126 / S1-LI02).

Verifies the elimination of caller-supplied identity bypass and unauthenticated
JWT decoding risks, ensuring cryptographic signature verification and robust
safeguards against account takeover.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwk, jwt

from app.auth.token_store import TokenRevocationStore
from app.config.settings import AppEnv, ConfigurationError, Settings, get_settings
from app.core.exceptions import BadRequestException, UnauthorizedException
from app.main import app
from app.ports.adapters.google_oauth_verifier import (
    google_jwks_client,
    google_oauth_verifier,
)
from app.repositories.postgres_user_repository import PostgresUserRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import GoogleAuthRequest
from app.services.google_auth_service import GoogleAuthService

client = TestClient(app)


def _generate_rsa_key_pair(kid: str = "security-test-kid"):
    """Generate an ephemeral RSA key pair and public JWK dict for cryptographic testing."""
    priv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = priv_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    priv_jwk = jwk.RSAKey(algorithm="RS256", key=priv_key)
    pub_dict = {k: v for k, v in priv_jwk.to_dict().items() if k in ("kty", "alg", "use", "n", "e")}
    pub_dict["kid"] = kid
    return priv_pem, pub_dict


def _create_signed_google_token(
    priv_pem: str,
    kid: str = "security-test-kid",
    email: str = "alice@example.com",
    email_verified: Any = True,
    exp: int | None = None,
    iss: str = "https://accounts.google.com",
    aud: str = "test-google-client-id",
    sub: str = "google-uid-12345",
    name: str = "Alice Security",
) -> str:
    claims: dict[str, Any] = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "email": email,
        "name": name,
        "exp": exp if exp is not None else (int(time.time()) + 3600),
    }
    if email_verified is not None:
        claims["email_verified"] = email_verified
    return jwt.encode(claims, priv_pem, algorithm="RS256", headers={"kid": kid})


@pytest.fixture(autouse=True)
def setup_security_test(monkeypatch):
    """Isolate test environment with fresh state and registered RSA test key."""
    fresh_repo = UserRepository()
    fresh_store = TokenRevocationStore()
    monkeypatch.setattr("app.services.auth_service.user_repository", fresh_repo)
    monkeypatch.setattr("app.services.auth_service.token_revocation_store", fresh_store)
    monkeypatch.setattr("app.auth.dependencies.token_revocation_store", fresh_store)
    monkeypatch.setattr("app.routers.users.user_repository", fresh_repo)

    # Configure test client ID and enable mock auth in test environment
    monkeypatch.setattr(get_settings(), "google_client_id", "test-google-client-id")
    monkeypatch.setattr(get_settings(), "allow_mock_google_auth", True)
    monkeypatch.setattr(get_settings(), "app_env", AppEnv.LOCAL)

    priv_pem, pub_dict = _generate_rsa_key_pair("security-test-kid")
    google_jwks_client.clear_overrides()
    google_jwks_client.add_key_override("security-test-kid", pub_dict)

    yield {
        "priv_pem": priv_pem,
        "pub_dict": pub_dict,
        "repo": fresh_repo,
    }

    google_jwks_client.clear_overrides()


# ─────────────────────────────────────────────────────────────────────────────
# Security Vector 1: Caller-Supplied Identity Bypass Rejection
# ─────────────────────────────────────────────────────────────────────────────


class TestCallerSuppliedIdentityBypassRejection:
    def test_post_callback_with_raw_email_only_returns_400(self):
        """Attacker sending victim's email without token must be rejected with 400."""
        resp = client.post(
            "/api/v1/auth/google/callback",
            json={"email": "victim@example.com"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["success"] is False
        assert data["error_code"] == "MISSING_GOOGLE_CREDENTIAL"

    def test_post_callback_with_raw_email_and_name_returns_400(self):
        """Attacker providing full synthetic identity without credential must fail."""
        resp = client.post(
            "/api/v1/auth/google/callback",
            json={
                "email": "victim@example.com",
                "name": "Victim User",
                "google_id": "google_victim",
                "picture": "https://attacker.com/pic.png",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "MISSING_GOOGLE_CREDENTIAL"

    def test_post_callback_with_mock_payload_dict_without_token_returns_400(self):
        """Unauthenticated mock_payload dict without token must be rejected."""
        resp = client.post(
            "/api/v1/auth/google/callback",
            json={
                "mock_payload": {
                    "email": "victim@example.com",
                    "email_verified": True,
                    "name": "Victim",
                }
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "MISSING_GOOGLE_CREDENTIAL"

    def test_service_verify_google_identity_without_token_raises_bad_request(self):
        """GoogleAuthService must refuse identity objects lacking credential or id_token."""
        service = GoogleAuthService()
        req = GoogleAuthRequest(email="victim@example.com")
        with pytest.raises(BadRequestException) as exc_info:
            service.verify_google_identity(req)
        assert exc_info.value.error_code == "MISSING_GOOGLE_CREDENTIAL"


# ─────────────────────────────────────────────────────────────────────────────
# Security Vector 2: Missing Credential Rejection
# ─────────────────────────────────────────────────────────────────────────────


class TestMissingCredentialRejection:
    def test_empty_json_body_returns_400(self):
        resp = client.post("/api/v1/auth/google/callback", json={})
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "MISSING_GOOGLE_CREDENTIAL"

    def test_null_id_token_returns_400(self):
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": None})
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "MISSING_GOOGLE_CREDENTIAL"

    def test_empty_string_id_token_returns_400(self):
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": ""})
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "MISSING_GOOGLE_CREDENTIAL"

    def test_whitespace_string_id_token_returns_400(self):
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": "   "})
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "MISSING_GOOGLE_CREDENTIAL"

    def test_empty_credential_field_returns_400(self):
        resp = client.post("/api/v1/auth/google/callback", json={"credential": ""})
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "MISSING_GOOGLE_CREDENTIAL"


# ─────────────────────────────────────────────────────────────────────────────
# Security Vector 3 & 4: Cryptographic Signature & Tampering Verification
# ─────────────────────────────────────────────────────────────────────────────


class TestCryptographicSignatureAndTampering:
    def test_forged_signature_with_untrusted_key_rejected(self, setup_security_test):
        """Token signed with an attacker's private key (not in JWKS) must be rejected."""
        priv_pem_forged, _ = _generate_rsa_key_pair("attacker-kid")
        # Attacker signs token with untrusted key and claims it belongs to security-test-kid
        token = _create_signed_google_token(
            priv_pem=priv_pem_forged,
            kid="security-test-kid",
            email="victim@example.com",
        )
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": token})
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "INVALID_GOOGLE_TOKEN"

    def test_unknown_kid_rejected(self, setup_security_test):
        """Token with an unknown key ID not present in JWKS must be rejected."""
        priv_pem, _ = _generate_rsa_key_pair("unknown-kid")
        token = _create_signed_google_token(
            priv_pem=priv_pem,
            kid="unknown-kid",
            email="victim@example.com",
        )
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": token})
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "INVALID_GOOGLE_TOKEN"

    def test_transient_jwks_network_failure_returns_503(self, monkeypatch):
        """Transient network errors fetching Google JWKS return HTTP 503."""
        google_jwks_client.clear_overrides()

        def _mock_failing_fetch():
            from app.core.exceptions import ServiceUnavailableException

            raise ServiceUnavailableException(
                message="Google authentication service is currently unavailable",
                error_code="SERVICE_UNAVAILABLE",
            )

        monkeypatch.setattr(google_jwks_client, "_fetch_keys", _mock_failing_fetch)
        priv_pem, _ = _generate_rsa_key_pair("net-fail-kid")
        token = _create_signed_google_token(
            priv_pem=priv_pem,
            kid="net-fail-kid",
            email="victim@example.com",
        )
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": token})
        assert resp.status_code == 503
        assert resp.json()["error_code"] == "SERVICE_UNAVAILABLE"

    def test_tampered_signature_bytes_rejected(self, setup_security_test):
        """Token whose signature bytes were corrupted or modified must be rejected."""
        token = _create_signed_google_token(
            priv_pem=setup_security_test["priv_pem"],
            email="victim@example.com",
        )
        parts = token.split(".")
        # Corrupt the signature part
        corrupted_token = f"{parts[0]}.{parts[1]}.{parts[2][:-5]}xxxxx"
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": corrupted_token})
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "INVALID_GOOGLE_TOKEN"

    def test_tampered_payload_claims_rejected(self, setup_security_test):
        """Token whose payload was modified without valid re-signing must be rejected."""
        token = _create_signed_google_token(
            priv_pem=setup_security_test["priv_pem"],
            email="innocent@example.com",
        )
        parts = token.split(".")
        # Tamper payload claims to impersonate admin
        tampered_payload = {
            "iss": "https://accounts.google.com",
            "aud": "test-google-client-id",
            "sub": "google-uid-12345",
            "email": "admin@example.com",
            "email_verified": True,
            "exp": int(time.time()) + 3600,
        }
        encoded_tampered_payload = (
            base64.urlsafe_b64encode(json.dumps(tampered_payload).encode()).decode().rstrip("=")
        )
        tampered_token = f"{parts[0]}.{encoded_tampered_payload}.{parts[2]}"

        resp = client.post("/api/v1/auth/google/callback", json={"id_token": tampered_token})
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "INVALID_GOOGLE_TOKEN"


# ─────────────────────────────────────────────────────────────────────────────
# Security Vector 5: Unverified Email Rejection
# ─────────────────────────────────────────────────────────────────────────────


class TestUnverifiedEmailRejection:
    def test_email_verified_false_rejected(self, setup_security_test):
        """Token with email_verified: False must be strictly rejected."""
        token = _create_signed_google_token(
            priv_pem=setup_security_test["priv_pem"],
            email="unverified@example.com",
            email_verified=False,
        )
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": token})
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "UNVERIFIED_GOOGLE_EMAIL"

    def test_missing_email_verified_claim_rejected(self, setup_security_test):
        """Token with missing email_verified claim must be strictly rejected."""
        token = _create_signed_google_token(
            priv_pem=setup_security_test["priv_pem"],
            email="missing_verified@example.com",
            email_verified=None,
        )
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": token})
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "UNVERIFIED_GOOGLE_EMAIL"

    def test_string_false_email_verified_rejected(self, setup_security_test):
        """Token with email_verified='false' as string must be rejected."""
        token = _create_signed_google_token(
            priv_pem=setup_security_test["priv_pem"],
            email="string_false@example.com",
            email_verified="false",
        )
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": token})
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "UNVERIFIED_GOOGLE_EMAIL"


# ─────────────────────────────────────────────────────────────────────────────
# Security Vector 6: Expired Token Rejection
# ─────────────────────────────────────────────────────────────────────────────


class TestExpiredTokenRejection:
    def test_expired_token_rejected(self, setup_security_test):
        """Token with exp timestamp in the past must be rejected with 401."""
        token = _create_signed_google_token(
            priv_pem=setup_security_test["priv_pem"],
            email="expired@example.com",
            exp=int(time.time()) - 300,
        )
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": token})
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "EXPIRED_GOOGLE_TOKEN"


# ─────────────────────────────────────────────────────────────────────────────
# Security Vector 7: Audience Claim Validation
# ─────────────────────────────────────────────────────────────────────────────


class TestAudienceValidation:
    def test_mismatched_audience_rejected(self, setup_security_test):
        """Token with aud not matching configured GOOGLE_CLIENT_ID must be rejected."""
        token = _create_signed_google_token(
            priv_pem=setup_security_test["priv_pem"],
            aud="wrong-foreign-client-id",
        )
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": token})
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "INVALID_GOOGLE_TOKEN"


# ─────────────────────────────────────────────────────────────────────────────
# Security Vector 8: Issuer Claim Validation
# ─────────────────────────────────────────────────────────────────────────────


class TestIssuerValidation:
    def test_untrusted_issuer_rejected(self, setup_security_test):
        """Token with non-Google issuer must be rejected."""
        token = _create_signed_google_token(
            priv_pem=setup_security_test["priv_pem"],
            iss="https://evil-identity.com",
        )
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": token})
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "INVALID_GOOGLE_TOKEN"

    def test_valid_google_issuers_accepted(self, setup_security_test):
        """Both accounts.google.com and https://accounts.google.com must be accepted."""
        for i, valid_iss in enumerate(("accounts.google.com", "https://accounts.google.com")):
            token = _create_signed_google_token(
                priv_pem=setup_security_test["priv_pem"],
                iss=valid_iss,
                email=f"valid_iss_{i}_{int(time.time())}@example.com",
                sub=f"sub_valid_iss_{i}",
            )
            resp = client.post("/api/v1/auth/google/callback", json={"id_token": token})
            assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Security Vector 9: Production Mock Gate & Fail-Closed Enforcement
# ─────────────────────────────────────────────────────────────────────────────


class TestProductionMockGate:
    def test_mock_token_rejected_in_production_environment(self, monkeypatch):
        """In production, mock tokens must fail closed even if ALLOW_MOCK_GOOGLE_AUTH is set."""
        monkeypatch.setattr(get_settings(), "app_env", AppEnv.PROD)
        monkeypatch.setattr(get_settings(), "allow_mock_google_auth", True)

        # 1. Direct verifier call must raise UnauthorizedException(MOCK_AUTH_DISABLED)
        with pytest.raises(UnauthorizedException) as exc_info:
            google_oauth_verifier.verify_google_token("mock:alice@finex.com:Alice")
        assert exc_info.value.error_code == "MOCK_AUTH_DISABLED"

        # 2. HTTP callback request in production must be refused (401 or 403, never 200)
        resp = client.post(
            "/api/v1/auth/google/callback",
            json={"id_token": "mock:alice@finex.com:Alice"},
        )
        assert resp.status_code in (401, 403)
        assert resp.json()["success"] is False

    def test_mock_token_rejected_when_allow_mock_auth_is_false(self, monkeypatch):
        """When allow_mock_google_auth is False, mock tokens must be rejected."""
        monkeypatch.setattr(get_settings(), "allow_mock_google_auth", False)

        resp = client.post(
            "/api/v1/auth/google/callback",
            json={"id_token": "mock:alice@finex.com:Alice"},
        )
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "MOCK_AUTH_DISABLED"

    def test_settings_validation_forbids_mock_auth_in_production(self):
        """Settings model validator must reject allow_mock_google_auth=True in production."""
        with pytest.raises(ConfigurationError):
            Settings(
                app_env=AppEnv.PROD,
                allow_mock_google_auth=True,
                secret_key="a" * 32,
                api_base_url="https://api.finex.com",
                allowed_origins=["https://finex.com"],
                debug=False,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Security Vector 10: Legitimate Token Acceptance & Account Linking Safeguards
# ─────────────────────────────────────────────────────────────────────────────


class TestLegitimateTokenAndAccountLinking:
    def test_valid_token_authenticates_and_issues_sessions(self, setup_security_test):
        """Legitimate cryptographic token creates user and returns valid session tokens."""
        token = _create_signed_google_token(
            priv_pem=setup_security_test["priv_pem"],
            email="verified.google@example.com",
            name="Verified User",
        )
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": token})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "verified.google@example.com"

    def test_verified_token_links_to_existing_password_user(self, setup_security_test):
        """A verified Google token links google_id to existing email/password account."""
        repo = setup_security_test["repo"]
        # Existing password user
        pwd_user = repo.create_user(
            name="Existing Password User",
            email="existing@example.com",
            hashed_password="hashed_pwd_placeholder",
        )

        token = _create_signed_google_token(
            priv_pem=setup_security_test["priv_pem"],
            email="existing@example.com",
            sub="gid-linked-1234",
        )
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": token})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["user"]["id"] == pwd_user.id

        # Verify repo record now has google_id
        updated = repo.get_user_by_id(pwd_user.id)
        assert updated.google_id == "gid-linked-1234"

    def test_conflicting_google_id_for_different_email_rejected(self, setup_security_test):
        """A Google ID already linked to another email must be rejected."""
        repo = setup_security_test["repo"]
        # User 1 registered with google_id
        repo.create_user(
            name="Alice",
            email="alice@example.com",
            hashed_password="",
            google_id="stable_google_id_999",
        )

        # Attacker presents a token claiming the same google_id for bob@example.com
        token = _create_signed_google_token(
            priv_pem=setup_security_test["priv_pem"],
            email="bob@example.com",
            sub="stable_google_id_999",
        )
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": token})
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "GOOGLE_ACCOUNT_CONFLICT"


# ─────────────────────────────────────────────────────────────────────────────
# Security Vector 11: PostgreSQL Repository Parity
# ─────────────────────────────────────────────────────────────────────────────


class TestPostgresRepositoryParity:
    def test_postgres_repo_rejects_unverified_email_linking(self):
        """PostgresUserRepository must strictly reject unverified email linking."""
        pg_repo = PostgresUserRepository(require_db=False)
        with pytest.raises(BadRequestException) as exc_info:
            pg_repo.get_or_create_google_user(
                google_id="gid_unverified",
                email="unverified@example.com",
                name="Unverified",
                email_verified=False,
            )
        assert exc_info.value.error_code == "UNVERIFIED_GOOGLE_EMAIL"

    def test_postgres_repo_handles_verified_google_identity(self):
        """PostgresUserRepository successfully links/creates verified OAuth user."""
        pg_repo = PostgresUserRepository(require_db=False)
        user = pg_repo.get_or_create_google_user(
            google_id="gid_verified_pg",
            email="pg_oauth@example.com",
            name="PG OAuth User",
            email_verified=True,
        )
        assert user.email == "pg_oauth@example.com"
        assert user.google_id == "gid_verified_pg"
