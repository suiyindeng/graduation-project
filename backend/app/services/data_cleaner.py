import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DATE_KEYWORDS = ("date", "time", "day", "month", "日期", "时间", "月份", "年月", "下单", "订单")
SALES_KEYWORDS = (
    "sale",
    "sales",
    "amount",
    "revenue",
    "total",
    "quantity",
    "price",
    "销售",
    "金额",
    "营收",
    "收入",
    "数量",
    "件数",
    "单价",
)


def clean_json_value(value: Any) -> Any:
    """Convert pandas/numpy values into JSON-serializable Python values."""
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    return value


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        records.append({key: clean_json_value(value) for key, value in row.items()})
    return records


def dataframe_from_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(records)


def _normalize_columns(columns: list[Any]) -> list[str]:
    normalized: list[str] = []
    used: dict[str, int] = {}
    for index, column in enumerate(columns, start=1):
        name = str(column).strip() if column is not None else ""
        name = re.sub(r"\s+", "_", name)
        name = name if name and name.lower() != "nan" else f"column_{index}"
        if name in used:
            used[name] += 1
            name = f"{name}_{used[name]}"
        else:
            used[name] = 1
        normalized.append(name)
    return normalized


def _try_convert_numeric(series: pd.Series) -> pd.Series:
    if series.dtype != "object":
        return series
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("￥", "", regex=False)
        .str.replace("¥", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip()
    )
    converted = pd.to_numeric(cleaned, errors="coerce")
    if converted.notna().mean() >= 0.65:
        return converted
    return series


def _try_convert_date(name: str, series: pd.Series) -> pd.Series:
    lower_name = name.lower()
    should_try = any(keyword in lower_name for keyword in DATE_KEYWORDS)
    if not should_try and series.dtype != "object":
        return series
    converted = pd.to_datetime(series, errors="coerce", format="mixed")
    if converted.notna().mean() >= 0.55:
        return converted
    return series


