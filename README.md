# 基于 PyCaret 的销售数据分析预测系统

本项目是一个面向木制家具、实木家具及销售统计数据的自动化分析系统。系统支持 Excel/表格数据上传、自动清洗、可视化图表推荐、图例文字解析、行情预测、Word 报告导出、记账数据管理和后台用户管理。

项目用于毕业设计演示，核心目标是把销售数据处理流程做成一个可操作的 Web 系统：用户上传数据后，系统自动完成清洗、统计、图表生成、图文解释和预测分析。

## 技术栈

后端：

- Python 3.11：后端运行环境。
- FastAPI：提供登录注册、数据上传、图表分析、预测、报告导出等接口。
- SQLAlchemy：操作 MySQL 数据库。
- MySQL：保存用户、数据集、清洗后的记录、预测结果和操作日志。
- pandas / openpyxl / xlrd：读取 Excel、处理表格、完成数据清洗和统计。
- PyCaret：自动建模主体，用于模型预处理、模型比较和预测分析。
- scikit-learn：当 PyCaret 不可用时作为回退预测方案。
- python-docx：导出 Word 分析报告。

前端：

- Vue3：构建前端页面。
- Vite：本地开发和前端打包。
- Vue Router：页面路由和权限跳转。
- Axios：请求后端 API。
- ECharts：渲染柱状图、折线图、饼图、箱线图、热力图、雷达图等图表。
- Lucide Icons：页面图标。

## 主要功能

- 用户登录、注册、验证码校验、密码重置。
- 普通用户、管理员、超级管理员分级权限。
- Excel / xls / txt 表格上传和自动清洗。
- 自动识别日期字段、数值字段、分类字段。
- 自动处理缺失值、重复列名、数值格式、日期格式和部分销售业务异常值。
- 自动推荐可视化图表，并支持图表隐藏、显示和图片导出。
- 图例分析页面：根据图表类型自动生成“怎么看”“数值代表什么”“系统发现”“经营判断问题”等文字解析。
- PyCaret 自动建模：自动预处理、比较模型、生成预测结果和经营建议。
- Word 报告导出：包含清洗概览、图表截图和预测结论。
- 记账模块：支持销售记录字段配置、Excel 导入、分组预览、导出和转为数据集。
- 用户中心：头像上传、主题选择、个人统计。
- 管理端：用户管理、数据集查看、系统统计。
- 主题切换：Arcaea、轻盈一梦、腐蚀之心、模块禁用、七日重生；超级管理员冴月麟可使用“遗忘的风华”主题。

## 数据来源

项目中包含两类演示数据：

- `清洗实验样本_实木家具销售_脏数据.xlsx`：用于演示上传、清洗、图表推荐和预测流程。
- `云南木制家具市场销售数据_官方统计原始汇总版.csv/.xlsx`：来自云南省统计局公开发布的《云南统计年鉴》Excel 原表，整理为云南木制家具、家具零售、木材及制品和区域消费市场相关统计数据。

注意：官方统计数据是真实公开统计口径，不是随机生成数据，也不是某个店铺的订单明细。用于论文和答辩时，建议说明“数据来自云南省统计局统计年鉴，属于官方统计数据”。

## 目录结构

```text
backend/                         后端 FastAPI 项目
  app/core/                      配置、密码哈希、Token 生成与校验
  app/routers/                   认证、数据集、预测、报告、记账、用户、管理端接口
  app/services/                  数据清洗、图表生成、图例解析、预测、报告导出
  app/models/                    SQLAlchemy 数据库模型
  storage/                       上传文件、头像、报告输出目录

frontend/                        前端 Vue3 项目
  src/views/                     登录、工作台、图例分析、记账、管理端、用户中心页面
  src/components/                图表组件、数据预览组件、主题组件
  src/api/                       Axios 接口封装
  src/styles/                    全局样式与主题样式

scripts/                         数据整理脚本
真实数据_中国云南木材家具/        云南统计年鉴原始下载和解压文件
```

