from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User


ADMIN_ROLES = {"admin", "super_admin"}


def has_admin_permission(user: User) -> bool:
    return user.role in ADMIN_ROLES


def has_super_admin_permission(user: User) -> bool:
    return user.role == "super_admin"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Read the bearer token and return the authenticated user."""
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期")

    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not has_admin_permission(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if not has_super_admin_permission(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要超级管理员权限")
    return current_user