def detect_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
    date_columns = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()
    categorical_columns = [
        column
        for column in df.columns
        if column not in numeric_columns
        and column not in date_columns
        and 1 < df[column].nunique(dropna=True) <= min(50, max(2, len(df) // 2))
    ]
    return {
        "numeric_columns": numeric_columns,
        "date_columns": date_columns,
        "categorical_columns": categorical_columns,
    }


def pick_target_column(df: pd.DataFrame) -> str | None:
    numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
    if not numeric_columns:
        return None
    for column in numeric_columns:
        lower_name = column.lower()
        if any(keyword in lower_name for keyword in SALES_KEYWORDS):
            return column
    return numeric_columns[0]


def pick_date_column(df: pd.DataFrame) -> str | None:
    date_columns = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()
    if not date_columns:
        return None
    for column in date_columns:
        lower_name = column.lower()
        if any(keyword in lower_name for keyword in DATE_KEYWORDS):
            return column
    return date_columns[0]


def _fill_missing_values(df: pd.DataFrame) -> dict[str, int]:
    filled: dict[str, int] = {}
    for column in df.columns:
        missing_count = int(df[column].isna().sum())
        if missing_count == 0:
            continue
        filled[column] = missing_count
        if pd.api.types.is_numeric_dtype(df[column]):
            value = df[column].median()
            df[column] = df[column].fillna(0 if pd.isna(value) else value)
        elif pd.api.types.is_datetime64_any_dtype(df[column]):
            df[column] = df[column].ffill().bfill()
        else:
            mode = df[column].mode(dropna=True)
            df[column] = df[column].fillna(mode.iloc[0] if not mode.empty else "未知")
    return filled


def build_chart_options(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Create ECharts options from the cleaned dataframe."""
    detected = detect_columns(df)
    numeric_columns = detected["numeric_columns"]
    date_column = pick_date_column(df)
    target_column = pick_target_column(df)
    categorical_columns = detected["categorical_columns"]
    charts: list[dict[str, Any]] = []

    if date_column and target_column:
        time_df = df[[date_column, target_column]].dropna().copy()
        time_df[date_column] = pd.to_datetime(time_df[date_column], errors="coerce")
        time_df = time_df.dropna()
        if not time_df.empty:
            time_df["period"] = time_df[date_column].dt.to_period("M").astype(str)
            grouped = time_df.groupby("period", as_index=False)[target_column].sum().tail(18)
            charts.append(
                {
                    "id": "trend",
                    "title": f"{target_column} 月度趋势",
                    "type": "line",
                    "reason": "识别到日期字段和销售类数值字段，适合观察行情走势。",
                    "option": {
                        "tooltip": {"trigger": "axis"},
                        "grid": {"left": 42, "right": 18, "top": 42, "bottom": 36},
                        "xAxis": {"type": "category", "data": grouped["period"].tolist()},
                        "yAxis": {"type": "value"},
                        "series": [
                            {
                                "name": target_column,
                                "type": "line",
                                "smooth": True,
                                "areaStyle": {},
                                "data": [clean_json_value(value) for value in grouped[target_column].tolist()],
                            }
                        ],
                    },
                }
            )

    if categorical_columns and target_column:
        category = categorical_columns[0]
        grouped = (
            df.groupby(category, as_index=False)[target_column]
            .sum()
            .sort_values(target_column, ascending=False)
            .head(10)
        )
        charts.append(
            {
                "id": "category_bar",
                "title": f"{category} 销售贡献",
                "type": "bar",
                "reason": "识别到分类字段，适合比较不同产品、地区或渠道的销售贡献。",
                "option": {
                    "tooltip": {"trigger": "axis"},
                    "grid": {"left": 50, "right": 18, "top": 42, "bottom": 58},
                    "xAxis": {"type": "category", "data": grouped[category].astype(str).tolist(), "axisLabel": {"rotate": 24}},
                    "yAxis": {"type": "value"},
                    "series": [
                        {
                            "name": target_column,
                            "type": "bar",
                            "barMaxWidth": 34,
                            "data": [clean_json_value(value) for value in grouped[target_column].tolist()],
                        }
                    ],
                },
            }
        )

        pie_data = [
            {"name": str(row[category]), "value": clean_json_value(row[target_column])}
            for _, row in grouped.head(8).iterrows()
        ]
        charts.append(
            {
                "id": "category_pie",
                "title": f"{category} 占比",
                "type": "pie",
                "reason": "分类汇总后可以查看头部类别占比，适合给非专业用户快速判断重点。",
                "option": {
                    "tooltip": {"trigger": "item"},
                    "legend": {"bottom": 0, "type": "scroll"},
                    "series": [
                        {
                            "name": target_column,
                            "type": "pie",
                            "radius": ["42%", "68%"],
                            "center": ["50%", "45%"],
                            "data": pie_data,
                        }
                    ],
                },
            }
        )

    if len(numeric_columns) >= 2:
        x_col, y_col = numeric_columns[:2]
        scatter = [
            [clean_json_value(row[x_col]), clean_json_value(row[y_col])]
            for _, row in df[[x_col, y_col]].dropna().head(300).iterrows()
        ]
        charts.append(
            {
                "id": "scatter",
                "title": f"{x_col} 与 {y_col} 关系",
                "type": "scatter",
                "reason": "识别到多个数值字段，适合观察价格、数量、销售额之间的关系。",
                "option": {
                    "tooltip": {"trigger": "item"},
                    "grid": {"left": 50, "right": 18, "top": 42, "bottom": 42},
                    "xAxis": {"type": "value", "name": x_col},
                    "yAxis": {"type": "value", "name": y_col},
                    "series": [{"type": "scatter", "symbolSize": 9, "data": scatter}],
                },
            }
        )

    if len(numeric_columns) >= 3:
        selected = numeric_columns[:5]
        corr = df[selected].corr(numeric_only=True).fillna(0)
        heatmap_data = []
        for i, row_name in enumerate(selected):
            for j, column_name in enumerate(selected):
                heatmap_data.append([j, i, round(float(corr.loc[row_name, column_name]), 3)])
        charts.append(
            {
                "id": "correlation",
                "title": "数值字段相关性",
                "type": "heatmap",
                "reason": "多个数值字段可计算相关系数，适合发现影响销售额的潜在线索。",
                "option": {
                    "tooltip": {"position": "top"},
                    "grid": {"left": 90, "right": 24, "top": 42, "bottom": 70},
                    "xAxis": {"type": "category", "data": selected, "axisLabel": {"rotate": 24}},
                    "yAxis": {"type": "category", "data": selected},
                    "visualMap": {"min": -1, "max": 1, "calculable": True, "orient": "horizontal", "bottom": 0},
                    "series": [{"type": "heatmap", "data": heatmap_data, "label": {"show": True}}],
                },
            }
        )

    return charts


def build_recommendations(charts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"id": chart["id"], "title": chart["title"], "type": chart["type"], "reason": chart["reason"]}
        for chart in charts
    ]


def load_and_clean_excel(file_path: Path) -> tuple[pd.DataFrame, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Read an Excel file, clean common problems, and return chart recommendations."""
    raw_df = pd.read_excel(file_path, sheet_name=0)
    original_rows, original_columns = raw_df.shape

    df = raw_df.dropna(how="all").dropna(axis=1, how="all").copy()
    df.columns = _normalize_columns(df.columns.tolist())

    for column in df.columns:
        df[column] = _try_convert_numeric(df[column])
        df[column] = _try_convert_date(column, df[column])

    missing_before = {column: int(df[column].isna().sum()) for column in df.columns}
    filled_missing = _fill_missing_values(df)
    duplicates_removed = int(df.duplicated().sum())
    df = df.drop_duplicates().reset_index(drop=True)

    detected = detect_columns(df)
    profile = {
        "original_rows": original_rows,
        "original_columns": original_columns,
        "cleaned_rows": int(df.shape[0]),
        "cleaned_columns": int(df.shape[1]),
        "duplicates_removed": duplicates_removed,
        "missing_before": missing_before,
        "filled_missing": filled_missing,
        "numeric_columns": detected["numeric_columns"],
        "date_columns": detected["date_columns"],
        "categorical_columns": detected["categorical_columns"],
        "target_column": pick_target_column(df),
        "date_column": pick_date_column(df),
    }

    charts = build_chart_options(df)
    recommendations = build_recommendations(charts)
    return df, profile, recommendations, charts
