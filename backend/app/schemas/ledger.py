from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


LedgerFieldType = Literal["text", "number", "date"]


class LedgerFieldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    field_type: LedgerFieldType = "text"


class LedgerFieldResponse(BaseModel):
    id: int
    name: str
    field_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class LedgerRecordCreate(BaseModel):
    content_json: dict[str, Any] = Field(default_factory=dict)


class LedgerRecordResponse(BaseModel):
    id: int
    content_json: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class LedgerDatasetCreate(BaseModel):
    record_ids: list[int] | None = None
    filename: str = Field(default="记账数据集", max_length=120)


class LedgerGroupedDatasetCreate(LedgerDatasetCreate):
    group_field: str = Field(min_length=1, max_length=80)
