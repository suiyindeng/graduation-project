from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.dataset import Dataset, ModelRun
from app.models.user import User
from app.routers.dependencies import require_admin, require_super_admin
from app.schemas.auth import AdminUserUpdateRequest, SuperAdminUserUpdateRequest, UserBase

router = APIRouter()


def _role_label(role: str) -> str:
    return {"super_admin": "超级管理员", "admin": "管理员", "user": "普通用户"}.get(role, role)


def _can_view_user(current_user: User, target_user: User) -> bool:
    if current_user.role == "super_admin":
        return True
    return target_user.role == "user"


def _ensure_editable_user(current_user: User, target_user: User) -> None:
    if target_user.role == "super_admin":
        raise HTTPException(status_code=403, detail="无权限查看或修改超级管理员信息")
    if current_user.role == "admin" and target_user.role != "user":
        raise HTTPException(status_code=403, detail="管理员只能修改普通用户")


def _can_use_fenghua_theme(user: User) -> bool:
    return user.role == "super_admin" and user.username == "冴月麟"


def _apply_user_update(target_user: User, payload: AdminUserUpdateRequest) -> None:
    if payload.username is not None:
        target_user.username = payload.username
    if payload.email is not None:
        target_user.email = str(payload.email)
    if payload.theme_preference is not None:
        target_user.theme_preference = payload.theme_preference
    if payload.is_active is not None:
        target_user.is_active = payload.is_active


