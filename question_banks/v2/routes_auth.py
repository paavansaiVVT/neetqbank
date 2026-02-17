"""
Authentication routes for Sprint 12 RBAC.
Provides endpoints for user registration, login, user management (DB-backed).
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from question_banks.v2.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from question_banks.v2.config import get_settings
from question_banks.v2.repository import QbankV2Repository
from question_banks.v2.schemas_auth import (
    TokenPayload,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserRole,
    UserUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/qbank/auth", tags=["auth"])


def _repo() -> QbankV2Repository:
    return QbankV2Repository()


def _ensure_default_admin() -> None:
    """Create default admin if no users exist in DB."""
    repo = _repo()
    admin_email = "admin@qbank.dev"
    existing = repo.get_user_by_email(admin_email)
    if existing is None:
        try:
            repo.create_user(
                email=admin_email,
                password_hash=hash_password("admin123"),
                name="System Admin",
                role=UserRole.admin.value,
            )
            logger.info("Created default admin user: %s", admin_email)
        except Exception:
            logger.debug("Default admin already exists or creation failed")


# Seed default admin on module load
try:
    _ensure_default_admin()
except Exception:
    logger.warning("Could not seed default admin (DB may not be ready)")


def _user_to_response(user: dict[str, Any]) -> UserResponse:
    """Convert DB user dict to UserResponse."""
    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=UserRole(user["role"]),
        created_at=user["created_at"],
        is_active=user["is_active"],
    )


# ── Endpoints ────────────────────────────────────────────────────


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    data: UserCreate,
    current_user: TokenPayload = Depends(require_role(UserRole.admin)),
) -> TokenResponse:
    """
    Register a new user.

    Only admins can create new users.
    """
    repo = _repo()
    existing = repo.get_user_by_email(data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = repo.create_user(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        role=data.role.value,
    )

    token, expires_in = create_access_token(
        user_id=user["id"],
        email=user["email"],
        role=UserRole(user["role"]),
    )

    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=_user_to_response(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin) -> TokenResponse:
    """Authenticate user and return JWT token."""
    repo = _repo()
    user = repo.get_user_by_email(data.email)

    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    token, expires_in = create_access_token(
        user_id=user["id"],
        email=user["email"],
        role=UserRole(user["role"]),
    )

    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=_user_to_response(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: TokenPayload = Depends(get_current_user),
) -> UserResponse:
    """Get current authenticated user's info."""
    repo = _repo()
    user = repo.get_user_by_id(int(current_user.sub))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _user_to_response(user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: TokenPayload = Depends(require_role(UserRole.admin)),
) -> list[UserResponse]:
    """
    List all users.

    Only admins can view all users.
    """
    repo = _repo()
    users = repo.list_users()
    return [_user_to_response(u) for u in users]


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: TokenPayload = Depends(require_role(UserRole.admin)),
) -> UserResponse:
    """
    Update a user's role, active status, or name.

    Only admins can update users. Admins cannot deactivate themselves.
    """
    # Prevent admin from deactivating themselves
    if data.is_active is False and int(current_user.sub) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    repo = _repo()
    updated = repo.update_user(
        user_id,
        role=data.role.value if data.role else None,
        is_active=data.is_active,
        name=data.name,
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _user_to_response(updated)
