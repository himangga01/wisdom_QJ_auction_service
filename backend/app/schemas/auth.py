from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.analysis import ApiSchema

UserRole = Literal["admin", "member"]


class BootstrapStatus(ApiSchema):
    bootstrap_required: bool


class Credentials(ApiSchema):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)


class BootstrapRequest(Credentials):
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(Credentials):
    pass


class UserResponse(ApiSchema):
    id: UUID
    email: str
    display_name: str
    role: UserRole


class AuthResponse(ApiSchema):
    user: UserResponse
    expires_at: datetime


class ChangePasswordRequest(ApiSchema):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class AdminUserResponse(UserResponse):
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AdminUserPage(ApiSchema):
    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AdminUserCreate(BootstrapRequest):
    role: UserRole = "member"


class AdminUserPatch(ApiSchema):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("display_name")
    @classmethod
    def reject_blank_display_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("표시 이름이 필요합니다.")
        return value


class TemporaryPasswordRequest(ApiSchema):
    password: str = Field(min_length=12, max_length=128)


class TemporaryPasswordResponse(ApiSchema):
    user_id: UUID
    sessions_revoked: bool = True

