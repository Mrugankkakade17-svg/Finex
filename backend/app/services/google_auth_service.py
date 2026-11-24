"""
Google Auth Service responsible for extracting and verifying Google user identity.
Delegates token verification to the cryptographic GoogleOAuthVerifier and eliminates
caller-supplied identity bypass.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.exceptions import BadRequestException
from app.ports.adapters.google_oauth_verifier import google_oauth_verifier
from app.ports.google_oauth_port import GoogleOAuthPort
from app.schemas.auth import GoogleAuthRequest


class GoogleAuthService:
    """
    Service responsible for verifying Google identity tokens.
    Requires cryptographically verifiable Google ID tokens in production.
    Caller-supplied unauthenticated email or mock payloads without a valid
    token are strictly rejected to prevent identity bypass.
    """

    def __init__(self, verifier: Optional[GoogleOAuthPort] = None):
        self.verifier: GoogleOAuthPort = verifier or google_oauth_verifier

    def verify_google_identity(self, request: GoogleAuthRequest) -> Dict[str, Any]:
        """
        Extract and verify Google user identity from request.
        Requires a valid token in request.credential or request.id_token.
        Caller-supplied unauthenticated fields are strictly rejected.
        """
        token_str = request.credential or request.id_token
        if not token_str or not token_str.strip():
            raise BadRequestException(
                message="Google identity payload or credential is required",
                error_code="MISSING_GOOGLE_CREDENTIAL",
            )

        identity = self.verifier.verify_google_token(token_str.strip())
        return {
            "google_id": identity.google_id,
            "email": str(identity.email),
            "name": identity.name,
            "avatar_url": identity.picture,
            "email_verified": getattr(identity, "email_verified", True),
        }


# Singleton instance
google_auth_service = GoogleAuthService()
