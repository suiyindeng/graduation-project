from pydantic import BaseModel


class ChartImage(BaseModel):
    title: str
    image_base64: str


class ExportReportRequest(BaseModel):
    dataset_id: int
    model_run_id: int | None = None
    chart_images: list[ChartImage] = []
    notes: str | None = None
