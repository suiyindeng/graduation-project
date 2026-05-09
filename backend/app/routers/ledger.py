from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.dataset import Dataset, DatasetRow
from app.models.ledger import LedgerField, LedgerRecord
from app.models.user import User
from app.routers.dependencies import get_current_user
from app.schemas.dataset import DatasetDetail
from app.schemas.ledger import (
    LedgerDatasetCreate,
    LedgerFieldCreate,
    LedgerFieldResponse,
    LedgerGroupedDatasetCreate,
    LedgerRecordCreate,
    LedgerRecordResponse,
)
from app.services.activity_logger import log_activity
from app.services.data_cleaner import (
    build_chart_options,
    build_recommendations,
    dataframe_from_records,
    dataframe_to_records,
    detect_columns,
    pick_date_column,
    pick_target_column,
)

router = APIRouter()

SYSTEM_FIELDS = [
    {"name": "日期", "field_type": "date"},
    {"name": "事项", "field_type": "text"},
    {"name": "收入", "field_type": "number"},
    {"name": "支出", "field_type": "number"},
    {"name": "金额", "field_type": "number"},
    {"name": "分类", "field_type": "text"},
    {"name": "备注", "field_type": "text"},
]


def _clean_field_name(name: str) -> str:
    return " ".join(name.strip().split())


def _records_for_user(db: Session, user: User) -> list[LedgerRecord]:
    return (
        db.query(LedgerRecord)
        .filter(LedgerRecord.owner_id == user.id)
        .order_by(LedgerRecord.created_at.desc())
        .all()
    )


def _ledger_dataframe(records: list[LedgerRecord]) -> pd.DataFrame:
    if not records:
        raise HTTPException(status_code=400, detail="没有可用的记账记录")
    df = dataframe_from_records([record.content_json for record in records])
    df = df.dropna(how="all").reset_index(drop=True)
    if df.empty:
        raise HTTPException(status_code=400, detail="记账记录为空")
    return df


def _group_ledger_dataframe(records: list[LedgerRecord], group_field: str) -> pd.DataFrame:
    df = _ledger_dataframe(records)
    group_field = _clean_field_name(group_field)
    if group_field not in df.columns:
        raise HTTPException(status_code=400, detail="请选择记录中存在的整合词条字段")

    df[group_field] = df[group_field].fillna("").astype(str).str.strip()
    df = df[df[group_field] != ""].copy()
    if df.empty:
        raise HTTPException(status_code=400, detail="该字段没有可用于整合的有效词条")

    grouped_rows: list[dict[str, Any]] = []
    for group_value, group_df in df.groupby(group_field, dropna=False, sort=False):
        row: dict[str, Any] = {group_field: group_value, "记录数量": int(group_df.shape[0])}
        for column in df.columns:
            if column == group_field:
                continue
            numeric_values = pd.to_numeric(group_df[column], errors="coerce")
            if numeric_values.notna().any():
                row[column] = float(numeric_values.sum())
                continue
            values = [
                str(value).strip()
                for value in group_df[column].dropna().tolist()
                if str(value).strip()
            ]
            unique_values = list(dict.fromkeys(values))
            row[column] = "、".join(unique_values[:8])
        grouped_rows.append(row)

    return pd.DataFrame(grouped_rows)


def _dataset_detail_from_dataframe(
    db: Session,
    current_user: User,
    df: pd.DataFrame,
    filename: str,
    sheet_name: str,
    log_title: str,
    log_action: str,
    log_detail: str,
) -> DatasetDetail:
    profile = _profile_from_dataframe(df)
    charts = build_chart_options(df)
    recommendations = build_recommendations(charts)

    dataset = Dataset(
        owner_id=current_user.id,
        filename=f"{filename or '记账数据集'}.xlsx",
        sheet_name=sheet_name,
        rows_count=int(df.shape[0]),
        columns_count=int(df.shape[1]),
        columns_json=df.columns.tolist(),
        profile_json=profile,
        recommendations_json=recommendations,
        charts_json=charts,
    )
    db.add(dataset)
    db.flush()

    rows: list[DatasetRow] = []
    for index, record in enumerate(dataframe_to_records(df)):
        row = DatasetRow(dataset_id=dataset.id, row_index=index, content_json=record)
        db.add(row)
        rows.append(row)
    log_activity(
        db,
        current_user,
        log_action,
        log_title,
        log_detail,
        {"dataset_id": dataset.id},
    )
    db.commit()
    db.refresh(dataset)

    return DatasetDetail(
        id=dataset.id,
        filename=dataset.filename,
        rows_count=dataset.rows_count,
        columns_count=dataset.columns_count,
        columns_json=dataset.columns_json,
        profile_json=dataset.profile_json,
        recommendations_json=dataset.recommendations_json,
        charts_json=dataset.charts_json,
        created_at=dataset.created_at,
        preview_rows=[row.content_json for row in rows[:30]],
    )


