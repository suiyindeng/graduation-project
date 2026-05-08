from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.dataset import Dataset, DatasetRow, ModelRun
from app.models.user import User
from app.routers.dependencies import get_current_user, has_admin_permission
from app.schemas.report import ExportReportRequest
from app.services.report_exporter import export_word_report

router = APIRouter()


def _check_dataset(dataset: Dataset | None, user: User) -> Dataset:
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if not has_admin_permission(user) and dataset.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权导出该数据集")
    return dataset


@router.post("/export")
def export_report(
    payload: ExportReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Export chart screenshots and forecast result into a Word document."""
    dataset = _check_dataset(db.get(Dataset, payload.dataset_id), current_user)
    model_run = None
    if payload.model_run_id:
        model_run = db.get(ModelRun, payload.model_run_id)
        if not model_run or model_run.dataset_id != dataset.id:
            raise HTTPException(status_code=404, detail="预测记录不存在")

    rows = db.query(DatasetRow).filter(DatasetRow.dataset_id == dataset.id).order_by(DatasetRow.row_index.asc()).limit(20).all()
    report_path = export_word_report(
        dataset=dataset,
        rows=rows,
        model_run=model_run,
        chart_images=[item.model_dump() for item in payload.chart_images],
        notes=payload.notes,
    )
    return FileResponse(
        path=report_path,
        filename=report_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
