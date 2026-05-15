from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.dataset import Dataset, DatasetRow, ModelRun
from app.models.user import User
from app.routers.dependencies import get_current_user, has_admin_permission
from app.schemas.dataset import DatasetDetail, DatasetSummary, ForecastRequest, ForecastResponse
from app.services.data_cleaner import (
    build_chart_options,
    build_recommendations,
    dataframe_from_records,
    dataframe_to_records,
    load_and_clean_excel,
)
from app.services.chart_interpreter import analyze_dataset_charts
from app.services.activity_logger import log_activity
from app.services.predictor import forecast_dataframe

router = APIRouter()


def _ensure_dataset_access(dataset: Dataset | None, user: User) -> Dataset:
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if not has_admin_permission(user) and dataset.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问该数据集")
    return dataset


def _detail_response(dataset: Dataset, db: Session) -> DatasetDetail:
    dataset_rows = (
        db.query(DatasetRow)
        .filter(DatasetRow.dataset_id == dataset.id)
        .order_by(DatasetRow.row_index.asc())
        .all()
    )
    charts_json = dataset.charts_json
    recommendations_json = dataset.recommendations_json
    if dataset_rows:
        df = dataframe_from_records([row.content_json for row in dataset_rows])
        chart_options = build_chart_options(df)
        if chart_options:
            charts_json = chart_options
            recommendations_json = build_recommendations(chart_options)

    return DatasetDetail(
        id=dataset.id,
        filename=dataset.filename,
        rows_count=dataset.rows_count,
        columns_count=dataset.columns_count,
        columns_json=dataset.columns_json,
        profile_json=dataset.profile_json,
        recommendations_json=recommendations_json,
        charts_json=charts_json,
        created_at=dataset.created_at,
        preview_rows=[row.content_json for row in dataset_rows[:30]],
    )


