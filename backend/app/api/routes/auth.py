from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.core.identity import DEMO_ACCESS_TOKEN, require_session
from app.schemas.auth import LoginRequest, LoginResponse, UserProfile
from app.services.mock_repository import DEMO_USER

router = APIRouter(prefix="/auth", tags=["auth"])


def _dev_login_enabled() -> bool:
    settings = get_settings()
    return (
        settings.demo_identity_fallback_enabled
        and settings.environment.strip().lower() != "production"
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    """本地开发登录入口。

    身份唯一来源是云购账号：生产环境该接口始终返回 404，客户端必须直接调用
    云购登录接口取得 token 后作为 Bearer 令牌访问本服务。
    """
    if not _dev_login_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="请使用云购账号登录")
    if payload.account != "demo" or payload.password != "demo1234":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误，请使用演示账号 demo / demo1234",
        )
    return LoginResponse(access_token=DEMO_ACCESS_TOKEN, user=DEMO_USER)


@router.get("/me", response_model=UserProfile)
def me(user: Annotated[UserProfile, Depends(require_session)]) -> UserProfile:
    return user
