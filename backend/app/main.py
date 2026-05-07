from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.session import init_db
from app.routers import admin, auth, datasets, reports, users


def create_app() -> FastAPI:
    """Create the FastAPI application and register routes."""
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
    app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()
