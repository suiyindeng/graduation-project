from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Centralized application configuration loaded from .env."""

    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", env_file_encoding="utf-8")

    app_name: str = "Automatic Data Visualization System"
    app_env: str = "development"
    secret_key: str = "change-this-secret-key"
    access_token_expire_minutes: int = 1440
    admin_register_code: str = "FatalisHikari"
    database_url: str = (
        "mysql+pymysql://visual_user:visual_pass@127.0.0.1:3306/"
        "auto_visualization?charset=utf8mb4"
    )
    cors_origins_raw: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173",
        alias="CORS_ORIGINS",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def storage_dir(self) -> Path:
        return ROOT_DIR / "storage"

    @property
    def upload_dir(self) -> Path:
        path = self.storage_dir / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def report_dir(self) -> Path:
        path = self.storage_dir / "reports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def avatar_dir(self) -> Path:
        path = self.storage_dir / "avatars"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def static_dir(self) -> str:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        return str(self.storage_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
