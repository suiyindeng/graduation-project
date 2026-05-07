from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Dataset(Base):
    """Excel upload after automatic cleaning and profiling."""

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rows_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    columns_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    columns_json: Mapped[list] = mapped_column(JSON, nullable=False)
    profile_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    recommendations_json: Mapped[list] = mapped_column(JSON, nullable=False)
    charts_json: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="datasets")
    rows = relationship("DatasetRow", back_populates="dataset", cascade="all, delete-orphan")
    model_runs = relationship("ModelRun", back_populates="dataset", cascade="all, delete-orphan")


class DatasetRow(Base):
    """A cleaned row stored as JSON to support flexible Excel columns."""

    __tablename__ = "dataset_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), nullable=False, index=True)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    dataset = relationship("Dataset", back_populates="rows")


class ModelRun(Base):
    """Forecast result generated from a cleaned dataset."""

    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    target_column: Mapped[str] = mapped_column(String(120), nullable=False)
    date_column: Mapped[str | None] = mapped_column(String(120), nullable=True)
    algorithm: Mapped[str] = mapped_column(String(120), nullable=False)
    metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    prediction_json: Mapped[list] = mapped_column(JSON, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    dataset = relationship("Dataset", back_populates="model_runs")