def _profile_from_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    detected = detect_columns(df)
    return {
        "original_rows": int(df.shape[0]),
        "original_columns": int(df.shape[1]),
        "cleaned_rows": int(df.shape[0]),
        "cleaned_columns": int(df.shape[1]),
        "duplicates_removed": 0,
        "missing_before": {column: int(df[column].isna().sum()) for column in df.columns},
        "filled_missing": {},
        "business_cleaning": {
            "price_column": None,
            "quantity_column": None,
            "amount_columns": [],
            "discount_column": None,
            "negative_values_corrected": 0,
            "discounts_normalized": 0,
            "amounts_recalculated": 0,
        },
        "numeric_columns": detected["numeric_columns"],
        "date_columns": detected["date_columns"],
        "categorical_columns": detected["categorical_columns"],
        "target_column": pick_target_column(df),
        "date_column": pick_date_column(df),
        "source_format": "ledger",
    }


def _records_from_payload(db: Session, current_user: User, record_ids: list[int] | None) -> list[LedgerRecord]:
    query = db.query(LedgerRecord).filter(LedgerRecord.owner_id == current_user.id)
    if record_ids:
        query = query.filter(LedgerRecord.id.in_(record_ids))
    return query.order_by(LedgerRecord.created_at.asc()).all()


def _excel_cell_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value.item() if hasattr(value, "item") else value


def _clean_record_content(content_json: dict[str, Any]) -> dict[str, Any]:
    content = {str(key).strip(): value for key, value in content_json.items() if str(key).strip()}
    return {
        key: value
        for key, value in content.items()
        if value is not None and str(value).strip() != ""
    }


@router.get("/fields")
def list_fields(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[dict[str, Any]]]:
    custom_fields = (
        db.query(LedgerField)
        .filter(LedgerField.owner_id == current_user.id)
        .order_by(LedgerField.created_at.asc())
        .all()
    )
    seen = {field["name"] for field in SYSTEM_FIELDS}
    dataset_fields: list[dict[str, str]] = []
    for dataset in current_user.datasets:
        for column in dataset.columns_json or []:
            name = str(column)
            if name in seen:
                continue
            seen.add(name)
            dataset_fields.append({"name": name, "field_type": "text"})

    return {
        "system": SYSTEM_FIELDS,
        "dataset": dataset_fields,
        "custom": [LedgerFieldResponse.model_validate(field).model_dump(mode="json") for field in custom_fields],
    }


