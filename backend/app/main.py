from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.session import init_db
from app.routers import admin, auth, datasets, ledger, reports, users


def create_app() -> FastAPI:
    """Create the FastAPI application and register routes."""
    app = FastAPI(
        title=settings.app_name,
        description="销售数据清洗、自动可视化、图例分析、行情预测、记账管理和系统管理接口文档。",
        version="1.0.0",
        openapi_tags=[
            {"name": "认证与账号", "description": "验证码、注册、登录和密码重置相关接口。"},
            {"name": "用户中心", "description": "当前用户信息、个人统计、资料修改和头像上传接口。"},
            {"name": "数据集分析", "description": "数据上传清洗、图表生成、图例分析、预测建模和数据集管理接口。"},
            {"name": "记账管理", "description": "记账字段、记录、Excel 导入导出和转数据集接口。"},
            {"name": "报告导出", "description": "将图表截图、预测结果和备注导出为 Word 报告。"},
            {"name": "管理后台", "description": "管理员用户管理、数据集查看和系统统计接口。"},
            {"name": "系统状态", "description": "后端服务健康检查接口。"},
        ],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    app.include_router(auth.router, prefix="/api/auth", tags=["认证与账号"])
    app.include_router(users.router, prefix="/api/users", tags=["用户中心"])
    app.include_router(datasets.router, prefix="/api/datasets", tags=["数据集分析"])
    app.include_router(ledger.router, prefix="/api/ledger", tags=["记账管理"])
    app.include_router(reports.router, prefix="/api/reports", tags=["报告导出"])
    app.include_router(admin.router, prefix="/api/admin", tags=["管理后台"])

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    @app.get(
        "/api/health",
        tags=["系统状态"],
        summary="后端健康检查",
        description="检查 FastAPI 后端服务是否正常运行。返回 ok 表示服务可用。",
    )
    def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    return app


app = create_app()
