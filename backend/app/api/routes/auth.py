from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import DEMO_ACCESS_TOKEN, require_demo_user
from app.schemas.auth import LoginRequest, LoginResponse, UserProfile
from app.services.mock_repository import DEMO_USER

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    if payload.account != "demo" or payload.password != "demo1234":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误，请使用演示账号 demo / demo1234",
        )
    return LoginResponse(access_token=DEMO_ACCESS_TOKEN, user=DEMO_USER)


@router.get("/me", response_model=UserProfile)
def me(user: Annotated[UserProfile, Depends(require_demo_user)]) -> UserProfile:
    return user