@router.get(
    "/users",
    summary="管理端查询用户列表",
    description="管理员查询系统用户列表。超级管理员可查看全部用户，普通管理员只能查看普通用户。",
)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[dict]:
    """Administrator view of registered users."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "theme_preference": user.theme_preference,
            "created_at": user.created_at,
            "role_label": _role_label(user.role),
        }
        for user in users
        if _can_view_user(current_user, user)
    ]


@router.put(
    "/users/{user_id}",
    response_model=UserBase,
    summary="管理端修改用户资料",
    description="管理员修改普通用户资料和账号状态，但不能修改超级管理员信息。",
)
def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> UserBase:
    """Administrators can edit normal users, but never super administrators."""
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    _ensure_editable_user(current_user, target_user)

    if payload.username is not None or payload.email is not None:
        checks = []
        if payload.username is not None:
            checks.append(User.username == payload.username)
        if payload.email is not None:
            checks.append(User.email == str(payload.email))
        duplicate = (
            db.query(User)
            .filter(User.id != target_user.id, or_(*checks))
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=400, detail="用户名或邮箱已被使用")

    if payload.theme_preference == "forgotten_fenghua" and not _can_use_fenghua_theme(target_user):
        raise HTTPException(status_code=403, detail="遗忘的风华主题仅超级管理员冴月麟可用")
    _apply_user_update(target_user, payload)
    db.commit()
    db.refresh(target_user)
    return UserBase.model_validate(target_user)


@router.put(
    "/users/{user_id}/role",
    response_model=UserBase,
    summary="超级管理员修改用户角色",
    description="仅超级管理员可提升普通用户为管理员，或调整管理员角色及资料。",
)
def update_user_role(
    user_id: int,
    payload: SuperAdminUserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> UserBase:
    """Only the super administrator can promote users or demote administrators."""
    if current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="需要超级管理员权限")

    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target_user.role == "super_admin":
        raise HTTPException(status_code=403, detail="超级管理员信息不可修改")

    if payload.username is not None or payload.email is not None:
        checks = []
        if payload.username is not None:
            checks.append(User.username == payload.username)
        if payload.email is not None:
            checks.append(User.email == str(payload.email))
        duplicate = (
            db.query(User)
            .filter(User.id != target_user.id, or_(*checks))
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=400, detail="用户名或邮箱已被使用")

    if payload.theme_preference == "forgotten_fenghua" and not _can_use_fenghua_theme(target_user):
        raise HTTPException(status_code=403, detail="遗忘的风华主题仅超级管理员冴月麟可用")
    _apply_user_update(target_user, payload)
    if payload.role is not None:
        target_user.role = payload.role
    db.commit()
    db.refresh(target_user)
    return UserBase.model_validate(target_user)


@router.get(
    "/datasets",
    summary="管理端查询全部数据集",
    description="管理员查询系统内已上传的数据集列表，包括所属用户、文件名、行列数量和创建时间。",
)
def list_all_datasets(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    """Administrator view of all uploaded datasets."""
    datasets = db.query(Dataset).order_by(Dataset.created_at.desc()).all()
    return [
        {
            "id": dataset.id,
            "owner_id": dataset.owner_id,
            "filename": dataset.filename,
            "rows_count": dataset.rows_count,
            "columns_count": dataset.columns_count,
            "created_at": dataset.created_at,
        }
        for dataset in datasets
    ]


def _range_filters(column, date_from: date | None, date_to: date | None) -> list:
    filters = []
    if date_from:
        filters.append(column >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        filters.append(column < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    return filters


@router.get(
    "/stats",
    summary="查询系统数据统计",
    description="超级管理员查询系统总用户数、数据集数量、清洗行数、预测次数、用户使用明细和近 7 日趋势。",
)
def system_stats(
    keyword: str | None = Query(default=None, alias="q"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
) -> dict:
    """Advanced usage statistics for the super administrator."""
    dataset_filters = _range_filters(Dataset.created_at, date_from, date_to)
    model_filters = _range_filters(ModelRun.created_at, date_from, date_to)

    today = datetime.utcnow().date()
    recent_start_at = datetime.combine(today - timedelta(days=6), datetime.min.time())
    recent_datasets = db.query(Dataset).filter(Dataset.created_at >= recent_start_at).all()

    daily: dict[str, dict[str, int]] = {}
    for offset in range(7):
        key = (today - timedelta(days=6 - offset)).isoformat()
        daily[key] = {"datasets": 0, "rows": 0}

    for dataset in recent_datasets:
        key = dataset.created_at.date().isoformat()
        if key not in daily:
            daily[key] = {"datasets": 0, "rows": 0}
        daily[key]["datasets"] += 1
        daily[key]["rows"] += dataset.rows_count

    user_query = db.query(User)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        user_query = user_query.filter(or_(User.username.like(pattern), User.email.like(pattern), User.role.like(pattern)))
    users = user_query.order_by(User.created_at.desc()).all()

    user_usage = []
    for user in users:
        user_dataset_query = db.query(Dataset).filter(Dataset.owner_id == user.id, *dataset_filters)
        user_model_query = db.query(ModelRun).filter(ModelRun.user_id == user.id, *model_filters)
        dataset_count = user_dataset_query.count()
        cleaned_rows = user_dataset_query.with_entities(func.coalesce(func.sum(Dataset.rows_count), 0)).scalar()
        forecast_count = user_model_query.count()
        last_dataset = user_dataset_query.order_by(Dataset.created_at.desc()).first()
        user_usage.append(
            {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "role_label": _role_label(user.role),
                "is_active": user.is_active,
                "dataset_count": dataset_count,
                "cleaned_rows": int(cleaned_rows or 0),
                "forecast_count": forecast_count,
                "last_dataset_at": last_dataset.created_at if last_dataset else None,
            }
        )

    total_users = db.query(User).count()
    total_datasets = db.query(Dataset).filter(*dataset_filters).count()
    total_rows = db.query(func.coalesce(func.sum(Dataset.rows_count), 0)).filter(*dataset_filters).scalar()
    total_forecasts = db.query(ModelRun).filter(*model_filters).count()

    return {
        "total_users": total_users,
        "total_datasets": total_datasets,
        "total_cleaned_rows": int(total_rows or 0),
        "total_forecasts": total_forecasts,
        "user_usage": user_usage,
        "recent_days": [
            {"date": date, "datasets": values["datasets"], "rows": values["rows"]}
            for date, values in daily.items()
        ],
    }
