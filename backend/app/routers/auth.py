import html
import random
import secrets
import string
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    PasswordResetCodeRequest,
    PasswordResetCodeResponse,
    PasswordResetConfirmRequest,
    RegisterRequest,
    TokenResponse,
    UserBase,
)
from app.services.activity_logger import log_activity

router = APIRouter()
CAPTCHA_TTL_MINUTES = 5
CAPTCHA_ALPHABET = string.ascii_letters + string.digits
CAPTCHA_STORE: dict[str, tuple[str, datetime]] = {}
RESET_CODE_TTL_MINUTES = 10
RESET_CODE_STORE: dict[str, tuple[str, datetime]] = {}


def _cleanup_captchas() -> None:
    now = datetime.utcnow()
    expired_keys = [key for key, (_, expires_at) in CAPTCHA_STORE.items() if expires_at < now]
    for key in expired_keys:
        CAPTCHA_STORE.pop(key, None)

    expired_reset_keys = [key for key, (_, expires_at) in RESET_CODE_STORE.items() if expires_at < now]
    for key in expired_reset_keys:
        RESET_CODE_STORE.pop(key, None)


def _build_captcha_svg(code: str) -> str:
    """Build a lightweight SVG captcha image with four mixed letters/numbers."""
    escaped = html.escape(code)
    noise_lines = []
    for _ in range(5):
        x1, y1 = random.randint(2, 88), random.randint(8, 34)
        x2, y2 = random.randint(2, 88), random.randint(8, 34)
        color = random.choice(["#76b9ff", "#b55cff", "#8fd8ff", "#9aa8ff"])
        noise_lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1" opacity="0.45" />'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="40" viewBox="0 0 96 40">'
        '<rect width="96" height="40" rx="8" fill="transparent"/>'
        f'{"".join(noise_lines)}'
        f'<text x="48" y="27" text-anchor="middle" font-family="Consolas, Arial, sans-serif" '
        f'font-size="22" font-weight="700" letter-spacing="3" fill="#17324d">{escaped}</text>'
        '</svg>'
    )


def _verify_captcha(captcha_id: str, captcha_code: str) -> None:
    _cleanup_captchas()
    stored = CAPTCHA_STORE.pop(captcha_id, None)
    if not stored:
        raise HTTPException(status_code=400, detail="验证码已过期，请刷新后重试")
    expected, expires_at = stored
    if expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="验证码已过期，请刷新后重试")
    if expected.lower() != captcha_code.lower():
        raise HTTPException(status_code=400, detail="验证码不正确")


def _validate_password_strength(password: str) -> None:
    """Keep backend password rules aligned with the Vue registration form."""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="密码至少需要 8 位")
    if not any(char.isalpha() for char in password):
        raise HTTPException(status_code=400, detail="密码需要包含英文字母")
    if not any(char.isdigit() for char in password):
        raise HTTPException(status_code=400, detail="密码需要包含数字")


@router.get("/captcha")
def create_captcha() -> dict[str, str]:
    """Generate a short captcha for login and registration."""
    _cleanup_captchas()
    captcha_id = secrets.token_urlsafe(16)
    code = "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(4))
    CAPTCHA_STORE[captcha_id] = (code, datetime.utcnow() + timedelta(minutes=CAPTCHA_TTL_MINUTES))
    return {"captcha_id": captcha_id, "image_url": f"/api/auth/captcha/{captcha_id}.svg"}


@router.get("/captcha/{captcha_id}.svg")
def get_captcha_image(captcha_id: str) -> Response:
    _cleanup_captchas()
    stored = CAPTCHA_STORE.get(captcha_id)
    if not stored:
        raise HTTPException(status_code=404, detail="验证码已过期")
    code, expires_at = stored
    if expires_at < datetime.utcnow():
        CAPTCHA_STORE.pop(captcha_id, None)
        raise HTTPException(status_code=404, detail="验证码已过期")
    return Response(
        content=_build_captcha_svg(code),
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Register a normal user or administrator."""
    _verify_captcha(payload.captcha_id, payload.captcha_code)
    _validate_password_strength(payload.password)

    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="两次输入的密码不一致")

    if payload.role == "admin" and payload.admin_code != settings.admin_register_code:
        raise HTTPException(status_code=400, detail="管理员注册码不正确")

    existing = db.query(User).filter(or_(User.username == payload.username, User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

    user = User(
        username=payload.username,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_activity(db, user, "register", "注册账号", f"创建{ '管理员' if user.role == 'admin' else '普通用户' }账号")
    db.commit()

    token = create_access_token(str(user.id), user.role)
    return TokenResponse(access_token=token, user=UserBase.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Validate account credentials and return a signed token."""
    _verify_captcha(payload.captcha_id, payload.captcha_code)
    user = db.query(User).filter(or_(User.username == payload.account, User.email == payload.account)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已停用")

    log_activity(db, user, "login", "登录系统", "账号密码验证通过")
    db.commit()

    token = create_access_token(str(user.id), user.role)
    return TokenResponse(access_token=token, user=UserBase.model_validate(user))


@router.post("/password-reset/code", response_model=PasswordResetCodeResponse)
def request_password_reset_code(
    payload: PasswordResetCodeRequest,
    db: Session = Depends(get_db),
) -> PasswordResetCodeResponse:
    """Verify captcha and generate a password reset code for the account email."""
    _verify_captcha(payload.captcha_id, payload.captcha_code)
    user = db.query(User).filter(User.email == str(payload.email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="该邮箱未注册")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户已停用")

    reset_code = "".join(secrets.choice(string.digits) for _ in range(6))
    RESET_CODE_STORE[str(payload.email).lower()] = (
        reset_code,
        datetime.utcnow() + timedelta(minutes=RESET_CODE_TTL_MINUTES),
    )
    return PasswordResetCodeResponse(
        message="重置验证码已生成。当前为开发模式，验证码直接显示在页面中。",
        expires_minutes=RESET_CODE_TTL_MINUTES,
        dev_reset_code=reset_code,
    )


@router.post("/password-reset/confirm")
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Reset password after validating the email reset code."""
    _cleanup_captchas()
    email = str(payload.email).lower()
    stored = RESET_CODE_STORE.pop(email, None)
    if not stored:
        raise HTTPException(status_code=400, detail="重置验证码已过期，请重新获取")

    expected_code, expires_at = stored
    if expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="重置验证码已过期，请重新获取")
    if expected_code != payload.reset_code:
        raise HTTPException(status_code=400, detail="重置验证码不正确")
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="两次输入的新密码不一致")

    _validate_password_strength(payload.new_password)
    user = db.query(User).filter(User.email == str(payload.email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="该邮箱未注册")

    user.password_hash = hash_password(payload.new_password)
    log_activity(db, user, "password_reset", "重置密码", "通过重置验证码修改密码")
    db.commit()
    return {"message": "密码已重置，请返回登录页重新登录"}
