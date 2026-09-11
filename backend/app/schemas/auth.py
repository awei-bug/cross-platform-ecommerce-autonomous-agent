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
    permissions: list[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
