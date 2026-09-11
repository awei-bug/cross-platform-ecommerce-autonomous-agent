from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.schemas.auth import UserProfile
from app.services.mock_repository import DEMO_USER

DEMO_ACCESS_TOKEN = "demo-access-token"
bearer_scheme = HTTPBearer(auto_error=False)


def require_demo_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> UserProfile:
    if credentials is None or credentials.credentials != DEMO_ACCESS_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return DEMO_USER
