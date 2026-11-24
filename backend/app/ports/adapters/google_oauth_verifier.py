"""
Google OAuth token verifier implementing cryptographic token verification
against Google's JWKS public keys.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx
from jose import jwk, jwt

from app.config.logging import logger
from app.config.settings import AppEnv, get_settings
from app.core.exceptions import (
    AuthenticationException,
    BadRequestException,
    ConfigurationError,
    ServiceUnavailableException,
    UnauthorizedException,
)
from app.ports.google_oauth_port import GoogleOAuthPort
from app.schemas.google_identity import GoogleIdentity


class GoogleJWKSClient:
    """
    Manages caching and retrieval of Google's public JSON Web Key Set (JWKS).
    Supports injecting key overrides for offline/deterministic automated testing.
    """

    JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"

    def __init__(self, jwks_url: str = JWKS_URL, cache_ttl_seconds: int = 3600):
        self.jwks_url = jwks_url
        self.cache_ttl_seconds = cache_ttl_seconds
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._expires_at: float = 0.0
        self._key_overrides: Dict[str, Dict[str, Any]] = {}

    def add_key_override(self, kid: str, key_dict: Dict[str, Any]) -> None:
        """Register a test key for a given kid (used in automated unit/regression tests)."""
        self._key_overrides[kid] = key_dict

    def clear_overrides(self) -> None:
        """Clear test key overrides."""
        self._key_overrides.clear()

    def get_key(self, kid: str) -> Optional[Dict[str, Any]]:
        """Fetch the public key dictionary for a given key ID."""
        # 1. Check test overrides first (prevents external network calls during tests)
        if self._key_overrides:
            return self._key_overrides.get(kid)

        # 2. Check cached keys
        now = time.time()
        if now < self._expires_at and self._keys:
            return self._keys.get(kid)

        # 3. Refresh from Google JWKS endpoint
        self._fetch_keys()
        return self._keys.get(kid)

    def _fetch_keys(self) -> None:
        """Fetch public keys from Google JWKS endpoint."""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(self.jwks_url)
                if response.status_code != 200:
                    logger.error(
                        "Failed to fetch Google JWKS from %s: HTTP %s",
                        self.jwks_url,
                        response.status_code,
                    )
                    raise ServiceUnavailableException(
                        message="Failed to retrieve Google public keys",
                        error_code="SERVICE_UNAVAILABLE",
                    )
                data = response.json()
        except ServiceUnavailableException:
            raise
        except Exception as exc:
            logger.error("Transient error fetching Google JWKS: %s", exc)
            raise ServiceUnavailableException(
                message=f"Google authentication service is currently unavailable: {str(exc)}",
                error_code="SERVICE_UNAVAILABLE",
            ) from exc

        keys = data.get("keys", [])
        self._keys = {k["kid"]: k for k in keys if "kid" in k}
        self._expires_at = time.time() + self.cache_ttl_seconds


google_jwks_client = GoogleJWKSClient()


class GoogleOAuthVerifier(GoogleOAuthPort):
    """
    Cryptographic Google ID token verifier implementing GoogleOAuthPort.
    Validates token signature against Google JWKS and enforces all required claims.
    """

    VALID_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

    def __init__(self, jwks_client: Optional[GoogleJWKSClient] = None):
        self.jwks_client = jwks_client or google_jwks_client

    def verify_google_token(self, id_token: str) -> GoogleIdentity:
        token = id_token.strip() if id_token else ""
        if not token:
            raise BadRequestException(
                message="Google token cannot be empty",
                error_code="INVALID_GOOGLE_TOKEN",
            )

        settings = get_settings()

        # Handle mock tokens if provided
        if token.startswith("mock:") or token.startswith("mock-google-token-"):
            if settings.is_production_like or settings.app_env in {AppEnv.PROD, AppEnv.UAT}:
                raise UnauthorizedException(
                    message="Mock Google authentication is disabled in production",
                    error_code="MOCK_AUTH_DISABLED",
                )
            if not settings.allow_mock_google_auth:
                raise UnauthorizedException(
                    message="Mock Google authentication is disabled",
                    error_code="MOCK_AUTH_DISABLED",
                )
            return self._verify_mock_token(token)

        # Real cryptographic verification
        try:
            header = jwt.get_unverified_header(token)
        except Exception as exc:
            raise UnauthorizedException(
                message=f"Invalid Google token format: {str(exc)}",
                error_code="INVALID_GOOGLE_TOKEN",
            )

        kid = header.get("kid")
        alg = header.get("alg")
        if not kid:
            raise UnauthorizedException(
                message="Missing key ID (kid) in Google token header",
                error_code="INVALID_GOOGLE_TOKEN",
            )
        if alg != "RS256":
            raise UnauthorizedException(
                message=f"Unsupported token algorithm '{alg}', expected RS256",
                error_code="INVALID_GOOGLE_TOKEN",
            )

        key_dict = self.jwks_client.get_key(kid)
        if not key_dict:
            raise UnauthorizedException(
                message=f"Unknown or untrusted Google key ID: {kid}",
                error_code="INVALID_GOOGLE_TOKEN",
            )

        try:
            public_key = jwk.construct(key_dict)
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": False,
                    "verify_iss": False,
                },
            )
        except jwt.ExpiredSignatureError:
            raise UnauthorizedException(
                message="Google token has expired",
                error_code="EXPIRED_GOOGLE_TOKEN",
            )
        except jwt.JWTClaimsError as exc:
            raise UnauthorizedException(
                message=f"Invalid Google token claims: {str(exc)}",
                error_code="INVALID_GOOGLE_TOKEN",
            )
        except Exception as exc:
            raise UnauthorizedException(
                message=f"Google token signature verification failed: {str(exc)}",
                error_code="INVALID_GOOGLE_TOKEN",
            )

        # Validate standard claims
        # 1. Issuer
        iss = claims.get("iss")
        if iss not in self.VALID_ISSUERS:
            raise UnauthorizedException(
                message=f"Invalid Google token issuer: {iss}",
                error_code="INVALID_GOOGLE_TOKEN",
            )

        # 2. Audience
        aud = claims.get("aud")
        if settings.google_client_id:
            if aud != settings.google_client_id:
                raise UnauthorizedException(
                    message=f"Google token audience '{aud}' does not match configured client ID",
                    error_code="INVALID_GOOGLE_TOKEN",
                )
        elif settings.is_production_like:
            raise ConfigurationError(
                message="GOOGLE_CLIENT_ID must be configured in production",
                error_code="CONFIGURATION_ERROR",
            )
        else:
            if not aud or not str(aud).strip():
                raise UnauthorizedException(
                    message="Google token missing audience claim",
                    error_code="INVALID_GOOGLE_TOKEN",
                )

        # 3. Expiration (in addition to jose check)
        exp = claims.get("exp")
        if exp is not None and int(exp) < int(time.time()):
            raise UnauthorizedException(
                message="Google token has expired",
                error_code="EXPIRED_GOOGLE_TOKEN",
            )

        # 4. Subject
        sub = claims.get("sub")
        if not sub or not str(sub).strip():
            raise UnauthorizedException(
                message="Google token missing subject (sub) claim",
                error_code="INVALID_GOOGLE_TOKEN",
            )

        # 5. Email
        email = claims.get("email")
        if not email or not str(email).strip() or "@" not in str(email):
            raise UnauthorizedException(
                message="Google token does not contain a valid email claim",
                error_code="INVALID_GOOGLE_TOKEN",
            )

        # 6. Email verified
        email_verified = claims.get("email_verified")
        if email_verified is not True and str(email_verified).lower() not in ("true", "1"):
            raise UnauthorizedException(
                message="Google identity email is not verified",
                error_code="UNVERIFIED_GOOGLE_EMAIL",
            )

        name = claims.get("name") or str(email).split("@")[0].capitalize()
        picture = claims.get("picture") or claims.get("avatar_url")

        return GoogleIdentity(
            google_id=str(sub).strip(),
            email=str(email).strip().lower(),
            name=str(name).strip(),
            picture=str(picture).strip() if picture else None,
            email_verified=True,
        )

    def _verify_mock_token(self, token: str) -> GoogleIdentity:
        if token.startswith("mock:"):
            parts = token.split(":", maxsplit=2)
            if len(parts) != 3:
                raise AuthenticationException(
                    message="Invalid mock token format. Expected: mock:<email>:<name>"
                )
            _, email, name = parts
            if not email or "@" not in email:
                raise AuthenticationException(message="Invalid email in mock token")
            google_id = f"mock_gid_{email.replace('@', '_').replace('.', '_')}"
            encoded_name = name.replace(" ", "+")
            picture = f"https://ui-avatars.com/api/?name={encoded_name}&background=6366f1&color=fff"
            return GoogleIdentity(
                google_id=google_id,
                email=email,
                name=name,
                picture=picture,
                email_verified=True,
            )
        elif token.startswith("mock-google-token-"):
            clean = token.replace("mock-google-token-", "")
            if "@" not in clean:
                raise UnauthorizedException(
                    message="Invalid mock token email format",
                    error_code="INVALID_GOOGLE_TOKEN",
                )
            username = clean.split("@")[0]
            return GoogleIdentity(
                google_id=f"google_{clean}",
                email=clean,
                name=username.capitalize(),
                picture=None,
                email_verified=True,
            )
        raise UnauthorizedException(
            message="Unrecognized mock token format",
            error_code="INVALID_GOOGLE_TOKEN",
        )


google_oauth_verifier = GoogleOAuthVerifier()
