from typing import Any

from sqlalchemy.orm import Session

from app.models.activity import UserActivityLog
from app.models.user import User


def log_activity(
    db: Session,
    user: User,
    action: str,
    title: str,
    detail: str | None = None,
    meta: dict[str, Any] | None = None,
) -> UserActivityLog:
    """Add one user operation log to the current database transaction."""
    log = UserActivityLog(
        user_id=user.id,
        action=action,
        title=title,
        detail=detail,
        meta_json=meta or {},
    )
    db.add(log)
    return log