@router.post("/fields", response_model=LedgerFieldResponse)
def create_field(
    payload: LedgerFieldCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerFieldResponse:
    name = _clean_field_name(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="字段名不能为空")
    exists = (
        db.query(LedgerField)
        .filter(LedgerField.owner_id == current_user.id, LedgerField.name == name)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="该自定义字段已存在")

    field = LedgerField(owner_id=current_user.id, name=name, field_type=payload.field_type)
    db.add(field)
    log_activity(db, current_user, "ledger_field_create", "新增记账字段", f"{name}（{payload.field_type}）")
    db.commit()
    db.refresh(field)
    return LedgerFieldResponse.model_validate(field)


@router.delete("/fields/{field_id}")
def delete_field(
    field_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    field = db.get(LedgerField, field_id)
    if not field or field.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="自定义字段不存在")

    for record in _records_for_user(db, current_user):
        content = dict(record.content_json or {})
        if field.name in content:
            content.pop(field.name, None)
            record.content_json = content
    log_activity(db, current_user, "ledger_field_delete", "删除记账字段", field.name)
    db.delete(field)
    db.commit()
    return {"message": "自定义字段已删除"}


@router.get("/records", response_model=list[LedgerRecordResponse])
def list_records(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LedgerRecordResponse]:
    return [LedgerRecordResponse.model_validate(record) for record in _records_for_user(db, current_user)]


@router.post("/import", response_model=list[LedgerRecordResponse])
async def import_records_from_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LedgerRecordResponse]:
    suffix = (file.filename or "").lower().split(".")[-1]
    if suffix not in {"xlsx", "xls"}:
        raise HTTPException(status_code=400, detail="记账导入仅支持 .xlsx 或 .xls 文件")

    content = await file.read()
    try:
        df = pd.read_excel(BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Excel 读取失败：{exc}") from exc

    df = df.dropna(how="all")
    if df.empty:
        raise HTTPException(status_code=400, detail="Excel 中没有可导入的记录")

    df.columns = [_clean_field_name(str(column)) for column in df.columns]
    imported_records: list[LedgerRecord] = []
    for raw_record in df.to_dict(orient="records"):
        record_content = {
            key: _excel_cell_value(value)
            for key, value in raw_record.items()
            if key and _excel_cell_value(value) is not None and str(_excel_cell_value(value)).strip() != ""
        }
        if not record_content:
            continue
        record = LedgerRecord(owner_id=current_user.id, content_json=record_content)
        db.add(record)
        imported_records.append(record)

    if not imported_records:
        raise HTTPException(status_code=400, detail="Excel 中没有有效记录")

    log_activity(
        db,
        current_user,
        "ledger_import",
        "导入记账 Excel",
        f"{file.filename or 'Excel 文件'}，{len(imported_records)} 条记录",
    )
    db.commit()
    for record in imported_records:
        db.refresh(record)
    return [LedgerRecordResponse.model_validate(record) for record in imported_records]


@router.post("/records", response_model=LedgerRecordResponse)
def create_record(
    payload: LedgerRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerRecordResponse:
    content = _clean_record_content(payload.content_json)
    if not content:
        raise HTTPException(status_code=400, detail="请至少填写一个字段")
    record = LedgerRecord(owner_id=current_user.id, content_json=content)
    db.add(record)
    log_activity(db, current_user, "ledger_record_create", "保存记账记录", f"{len(content)} 个字段")
    db.commit()
    db.refresh(record)
    return LedgerRecordResponse.model_validate(record)


@router.put("/records/{record_id}", response_model=LedgerRecordResponse)
def update_record(
    record_id: int,
    payload: LedgerRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerRecordResponse:
    record = db.get(LedgerRecord, record_id)
    if not record or record.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="记账记录不存在")

    content = _clean_record_content(payload.content_json)
    if not content:
        raise HTTPException(status_code=400, detail="请至少保留一个字段")

    record.content_json = content
    log_activity(
        db,
        current_user,
        "ledger_record_update",
        "修改记账记录",
        f"记录 ID：{record.id}，{len(content)} 个字段",
    )
    db.commit()
    db.refresh(record)
    return LedgerRecordResponse.model_validate(record)


@router.delete("/records/{record_id}")
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    record = db.get(LedgerRecord, record_id)
    if not record or record.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="记账记录不存在")
    log_activity(db, current_user, "ledger_record_delete", "删除记账记录", f"记录 ID：{record.id}")
    db.delete(record)
    db.commit()
    return {"message": "记账记录已删除"}


@router.get("/export")
def export_records(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    df = _ledger_dataframe(_records_for_user(db, current_user))
    log_activity(db, current_user, "ledger_export", "导出记账 Excel", f"{df.shape[0]} 条记录")
    db.commit()
    stream = BytesIO()
    with pd.ExcelWriter(stream, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="记账记录")
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ledger-records.xlsx"},
    )


@router.post("/to-dataset", response_model=DatasetDetail)
def create_dataset_from_records(
    payload: LedgerDatasetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DatasetDetail:
    records = _records_from_payload(db, current_user, payload.record_ids)
    df = _ledger_dataframe(records)
    return _dataset_detail_from_dataframe(
        db=db,
        current_user=current_user,
        df=df,
        filename=payload.filename,
        sheet_name="记账记录",
        log_title="记账记录转为数据集",
        log_action="ledger_to_dataset",
        log_detail=f"{payload.filename or '记账数据集'}，{df.shape[0]} 行 {df.shape[1]} 列",
    )


@router.post("/group-preview")
def preview_grouped_records(
    payload: LedgerGroupedDatasetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    records = _records_from_payload(db, current_user, payload.record_ids)
    df = _group_ledger_dataframe(records, payload.group_field)
    return {
        "rows_count": int(df.shape[0]),
        "columns": df.columns.tolist(),
        "preview_rows": dataframe_to_records(df)[:30],
    }


@router.post("/group-export")
def export_grouped_records(
    payload: LedgerGroupedDatasetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    records = _records_from_payload(db, current_user, payload.record_ids)
    df = _group_ledger_dataframe(records, payload.group_field)
    log_activity(
        db,
        current_user,
        "ledger_group_export",
        "导出整合记账 Excel",
        f"按 {payload.group_field} 整合为 {df.shape[0]} 条词条",
    )
    db.commit()
    stream = BytesIO()
    with pd.ExcelWriter(stream, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=f"按{payload.group_field}整合")
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=grouped-ledger-records.xlsx"},
    )


@router.post("/group-to-dataset", response_model=DatasetDetail)
def create_grouped_dataset_from_records(
    payload: LedgerGroupedDatasetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DatasetDetail:
    records = _records_from_payload(db, current_user, payload.record_ids)
    df = _group_ledger_dataframe(records, payload.group_field)
    return _dataset_detail_from_dataframe(
        db=db,
        current_user=current_user,
        df=df,
        filename=payload.filename,
        sheet_name=f"按{payload.group_field}整合",
        log_title="整合记账记录为数据集",
        log_action="ledger_group_to_dataset",
        log_detail=f"按 {payload.group_field} 整合为 {df.shape[0]} 条词条",
    )
