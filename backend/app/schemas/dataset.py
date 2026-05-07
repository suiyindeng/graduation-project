from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DatasetSummary(BaseModel):
    id: int
    filename: str
    rows_count: int
    columns_count: int
    columns_json: list[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DatasetDetail(DatasetSummary):
    profile_json: dict[str, Any]
    recommendations_json: list[dict[str, Any]]
    charts_json: list[dict[str, Any]]
    preview_rows: list[dict[str, Any]]


class ForecastRequest(BaseModel):
    periods: int = Field(default=6, ge=1, le=24)
    target_column: str | None = None
    date_column: str | None = None


class ForecastResponse(BaseModel):
    id: int
    target_column: str
    date_column: str | None
    algorithm: str
    metrics_json: dict[str, Any]
    prediction_json: list[dict[str, Any]]
    summary: str
    created_at: datetime

    class Config:
        from_attributes = True
