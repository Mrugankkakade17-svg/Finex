from typing import Protocol

from app.schemas.google_identity import GoogleIdentity


class GoogleOAuthPort(Protocol):
    """
    Port interface for Google OAuth identity verification.

    Production: implement with google-auth library verifying real ID tokens.
    Development/Test: use MockGoogleVerifier.
    """

    def verify_google_token(self, id_token: str) -> GoogleIdentity:
        """
        Verify a Google ID token and return the decoded identity.

        Args:
            id_token: The Google ID token string from the frontend.

        Returns:
            GoogleIdentity with google_id, email, name, picture.

        Raises:
            AuthenticationException: if the token is invalid or expired.
        """
        ...
