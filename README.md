# Python + Vue3 + MySQL 自动数据可视化系统

本项目用于对实木家具销售 Excel 数据进行自动清洗、可视化分析、行情预测和 Word 报告导出。

## 技术栈

后端：

- Python：后端主要开发语言。
- FastAPI：提供登录、上传、分析、预测和导出接口。
- SQLAlchemy：连接并操作数据库。
- Pandas：读取 Excel，并完成数据清洗和统计。
- scikit-learn：实现销售行情预测。
- python-docx：生成 Word 分析报告。

前端：

- Vue3：构建前端页面。
- Vite：启动和打包前端项目。
- Vue Router：管理页面跳转。
- Axios：请求后端接口。
- ECharts：绘制可视化图表。
- Lucide Icons：提供页面图标。

数据库：

- MySQL：保存用户信息和清洗后的数据。

## 主要功能

- 用户注册、登录、管理员和普通用户分离
- Excel 表格上传、拖拽上传和数据清洗
- 自动推荐可视化图表
- 销售数据行情预测
- Word 分析报告导出
- 用户头像和用户中心
- Arcaea / 轻盈一梦双主题切换

## 目录说明

```text
backend/        后端代码
frontend/       前端代码
代码编写步骤.txt  项目编写和启动说明
```

## 启动方式

先确认本机 MySQL 已启动，并已创建数据库：

```sql
CREATE DATABASE auto_visualization DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

后端启动：

```powershell
cd "D:\毕业设计\代码仓库\python+vue3+mysql\backend"
.\.venv313\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

前端启动：

```powershell
cd "D:\毕业设计\代码仓库\python+vue3+mysql\frontend"
npm install
npm run dev
```

默认访问地址：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`

如果 5173 被占用，Vite 会自动换到 5174，请按终端显示的地址访问。

## 默认配置

- 数据库连接在 `backend/.env` 中配置。
- 默认管理员注册密钥：`FatalisHikari`
- 普通用户只能管理自己的数据。
- 管理员可以查看用户和数据集信息。
- PyCaret 不是必须安装；未安装时系统会使用 scikit-learn 进行预测。
