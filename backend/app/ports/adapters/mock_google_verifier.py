"""
Mock Google OAuth verifier for development and testing.

Accepts tokens in the format:  mock:<email>:<name>
Example: "mock:alice@finex.com:Alice Smith"

This implements GoogleOAuthPort so it can be injected wherever a real
Google verifier would be used.
Fails closed in UAT and production environments.
"""

from app.config.settings import AppEnv, get_settings
from app.core.exceptions import AuthenticationException, UnauthorizedException
from app.schemas.google_identity import GoogleIdentity


class MockGoogleVerifier:
    """
    Development/test implementation of GoogleOAuthPort.

    Token format: mock:<email>:<name>
    Any other format raises AuthenticationException (simulates invalid token).
    Strictly forbidden in production configurations.
    """

    def verify_google_token(self, id_token: str) -> GoogleIdentity:
        settings = get_settings()
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

        if not id_token.startswith("mock:"):
            raise AuthenticationException(message="Invalid Google ID token")

        parts = id_token.split(":", maxsplit=2)
        if len(parts) != 3:
            raise AuthenticationException(
                message="Invalid mock token format. Expected: mock:<email>:<name>"
            )

        _, email, name = parts

        if not email or "@" not in email:
            raise AuthenticationException(message="Invalid email in mock token")

        # Derive a stable google_id from the email (deterministic for tests)
        google_id = f"mock_gid_{email.replace('@', '_').replace('.', '_')}"

        picture = (
            f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&background=6366f1&color=fff"
        )

        return GoogleIdentity(
            google_id=google_id,
            email=email,
            name=name,
            picture=picture,
            email_verified=True,
        )


# Singleton for dependency injection
mock_google_verifier = MockGoogleVerifier()
