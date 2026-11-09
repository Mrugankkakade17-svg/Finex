from app.auth.jwt_handler import create_access_token, create_refresh_token, decode_token
from app.auth.password import hash_password, verify_password
from app.auth.token_store import token_revocation_store
from app.core.exceptions import BadRequestException, UnauthorizedException
from app.ports.adapters.mock_google_verifier import mock_google_verifier
from app.repositories.user_repository import user_repository


def register(name: str, email: str, password: str) -> dict:
    """
    Validate duplicate email.
    Hash password.
    Create user.
    Generate JWT.
    Generate Refresh Token.
    """
    existing = user_repository.get_user_by_email(email)
    if existing:
        raise BadRequestException(
            message="Email already registered",
            error_code="EMAIL_EXISTS",
        )

    hashed = hash_password(password)
    user = user_repository.create_user(name=name, email=email, hashed_password=hashed)

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    refresh_token = create_refresh_token(data={"sub": user.email, "user_id": user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
    }


def login(email: str, password: str) -> dict:
    """
    Verify password.
    Generate JWT.
    Generate Refresh Token.
    Raise FinExException when required.
    """
    user = user_repository.get_user_by_email(email)

    if not user or not verify_password(password, user.hashed_password):
        raise UnauthorizedException(
            message="Invalid email or password",
            error_code="INVALID_CREDENTIALS",
        )

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    refresh_token = create_refresh_token(data={"sub": user.email, "user_id": user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
    }


def get_current_user(token: str) -> dict:
    """
    Decode access token.
    Return user payload.
    Raise FinExException if invalid.
    """
    payload = decode_token(token)

    if payload is None:
        raise UnauthorizedException(
            message="Invalid or expired token",
            error_code="INVALID_TOKEN",
        )

    if payload.get("type") != "access":
        raise UnauthorizedException(
            message="Invalid token type",
            error_code="INVALID_TOKEN_TYPE",
        )

    return payload


def refresh(token: str) -> dict:
    """
    Validate refresh token.
    Check revocation store — rejects tokens revoked on logout.
    Generate new access token.
    """
    payload = decode_token(token)

    if payload is None or payload.get("type") != "refresh":
        raise UnauthorizedException(
            message="Invalid refresh token",
            error_code="INVALID_REFRESH_TOKEN",
        )

    jti = payload.get("jti")
    if jti and token_revocation_store.is_revoked(jti):
        raise UnauthorizedException(
            message="Token has been revoked",
            error_code="TOKEN_REVOKED",
        )

    new_access_token = create_access_token(
        data={"sub": payload["sub"], "user_id": payload.get("user_id")}
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
    }


def logout(refresh_token: str | None = None) -> dict:
    """
    Logout — revoke the refresh token by its JTI so it cannot be reused.
    Raises UnauthorizedException if caller accidentally passes an access token.
    Client should discard both tokens.
    """
    if refresh_token:
        payload = decode_token(refresh_token)
        if payload is None:
            return {}
        if payload.get("type") != "refresh":
            raise UnauthorizedException(
                message="Expected a refresh token, not an access token",
                error_code="INVALID_TOKEN_TYPE",
            )
        jti = payload.get("jti")
        if jti:
            token_revocation_store.revoke(jti)
    return {}


def login_or_create_google_user(
    google_id: str, email: str, name: str, avatar_url: str | None = None
) -> dict:
    """
    Find existing user by email or create a new one from Google identity.
    Returns JWT access + refresh tokens plus the user profile.
    """
    user = user_repository.get_user_by_email(email)

    if not user:
        # First-time Google login — create account with no password
        user = user_repository.create_user(
            name=name,
            email=email,
            hashed_password="",  # No password for OAuth users
        )

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    refresh_token = create_refresh_token(data={"sub": user.email, "user_id": user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
    }


def google_callback(id_token: str, google_verifier=None) -> dict:
    """
    Verify Google identity token via the injected verifier port.
    Defaults to mock_google_verifier for development.
    Create or load user. Return JWT tokens + user profile.
    """
    verifier = google_verifier or mock_google_verifier
    identity = verifier.verify_google_token(id_token)
    return login_or_create_google_user(
        google_id=identity.google_id,
        email=str(identity.email),
        name=identity.name,
        avatar_url=identity.picture,
    )
