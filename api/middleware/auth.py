"""
PROVCHAIN — Firebase Auth Middleware
======================================
Validates Firebase Auth JWT tokens from the Authorization header.

Phase 1: Stub implementation — logs the header and passes through.
Phase 2+: Will call firebase_admin.auth.verify_id_token().

Usage in routes:
    from api.middleware.auth import verify_token

    @router.get("/protected")
    async def protected_route(user=Depends(verify_token)):
        return {"uid": user["uid"]}
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import get_settings

logger = logging.getLogger(__name__)

# HTTPBearer extracts the token from "Authorization: Bearer <token>"
security_scheme = HTTPBearer(auto_error=False)


async def verify_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> dict:
    """
    Validate Firebase Auth token from the Authorization header.

    Returns a dict with user info (uid, email, etc.).
    In Phase 1, this is a passthrough stub that returns a placeholder user.

    Raises:
        HTTPException 401 if no token is provided and DEBUG is False.
    """
    settings = get_settings()

    # In debug mode, allow unauthenticated requests with a placeholder user
    if settings.DEBUG:
        if credentials is None:
            logger.debug("DEBUG mode: no auth token — using placeholder user")
            return {
                "uid": "debug-user",
                "email": "debug@provchain.dev",
                "name": "Debug User",
            }

        logger.debug("DEBUG mode: token provided but not verified — passing through")
        return {
            "uid": "debug-user",
            "email": "debug@provchain.dev",
            "name": "Debug User",
            "token_present": True,
        }

    # Production: require a valid token
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # TODO (Phase 2): Replace with actual Firebase token verification
    # import firebase_admin
    # from firebase_admin import auth
    # decoded_token = auth.verify_id_token(token)
    # return decoded_token

    logger.warning("Token verification not yet implemented — rejecting request")
    raise HTTPException(
        status_code=401,
        detail="Token verification not yet implemented",
        headers={"WWW-Authenticate": "Bearer"},
    )
