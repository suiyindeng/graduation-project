from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    avatar_url: str | None = None
    theme_preference: str = "arcaea"
    created_at: datetime

    class Config:
        from_attributes = True


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    confirm_password: str = Field(min_length=8, max_length=100)
    role: str = Field(default="user", pattern="^(user|admin)$")
    admin_code: str | None = None
    captcha_id: str
    captcha_code: str = Field(min_length=4, max_length=4)


class LoginRequest(BaseModel):
    account: str
    password: str
    captcha_id: str
    captcha_code: str = Field(min_length=4, max_length=4)


class PasswordResetCodeRequest(BaseModel):
    email: EmailStr
    captcha_id: str
    captcha_code: str = Field(min_length=4, max_length=4)


class PasswordResetCodeResponse(BaseModel):
    message: str
    expires_minutes: int
    dev_reset_code: str | None = None


class PasswordResetConfirmRequest(BaseModel):
    email: EmailStr
    reset_code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=100)
    confirm_password: str = Field(min_length=8, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserBase


class UserUpdateRequest(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=50)
    email: EmailStr | None = None
    theme_preference: str | None = Field(default=None, pattern="^(arcaea|rosmontis|skadi|module_disabled|seven_rebirth|forgotten_fenghua)$")


class AdminUserUpdateRequest(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=50)
    email: EmailStr | None = None
    theme_preference: str | None = Field(default=None, pattern="^(arcaea|rosmontis|skadi|module_disabled|seven_rebirth|forgotten_fenghua)$")
    is_active: bool | None = None


class SuperAdminUserUpdateRequest(AdminUserUpdateRequest):
    role: str | None = Field(default=None, pattern="^(user|admin)$")