@router.post(
    "/upload",
    response_model=DatasetDetail,
    summary="上传并清洗数据集",
    description="上传 Excel 或文本表格文件，后端使用 pandas 进行字段规范化、类型识别、缺失值处理和业务值清洗，并返回图表推荐与数据预览。",
)
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DatasetDetail:
    """Upload spreadsheet-like data, clean it, save cleaned rows, and return chart recommendations."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".xlsx", ".xls", ".txt"}:
        raise HTTPException(status_code=400, detail="仅支持表格数据文件：.xlsx、.xls 或 .txt")

    stored_name = f"{uuid4().hex}{suffix}"
    file_path = settings.upload_dir / stored_name
    file_path.write_bytes(await file.read())

    try:
        cleaned_df, profile, recommendations, charts = load_and_clean_excel(file_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"数据文件解析或清洗失败：{exc}") from exc

    dataset = Dataset(
        owner_id=current_user.id,
        filename=file.filename or stored_name,
        sheet_name="Sheet1",
        rows_count=int(cleaned_df.shape[0]),
        columns_count=int(cleaned_df.shape[1]),
        columns_json=cleaned_df.columns.tolist(),
        profile_json=profile,
        recommendations_json=recommendations,
        charts_json=charts,
    )
    db.add(dataset)
    db.flush()

    for index, record in enumerate(dataframe_to_records(cleaned_df)):
        db.add(DatasetRow(dataset_id=dataset.id, row_index=index, content_json=record))

    log_activity(
        db,
        current_user,
        "dataset_upload",
        "上传并清洗数据集",
        f"{dataset.filename}，{dataset.rows_count} 行 {dataset.columns_count} 列",
        {"dataset_id": dataset.id},
    )
    db.commit()
    db.refresh(dataset)
    return _detail_response(dataset, db)


@router.get(
    "",
    response_model=list[DatasetSummary],
    summary="查询数据集列表",
    description="查询当前用户可访问的数据集。普通用户只能查看自己的数据集，管理员可以查看更多数据集。",
)
def list_datasets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DatasetSummary]:
    query = db.query(Dataset).order_by(Dataset.created_at.desc())
    if not has_admin_permission(current_user):
        query = query.filter(Dataset.owner_id == current_user.id)
    return [DatasetSummary.model_validate(item) for item in query.all()]


@router.get(
    "/{dataset_id}",
    response_model=DatasetDetail,
    summary="获取数据集详情",
    description="根据数据集编号获取清洗后的字段、行列数量、数据画像、图表配置、推荐说明和前 30 行预览数据。",
)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DatasetDetail:
    dataset = _ensure_dataset_access(db.get(Dataset, dataset_id), current_user)
    return _detail_response(dataset, db)


@router.get(
    "/{dataset_id}/chart-analysis",
    summary="生成图例分析",
    description="读取清洗后的数据和图表配置，按图表类型生成图文解析、系统发现、经营判断问题和 PyCaret/统计模型提示。",
)
def get_chart_analysis(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    dataset = _ensure_dataset_access(db.get(Dataset, dataset_id), current_user)
    rows = db.query(DatasetRow).filter(DatasetRow.dataset_id == dataset.id).order_by(DatasetRow.row_index.asc()).all()
    df = dataframe_from_records([row.content_json for row in rows])
    charts = build_chart_options(df) or dataset.charts_json
    result = analyze_dataset_charts(
        df=df,
        profile=dataset.profile_json,
        charts=charts,
        filename=dataset.filename,
        dataset_id=dataset.id,
    )
    log_activity(
        db,
        current_user,
        "chart_analysis",
        "生成图例分析",
        dataset.filename,
        {"dataset_id": dataset.id},
    )
    db.commit()
    return result


@router.post(
    "/{dataset_id}/forecast",
    response_model=ForecastResponse,
    summary="生成行情预测",
    description="对指定数据集执行自动预测。系统优先尝试 PyCaret 自动建模，并在不可用时回退到统计/机器学习预测流程。",
)
def create_forecast(
    dataset_id: int,
    payload: ForecastRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ForecastResponse:
    dataset = _ensure_dataset_access(db.get(Dataset, dataset_id), current_user)
    rows = db.query(DatasetRow).filter(DatasetRow.dataset_id == dataset.id).order_by(DatasetRow.row_index.asc()).all()
    df = dataframe_from_records([row.content_json for row in rows])
    try:
        result = forecast_dataframe(df, payload.periods, payload.target_column, payload.date_column)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    model_run = ModelRun(
        dataset_id=dataset.id,
        user_id=current_user.id,
        target_column=result["target_column"],
        date_column=result["date_column"],
        algorithm=result["algorithm"],
        metrics_json=result["metrics"],
        prediction_json=result["predictions"],
        summary=result["summary"],
    )
    db.add(model_run)
    log_activity(
        db,
        current_user,
        "forecast_create",
        "生成未来行情预测",
        f"{dataset.filename}，目标：{result['target_column']}，{payload.periods} 期",
        {"dataset_id": dataset.id},
    )
    db.commit()
    db.refresh(model_run)
    return ForecastResponse.model_validate(model_run)


@router.get(
    "/{dataset_id}/model-runs",
    response_model=list[ForecastResponse],
    summary="查询预测记录",
    description="查询指定数据集的历史预测任务，返回模型算法、评价指标、预测结果和预测摘要。",
)
def list_model_runs(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ForecastResponse]:
    dataset = _ensure_dataset_access(db.get(Dataset, dataset_id), current_user)
    runs = (
        db.query(ModelRun)
        .filter(ModelRun.dataset_id == dataset.id)
        .order_by(ModelRun.created_at.desc())
        .all()
    )
    return [ForecastResponse.model_validate(run) for run in runs]


@router.delete(
    "/{dataset_id}",
    summary="删除数据集",
    description="删除指定数据集及其相关清洗记录。普通用户只能删除自己的数据集。",
)
def delete_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    dataset = _ensure_dataset_access(db.get(Dataset, dataset_id), current_user)
    log_activity(
        db,
        current_user,
        "dataset_delete",
        "删除数据集",
        dataset.filename,
        {"dataset_id": dataset.id},
    )
    db.delete(dataset)
    db.commit()
    return {"message": "数据集已删除"}
