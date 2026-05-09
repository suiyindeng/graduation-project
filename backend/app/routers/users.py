from pathlib import Path
from uuid import uuid4
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.activity import UserActivityLog
from app.models.dataset import Dataset, ModelRun
from app.models.user import User
from app.routers.dependencies import get_current_user
from app.schemas.auth import UserBase, UserUpdateRequest
from app.services.activity_logger import log_activity

router = APIRouter()


def _can_use_fenghua_theme(user: User) -> bool:
    return user.role == "super_admin" and user.username == "冴月麟"


def _activity_item(log: UserActivityLog) -> dict:
    return {
        "id": log.id,
        "action": log.action,
        "title": log.title,
        "detail": log.detail,
        "created_at": log.created_at,
    }


@router.get("/me", response_model=UserBase)
def me(current_user: User = Depends(get_current_user)) -> UserBase:
    return UserBase.model_validate(current_user)


@router.get("/me/stats")
def my_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return personal usage summary for the profile page."""
    dataset_query = db.query(Dataset).filter(Dataset.owner_id == current_user.id)
    dataset_count = dataset_query.count()
    cleaned_rows = dataset_query.with_entities(func.coalesce(func.sum(Dataset.rows_count), 0)).scalar()
    forecast_count = db.query(ModelRun).filter(ModelRun.user_id == current_user.id).count()
    last_dataset = dataset_query.order_by(Dataset.created_at.desc()).first()
    last_week = datetime.utcnow() - timedelta(days=7)
    recent_logins = (
        db.query(UserActivityLog)
        .filter(
            UserActivityLog.user_id == current_user.id,
            UserActivityLog.action == "login",
            UserActivityLog.created_at >= last_week,
        )
        .order_by(UserActivityLog.created_at.desc())
        .limit(20)
        .all()
    )
    recent_operations = (
        db.query(UserActivityLog)
        .filter(UserActivityLog.user_id == current_user.id, UserActivityLog.action != "login")
        .order_by(UserActivityLog.created_at.desc())
        .limit(30)
        .all()
    )
    operation_count_7d = (
        db.query(UserActivityLog)
        .filter(
            UserActivityLog.user_id == current_user.id,
            UserActivityLog.action != "login",
            UserActivityLog.created_at >= last_week,
        )
        .count()
    )
    operation_count_total = (
        db.query(UserActivityLog)
        .filter(UserActivityLog.user_id == current_user.id, UserActivityLog.action != "login")
        .count()
    )
    return {
        "dataset_count": dataset_count,
        "cleaned_rows": int(cleaned_rows or 0),
        "forecast_count": forecast_count,
        "last_dataset_at": last_dataset.created_at if last_dataset else None,
        "registered_at": current_user.created_at,
        "recent_logins": [_activity_item(log) for log in recent_logins],
        "recent_operations": [_activity_item(log) for log in recent_operations],
        "operation_count_7d": operation_count_7d,
        "operation_count_total": operation_count_total,
    }


@router.put("/me", response_model=UserBase)
def update_me(
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserBase:
    """Update personal profile and theme preference."""
    if current_user.role == "super_admin" and (payload.username or payload.email):
        raise HTTPException(status_code=403, detail="超级管理员账号名和邮箱不可在用户中心修改")

    if payload.username or payload.email:
        duplicate = (
            db.query(User)
            .filter(
                User.id != current_user.id,
                or_(User.username == payload.username, User.email == str(payload.email)),
            )
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=400, detail="用户名或邮箱已被使用")

    changed_items: list[str] = []
    if payload.username and payload.username != current_user.username:
        current_user.username = payload.username
        changed_items.append("用户名")
    if payload.email and str(payload.email) != current_user.email:
        current_user.email = str(payload.email)
        changed_items.append("邮箱")
    if payload.theme_preference == "forgotten_fenghua" and not _can_use_fenghua_theme(current_user):
        raise HTTPException(status_code=403, detail="遗忘的风华主题仅超级管理员冴月麟可用")
    if payload.theme_preference and payload.theme_preference != current_user.theme_preference:
        current_user.theme_preference = payload.theme_preference
        changed_items.append("默认主题")

    if changed_items:
        log_activity(db, current_user, "profile_update", "更新用户中心设置", "、".join(changed_items))

    db.commit()
    db.refresh(current_user)
    return UserBase.model_validate(current_user)


@router.post("/avatar", response_model=UserBase)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserBase:
    """Store a custom avatar under backend/storage/avatars."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="头像仅支持 jpg、png、webp")

    filename = f"{uuid4().hex}{suffix}"
    target_path = settings.avatar_dir / filename
    target_path.write_bytes(await file.read())

    current_user.avatar_url = f"/static/avatars/{filename}"
    log_activity(db, current_user, "avatar_update", "更换头像", file.filename or filename)
    db.commit()
    db.refresh(current_user)
    return UserBase.model_validate(current_user)
