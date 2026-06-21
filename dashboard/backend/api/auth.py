"""Registration and login for hosted multi-user mode."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from src.storage.database import database_enabled, init_database
from src.storage.session import AuthError, create_access_token
from src.storage.users import UserError, authenticate_user, create_user, get_user_by_id

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: str


def _require_multi_user() -> None:
    if not database_enabled():
        raise HTTPException(
            status_code=501,
            detail="Multi-user mode is disabled. Set MARKET_HELM_DATABASE_URL to enable.",
        )


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest) -> AuthResponse:
    _require_multi_user()
    init_database()
    try:
        user = create_user(body.email, body.password)
    except UserError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        token = create_access_token(user["id"])
    except AuthError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return AuthResponse(access_token=token, user=user)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest) -> AuthResponse:
    _require_multi_user()
    init_database()
    user = authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    try:
        token = create_access_token(user["id"])
    except AuthError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return AuthResponse(access_token=token, user=user)


@router.get("/me", response_model=UserResponse)
async def me(authorization: Optional[str] = Header(default=None)) -> UserResponse:
    from dashboard.backend.auth import bearer_user_id

    _require_multi_user()
    user_id = bearer_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return UserResponse(**user)
