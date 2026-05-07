# Python + Vue3 + MySQL 自动数据可视化系统

本项目是一个面向实木家具销售 Excel 数据的自动清洗、可视化推荐、行情预测和 Word 报告导出系统。

## 技术栈

- 后端：Python、FastAPI、SQLAlchemy、Pandas、scikit-learn、python-docx、MySQL
- 前端：Vue3、Vite、Vue Router、Axios、ECharts、Lucide Icons
- 数据库：MySQL，用于保存用户信息、清洗后的数据、预测结果

## 目录结构

```text
backend/                 Python 后端接口
frontend/                Vue3 前端界面
docker-compose.yml       本地 MySQL 启动配置
```

## 快速启动

1. 启动 MySQL：

```powershell
docker compose up -d mysql
```

2. 配置后端环境变量：

```powershell
cd backend
Copy-Item .env.example .env
```

3. 安装后端依赖并启动：

```powershell
py -3.13 -m venv .venv313
.\.venv313\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

4. 安装前端依赖并启动：

```powershell
cd ..\frontend
npm install
npm run dev
```

前端默认访问地址为 `http://127.0.0.1:5173`，后端接口地址为 `http://127.0.0.1:8000`。

## 默认说明

- 普通用户注册后只能管理自己的数据。
- 管理员注册需要填写 `.env` 中的 `ADMIN_REGISTER_CODE`，默认示例为 `admin-2026`。
- 上传的 Excel 会自动完成空值处理、重复行处理、字段类型识别和可视化推荐。
- Word 报告导出会包含数据概览、推荐图表截图和预测结果。