## 核心代码位置

验证码与登录注册：

- `backend/app/routers/auth.py`：验证码生成、验证码校验、注册、登录、密码重置。
- `backend/app/core/security.py`：密码哈希、密码验证、Token 生成与解析。
- `frontend/src/views/AuthView.vue`：登录注册页面和验证码展示。

数据清洗与图表生成：

- `backend/app/services/data_cleaner.py`：读取表格、清洗数据、识别字段、生成 ECharts 配置。
- `backend/app/routers/datasets.py`：上传数据、返回清洗结果、调用图表分析和预测。
- `frontend/src/views/DashboardView.vue`：工作台上传、图表展示、预测和导出。
- `frontend/src/components/ChartPanel.vue`：ECharts 渲染。

图例分析：

- `backend/app/services/chart_interpreter.py`：按图表类型生成文字解释和模型提示。
- `frontend/src/views/LegendAnalysisView.vue`：图例分析页面。

预测建模：

- `backend/app/services/predictor.py`：PyCaret 自动建模和 scikit-learn 回退预测。
- `backend/requirements.txt`：PyCaret 及后端依赖版本。

报告导出：

- `backend/app/services/report_exporter.py`：Word 报告生成。
- `backend/app/routers/reports.py`：报告导出接口。

## 启动方式

先确认本机 MySQL 已启动，并创建数据库：

```sql
CREATE DATABASE auto_visualization DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

复制并配置后端环境变量：

```powershell
cd "D:\毕业设计\代码仓库\python+vue3+mysql\backend"
copy .env.example .env
```

根据本机 MySQL 用户名和密码修改 `backend/.env` 中的 `DATABASE_URL`。

后端启动：

```powershell
cd "D:\毕业设计\代码仓库\python+vue3+mysql\backend"
.\.venv311\Scripts\Activate.ps1
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
- 后端接口文档：`http://127.0.0.1:8000/docs`

如果 5173 被占用，Vite 会自动切换到其他端口，请以终端输出地址为准。

## 默认配置

- 数据库连接：`backend/.env` 中的 `DATABASE_URL`。
- 后端密钥：`backend/.env` 中的 `SECRET_KEY`。
- 管理员注册密钥：`ADMIN_REGISTER_CODE`，默认示例为 `FatalisHikari`。
- Token 有效期：`ACCESS_TOKEN_EXPIRE_MINUTES`。
- 上传文件目录：`backend/storage/uploads`。
- 报告导出目录：`backend/storage/reports`。
- 头像目录：`backend/storage/avatars`。

## 答辩说明

1. 用户上传 Excel 后，后端使用 pandas 读取数据。
2. `data_cleaner.py` 对字段名、数值、日期、缺失值和业务异常值进行清洗。
3. `build_chart_options()` 根据字段类型自动生成 ECharts 图表配置。
4. 前端 `ChartPanel.vue` 使用 ECharts 渲染图表。
5. 图例分析页面调用 `/datasets/{id}/chart-analysis` 接口。
6. `chart_interpreter.py` 根据图表类型提取横轴、纵轴、最大值、最小值、均值和占比，并生成文字解释。
7. 系统尝试使用 PyCaret 自动建模，判断关键字段；如果 PyCaret 不可用，则回退到统计相关性和分组均值分析。
8. 行情预测由 `predictor.py` 完成，优先使用 PyCaret，失败时使用 scikit-learn 回退模型。

## 常见问题

测试数据来源：数据云南木制家具市场数据来自云南省统计局《云南统计年鉴》公开 Excel 原表。系统中的清洗实验样本用于功能演示。

**为什么使用 PyCaret？**

PyCaret 可以自动完成预处理、模型比较、模型选择和预测，适合把机器学习流程封装到 Web 系统中，让用户不用手写建模代码也能完成预测。
