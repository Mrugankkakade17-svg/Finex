# app/auth/principal.py
"""Principal utilities for authentication.

Provides functions to retrieve the current principal (user) from
the request context, handling both bearer token sessions and real
sessions (e.g., OAuth). This module depends on ``dependencies`` for
common FastAPI dependency injection.
"""

from typing import Optional
from fastapi import Depends, HTTPException, Request, status

from .dependencies import get_current_user, get_current_bearer_user


def get_principal(request: Request, token: Optional[str] = None) -> str:
    """Return the identifier of the active principal.

    The function first attempts to resolve a bearer token if ``token``
    is supplied. If no token is present, it falls back to the regular
    session user retrieved via ``get_current_user``.

    Args:
        request: The incoming ``FastAPI`` request object.
        token: Optional bearer token extracted from the ``Authorization``
            header.
    Returns:
        The principal identifier (e.g., username or user id).
    Raises:
        HTTPException: If no principal can be resolved.
    """
    if token:
        user = get_current_bearer_user(token)
    else:
        user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthenticated principal",
        )
    return user

# Export for FastAPI dependency injection
CurrentPrincipal = Depends(lambda request: get_principal(request))
