from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create database tables declared in app.models."""
    from app.models import activity, dataset, ledger, user  # noqa: F401
    from app.core.security import hash_password
    from app.models.user import User

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        super_admin = db.query(User).filter(User.username == "冴月麟").first()
        if super_admin:
            super_admin.email = "superadmin@local.system"
            super_admin.password_hash = hash_password("FatalisHikari")
            super_admin.role = "super_admin"
            super_admin.is_active = True
        else:
            db.add(
                User(
                    username="冴月麟",
                    email="superadmin@local.system",
                    password_hash=hash_password("FatalisHikari"),
                    role="super_admin",
                    is_active=True,
                )
            )
        db.commit()
