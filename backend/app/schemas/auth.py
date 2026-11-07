from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    account: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=4, max_length=128)


class UserProfile(BaseModel):
    id: str
    name: str
    avatar_url: str | None = None
    role_name: str
    organization_id: str
    # 云购动作码（permissions.actions）原样保存，不在本地另立一套权限名。
    permissions: list[str]
    # 云购超级管理员：动作码已全量下发，这里保留以便显式短路判断。
    is_super: bool = False


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
