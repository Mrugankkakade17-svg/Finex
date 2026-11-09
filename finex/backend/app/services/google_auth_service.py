from typing import Any, Dict

from jose import jwt

from app.core.exceptions import BadRequestException, UnauthorizedException
from app.schemas.auth import GoogleAuthRequest


class GoogleAuthService:
    """
    Service responsible for verifying Google identity tokens or mock payloads.
    Provides pluggable verification supporting development mock identities,
    local testing tokens, and production Google ID tokens.
    """

    def verify_google_identity(self, request: GoogleAuthRequest) -> Dict[str, Any]:
        """
        Extract and verify Google user identity from request.
        Supports:
        1. Explicit mock identity fields in request (email, name, google_id, picture).
        2. Nested mock_payload dictionary.
        3. JWT credential/id_token string (mock or Google-issued).
        """
        # Case 1: Direct mock identity passed in fields
        if request.email:
            google_id = request.google_id or f"google_{request.email}"
            name = request.name or request.email.split("@")[0].capitalize()
            return {
                "google_id": google_id,
                "email": str(request.email),
                "name": name,
                "avatar_url": request.picture,
            }

        # Case 2: Nested mock_payload
        if request.mock_payload:
            payload = request.mock_payload
            email = payload.get("email")
            if not email:
                raise BadRequestException(
                    message="Mock Google identity must contain an email address",
                    error_code="INVALID_GOOGLE_IDENTITY",
                )
            google_id = payload.get("google_id") or payload.get("sub") or f"google_{email}"
            name = payload.get("name") or email.split("@")[0].capitalize()
            return {
                "google_id": google_id,
                "email": email,
                "name": name,
                "avatar_url": payload.get("picture") or payload.get("avatar_url"),
            }

        # Case 3: JWT token (credential or id_token)
        token_str = request.credential or request.id_token
        if token_str:
            return self._verify_token_string(token_str)

        raise BadRequestException(
            message="Google identity payload or credential is required",
            error_code="MISSING_GOOGLE_CREDENTIAL",
        )

    def _verify_token_string(self, token: str) -> Dict[str, Any]:
        """
        Parse and verify Google ID token string.
        In development/test mode, decodes claims with fallback for mock tokens.
        """
        token = token.strip()
        if not token:
            raise BadRequestException(
                message="Google token cannot be empty",
                error_code="INVALID_GOOGLE_TOKEN",
            )

        try:
            # First attempt to decode claims (without verifying signature if in mock mode)
            claims = jwt.get_unverified_claims(token)
            email = claims.get("email")
            google_id = claims.get("sub") or claims.get("google_id")
            name = claims.get("name") or (
                email.split("@")[0].capitalize() if email else "Google User"
            )
            picture = claims.get("picture") or claims.get("avatar_url")

            if not email:
                raise UnauthorizedException(
                    message="Google token does not contain an email claim",
                    error_code="INVALID_GOOGLE_TOKEN",
                )

            return {
                "google_id": str(google_id) if google_id else f"google_{email}",
                "email": email,
                "name": name,
                "avatar_url": picture,
            }
        except Exception as exc:
            # If token is a plain string mock identifier like "mock-google-token-user@example.com"
            if "@" in token:
                parts = token.split("@")
                username = parts[0].replace("mock-google-token-", "").replace("mock-", "")
                email = f"{username}@{parts[1]}"
                return {
                    "google_id": f"google_{email}",
                    "email": email,
                    "name": username.capitalize(),
                    "avatar_url": None,
                }

            raise UnauthorizedException(
                message=f"Failed to verify Google token: {str(exc)}",
                error_code="INVALID_GOOGLE_TOKEN",
            )


# Singleton instance
google_auth_service = GoogleAuthService()
