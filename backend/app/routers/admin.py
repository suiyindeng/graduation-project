from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.dataset import Dataset
from app.models.user import User
from app.routers.dependencies import require_admin

router = APIRouter()


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
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
        }
        for user in users
    ]


@router.get("/datasets")
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
