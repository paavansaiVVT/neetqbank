"""
JWT-based authentication for Sprint 12 RBAC.
Extends existing auth.py with user authentication and role-based access control.
"""
from __future__ import annotations

import hmac
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable

import bcrypt
from fastapi import Depends, Header, HTTPException, Query, status
from jose import JWTError, jwt

from question_banks.v2.config import get_settings
from question_banks.v2.schemas_auth import TokenPayload, UserRole

logger = logging.getLogger(__name__)

# JWT Configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def get_jwt_secret() -> str:
    """Get JWT secret from settings or fall back to internal API key."""
    settings = get_settings()
    return settings.internal_api_key or "fallback-secret-change-in-production"


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )


def create_access_token(user_id: int, email: str, role: UserRole) -> tuple[str, int]:
    """
    Create a JWT access token.
    
    Returns:
        Tuple of (token, expires_in_seconds)
    """
    now = datetime.utcnow()
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + expires_delta
    
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role.value,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }
    
    token = jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT access token.
    
    Raises:
        HTTPException: If token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
        return TokenPayload(
            sub=payload["sub"],
            email=payload["email"],
            role=UserRole(payload["role"]),
            exp=payload["exp"],
            iat=payload["iat"],
        )
    except JWTError as e:
        logger.warning("JWT decode error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> TokenPayload:
    """
    FastAPI dependency to extract and validate the current user from JWT.
    
    Usage:
        @router.get("/protected")
        async def protected_endpoint(user: TokenPayload = Depends(get_current_user)):
            return {"user_id": user.sub, "role": user.role}
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = parts[1]
    return decode_access_token(token)


def require_role(*allowed_roles: UserRole):
    """
    Dependency factory that creates a role checker.
    
    Usage:
        @router.post("/jobs")
        async def create_job(
            user: TokenPayload = Depends(require_role(UserRole.creator, UserRole.admin))
        ):
            pass
    """
    async def role_checker(
        user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' is not allowed. Required: {[r.value for r in allowed_roles]}",
            )
        return user
    
    return role_checker


# Keep the original internal API key check for backward compatibility
async def require_internal_api_key(
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
    api_key: str | None = Query(default=None, alias="key"),
) -> None:
    """Original API key authentication for internal services."""
    settings = get_settings()

    if not settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="QBANK_V2_INTERNAL_API_KEY is not configured",
        )

    token = x_internal_api_key or api_key

    if not token or not hmac.compare_digest(token, settings.internal_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid internal API key"
        )


async def require_auth_or_api_key(
    authorization: str | None = Header(default=None),
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
    api_key: str | None = Query(default=None, alias="key"),
) -> TokenPayload | None:
    """
    Accept either JWT auth or internal API key.
    Returns TokenPayload if JWT is used, None if API key is used.
    """
    # Try JWT first
    if authorization:
        try:
            return await get_current_user(authorization)
        except HTTPException:
            pass  # Fall through to API key check
    
    # Try internal API key
    token = x_internal_api_key or api_key
    settings = get_settings()
    
    if token and settings.internal_api_key and hmac.compare_digest(token, settings.internal_api_key):
        # API key is valid, return None to indicate API key auth (no user context)
        return None
    
    # Neither worked
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid JWT token or internal API key required",
        headers={"WWW-Authenticate": "Bearer"},
    )
