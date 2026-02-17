"""
User Role enum and auth-related Pydantic schemas for Sprint 12 RBAC.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """User roles for role-based access control."""
    creator = "creator"      # Generate jobs, edit drafts
    reviewer = "reviewer"    # Approve, reject, comment
    publisher = "publisher"  # Publish approved questions
    admin = "admin"          # All permissions + user management


class UserCreate(BaseModel):
    """Request schema for creating a new user."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    role: UserRole = UserRole.creator


class UserLogin(BaseModel):
    """Request schema for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Response schema for user data (excludes password)."""
    id: int
    email: str
    name: str
    role: UserRole
    created_at: datetime
    is_active: bool = True


class TokenResponse(BaseModel):
    """Response schema for JWT token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration
    user: UserResponse


class UserUpdate(BaseModel):
    """Request schema for updating an existing user (admin only)."""
    role: UserRole | None = None
    is_active: bool | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)


class TokenPayload(BaseModel):
    """JWT token payload structure."""
    sub: str  # User ID
    email: str
    role: UserRole
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
