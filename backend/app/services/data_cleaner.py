import io
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DATE_KEYWORDS = ("date", "time", "day", "month", "日期", "时间", "月份", "年月", "下单", "订单")
PRICE_KEYWORDS = ("unit_price", "price", "单价", "售价", "价格")
QUANTITY_KEYWORDS = ("quantity", "qty", "count", "number", "数量", "件数")
AMOUNT_KEYWORDS = (
    "amount",
    "total",
    "revenue",
    "sales",
    "sale",
    "金额",
    "总金额",
    "实付",
    "销售额",
    "营收",
    "收入",
    "合计",
)
DISCOUNT_KEYWORDS = ("discount", "折扣", "优惠率")
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
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "cp936")
TEXT_SEPARATORS = ("\t", ",", "，", ";", "；", "|")


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
    df = pd.DataFrame(records)
    for column in df.columns:
        df[column] = _try_convert_numeric(df[column])
        df[column] = _try_convert_date(column, df[column])
    return df


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


def _read_text_content(file_path: Path) -> tuple[str, str]:
    last_error: Exception | None = None
    for encoding in TEXT_ENCODINGS:
        try:
            return file_path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    raise ValueError("TXT 文件编码无法识别，请保存为 UTF-8 或 GBK 编码后重试") from last_error


def _separator_score(lines: list[str], separator: str) -> tuple[int, int]:
    counts = [line.count(separator) for line in lines if line.strip()]
    useful_counts = [count for count in counts if count > 0]
    if not useful_counts:
        return (0, 0)
    consistency = len(set(useful_counts))
    return (len(useful_counts), sum(useful_counts) - consistency)


def _looks_like_table(df: pd.DataFrame) -> bool:
    return not df.empty and df.shape[1] >= 2 and df.shape[0] >= 1


def _read_text_table(file_path: Path) -> pd.DataFrame:
    """Read txt data as a delimited table with common Chinese/Windows encodings."""
    text, _encoding = _read_text_content(file_path)
    lines = [line for line in text.splitlines() if line.strip()][:30]
    if not lines:
        raise ValueError("TXT 文件内容为空")

    ranked_separators = sorted(TEXT_SEPARATORS, key=lambda item: _separator_score(lines, item), reverse=True)
    candidates: list[str | None] = [separator for separator in ranked_separators if _separator_score(lines, separator)[0] > 0]
    candidates.append(None)

    errors: list[str] = []
    for separator in candidates:
        try:
            read_kwargs: dict[str, Any] = {"engine": "python"}
            if separator is None:
                read_kwargs["sep"] = None
            else:
                read_kwargs["sep"] = separator
            df = pd.read_csv(io.StringIO(text), **read_kwargs)
            if _looks_like_table(df):
                return df
        except Exception as exc:
            label = "自动识别分隔符" if separator is None else repr(separator)
            errors.append(f"{label}: {exc}")

    try:
        df = pd.read_csv(io.StringIO(text), sep=r"\s+", engine="python")
        if _looks_like_table(df):
            return df
    except Exception as exc:
        errors.append(f"空白字符分隔: {exc}")

    raise ValueError("TXT 文件未识别出表格结构，请使用制表符、逗号、分号或竖线分隔字段")


def _read_tabular_file(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(file_path, sheet_name=0)
    if suffix == ".txt":
        return _read_text_table(file_path)
    raise ValueError("仅支持 .xlsx、.xls 或 .txt 表格数据文件")


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


def _find_columns_by_keywords(columns: list[str], keywords: tuple[str, ...], exclude: set[str] | None = None) -> list[str]:
    exclude = exclude or set()
    matched: list[str] = []
    for column in columns:
        if column in exclude:
            continue
        lower_name = column.lower()
        if any(keyword.lower() in lower_name for keyword in keywords):
            matched.append(column)
    return matched


def _first_numeric_column(df: pd.DataFrame, keywords: tuple[str, ...], exclude: set[str] | None = None) -> str | None:
    for column in _find_columns_by_keywords(df.columns.tolist(), keywords, exclude):
        if pd.api.types.is_numeric_dtype(df[column]):
            return column
    return None


def _clean_sales_business_values(df: pd.DataFrame) -> dict[str, Any]:
    """Clean common sales data anomalies such as negative prices and invalid totals."""
    price_column = _first_numeric_column(df, PRICE_KEYWORDS)
    quantity_column = _first_numeric_column(df, QUANTITY_KEYWORDS)
    discount_column = _first_numeric_column(df, DISCOUNT_KEYWORDS)
    excluded = {column for column in (price_column, quantity_column, discount_column) if column}
    amount_columns = [
        column
        for column in _find_columns_by_keywords(df.columns.tolist(), AMOUNT_KEYWORDS, excluded)
        if pd.api.types.is_numeric_dtype(df[column])
    ]

    negative_values_corrected = 0
    for column in [price_column, quantity_column, *amount_columns]:
        if not column or not pd.api.types.is_numeric_dtype(df[column]):
            continue
        negative_mask = df[column] < 0
        negative_values_corrected += int(negative_mask.sum())
        df.loc[negative_mask, column] = df.loc[negative_mask, column].abs()

    discounts_normalized = 0
    if discount_column:
        percent_mask = (df[discount_column] > 1) & (df[discount_column] <= 100)
        discounts_normalized += int(percent_mask.sum())
        df.loc[percent_mask, discount_column] = df.loc[percent_mask, discount_column] / 100

        invalid_discount_mask = (df[discount_column] <= 0) | (df[discount_column] > 1)
        discounts_normalized += int(invalid_discount_mask.sum())
        df.loc[invalid_discount_mask, discount_column] = 1

    amounts_recalculated = 0
    if price_column and quantity_column and amount_columns:
        expected_amount = df[price_column] * df[quantity_column]
        if discount_column:
            expected_amount = expected_amount * df[discount_column]

        expected_amount = expected_amount.where(expected_amount >= 0)
        for amount_column in amount_columns:
            current_amount = df[amount_column]
            expected_positive = expected_amount.notna() & (expected_amount > 0)
            invalid_amount = current_amount.isna() | (current_amount <= 0)
            difference_rate = (current_amount - expected_amount).abs() / expected_amount.replace(0, np.nan)
            tolerance = 0.02 if discount_column else 0.35
            mismatch_amount = expected_positive & difference_rate.gt(tolerance)
            fix_mask = expected_positive & (invalid_amount | mismatch_amount)
            amounts_recalculated += int(fix_mask.sum())
            df.loc[fix_mask, amount_column] = expected_amount[fix_mask].round(2)

    return {
        "price_column": price_column,
        "quantity_column": quantity_column,
        "amount_columns": amount_columns,
        "discount_column": discount_column,
        "negative_values_corrected": negative_values_corrected,
        "discounts_normalized": discounts_normalized,
        "amounts_recalculated": amounts_recalculated,
    }


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
    amount_columns = _find_columns_by_keywords(numeric_columns, AMOUNT_KEYWORDS)
    if amount_columns:
        return amount_columns[0]
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


def _safe_chart_id(prefix: str, *parts: str) -> str:
    text = "_".join(str(part) for part in parts if part)
    text = re.sub(r"\W+", "_", text, flags=re.UNICODE).strip("_")
    return f"{prefix}_{text}"[:96] if text else prefix


def _format_bin_edge(value: float) -> str:
    if abs(value) >= 10000:
        return f"{value / 10000:.1f}万"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


def _group_target_sum(df: pd.DataFrame, category: str, target_column: str, limit: int = 10) -> pd.DataFrame:
    grouped = df[[category, target_column]].dropna().copy()
    grouped[target_column] = pd.to_numeric(grouped[target_column], errors="coerce")
    grouped = grouped.dropna(subset=[target_column])
    if grouped.empty:
        return pd.DataFrame(columns=[category, target_column])
    return (
        grouped.groupby(category, as_index=False)[target_column]
        .sum()
        .sort_values(target_column, ascending=False)
        .head(limit)
    )


def _group_category_count(df: pd.DataFrame, category: str, limit: int = 10) -> pd.DataFrame:
    counts = df[category].dropna().astype(str).value_counts().head(limit)
    return pd.DataFrame({category: counts.index.tolist(), "记录数": counts.values.tolist()})


def _histogram_data(series: pd.Series) -> tuple[list[str], list[int]]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty or values.nunique() < 2:
        return [], []
    bins = min(10, max(4, int(values.nunique())))
    counts, edges = np.histogram(values, bins=bins)
    labels = [f"{_format_bin_edge(edges[index])}-{_format_bin_edge(edges[index + 1])}" for index in range(len(counts))]
    return labels, counts.astype(int).tolist()


def _boxplot_rows(df: pd.DataFrame, category: str, target_column: str, limit: int = 8) -> tuple[list[str], list[list[float]]]:
    top_categories = df[category].dropna().astype(str).value_counts().head(limit).index.tolist()
    labels: list[str] = []
    rows: list[list[float]] = []
    for category_value in top_categories:
        values = pd.to_numeric(df.loc[df[category].astype(str) == category_value, target_column], errors="coerce").dropna()
        if len(values) < 3:
            continue
        labels.append(category_value)
        rows.append(
            [
                clean_json_value(values.min()),
                clean_json_value(values.quantile(0.25)),
                clean_json_value(values.median()),
                clean_json_value(values.quantile(0.75)),
                clean_json_value(values.max()),
            ]
        )
    return labels, rows


def _factor_analysis_payload(df: pd.DataFrame, numeric_columns: list[str]) -> dict[str, Any] | None:
    selected_columns: list[str] = []
    for column in numeric_columns:
        values = pd.to_numeric(df[column], errors="coerce")
        if values.notna().sum() >= max(6, int(len(df) * 0.45)) and values.nunique(dropna=True) >= 2:
            selected_columns.append(column)
        if len(selected_columns) >= 8:
            break

    if len(selected_columns) < 3:
        return None

    numeric_df = df[selected_columns].apply(pd.to_numeric, errors="coerce").dropna(how="all")
    if len(numeric_df) < 6:
        return None

    numeric_df = numeric_df.fillna(numeric_df.median(numeric_only=True))
    n_factors = min(4, len(selected_columns), max(2, len(numeric_df) - 1))
    if n_factors < 2:
        return None

    try:
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler

        scaled = StandardScaler().fit_transform(numeric_df)
        scaled = np.nan_to_num(scaled, nan=0.0, posinf=0.0, neginf=0.0)
        pca = PCA(n_components=n_factors)
        scores = pca.fit_transform(scaled)
    except Exception:
        return None

    factor_names = [f"因子{index + 1}" for index in range(n_factors)]
    loadings = pca.components_.T * np.sqrt(pca.explained_variance_)
    loading_limit = float(np.nanmax(np.abs(loadings))) if loadings.size else 1.0
    loading_limit = round(max(1.0, loading_limit), 3)
    contribution = [round(float(value) * 100, 2) for value in pca.explained_variance_ratio_]
    importance = np.abs(loadings).max(axis=1)
    importance_order = np.argsort(-importance)
    top_feature_indexes = importance_order[: min(5, len(selected_columns))]

    return {
        "columns": selected_columns,
        "factor_names": factor_names,
        "loadings": loadings,
        "loading_limit": loading_limit,
        "contribution": contribution,
        "scores": scores,
        "importance": importance,
        "importance_order": importance_order,
        "top_feature_indexes": top_feature_indexes,
    }


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
        time_df[target_column] = pd.to_numeric(time_df[target_column], errors="coerce")
        time_df = time_df.dropna()
        if not time_df.empty:
            time_df["period"] = time_df[date_column].dt.to_period("M").astype(str)
            grouped = time_df.groupby("period", as_index=False).agg(
                **{
                    target_column: (target_column, "sum"),
                    "平均值": (target_column, "mean"),
                    "记录数": (target_column, "size"),
                }
            ).tail(18)
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
            charts.append(
                {
                    "id": "monthly_count",
                    "title": "月度订单/记录数量",
                    "type": "bar",
                    "reason": "按日期字段统计每月记录数量，适合观察订单活跃度和业务量变化。",
                    "option": {
                        "tooltip": {"trigger": "axis"},
                        "grid": {"left": 50, "right": 18, "top": 42, "bottom": 46},
                        "xAxis": {"type": "category", "data": grouped["period"].tolist(), "axisLabel": {"rotate": 20}},
                        "yAxis": {"type": "value"},
                        "series": [
                            {
                                "name": "记录数",
                                "type": "bar",
                                "barMaxWidth": 32,
                                "data": [clean_json_value(value) for value in grouped["记录数"].tolist()],
                            }
                        ],
                    },
                }
            )
            charts.append(
                {
                    "id": "monthly_average",
                    "title": f"{target_column} 月度均值",
                    "type": "line",
                    "reason": "按月份查看平均客单或平均指标，能避免总量受订单数量影响过大。",
                    "option": {
                        "tooltip": {"trigger": "axis"},
                        "grid": {"left": 50, "right": 18, "top": 42, "bottom": 46},
                        "xAxis": {"type": "category", "data": grouped["period"].tolist(), "axisLabel": {"rotate": 20}},
                        "yAxis": {"type": "value"},
                        "series": [
                            {
                                "name": f"平均{target_column}",
                                "type": "line",
                                "smooth": True,
                                "data": [clean_json_value(round(float(value), 2)) for value in grouped["平均值"].tolist()],
                            }
                        ],
                    },
                }
            )

    if categorical_columns and target_column:
        for index, category in enumerate(categorical_columns[:3]):
            grouped = _group_target_sum(df, category, target_column)
            if not grouped.empty:
                charts.append(
                    {
                        "id": "category_bar" if index == 0 else _safe_chart_id("category_bar", category),
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

                if index < 2:
                    pie_data = [
                        {"name": str(row[category]), "value": clean_json_value(row[target_column])}
                        for _, row in grouped.head(8).iterrows()
                    ]
                    charts.append(
                        {
                            "id": "category_pie" if index == 0 else _safe_chart_id("category_pie", category),
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
                    charts.append(
                        {
                            "id": _safe_chart_id("treemap", category),
                            "title": f"{category} 销售矩形树图",
                            "type": "treemap",
                            "reason": "用面积大小展示头部类别贡献，适合快速发现销售集中度。",
                            "option": {
                                "tooltip": {"trigger": "item"},
                                "series": [
                                    {
                                        "name": target_column,
                                        "type": "treemap",
                                        "roam": False,
                                        "breadcrumb": {"show": False},
                                        "data": [
                                            {"name": str(row[category]), "value": clean_json_value(row[target_column])}
                                            for _, row in grouped.head(12).iterrows()
                                        ],
                                    }
                                ],
                            },
                        }
                    )

            count_grouped = _group_category_count(df, category)
            if not count_grouped.empty:
                charts.append(
                    {
                        "id": _safe_chart_id("category_count", category),
                        "title": f"{category} 记录数量",
                        "type": "bar",
                        "reason": "统计各分类出现次数，适合判断订单量、客户量或产品热度。",
                        "option": {
                            "tooltip": {"trigger": "axis"},
                            "grid": {"left": 50, "right": 18, "top": 42, "bottom": 58},
                            "xAxis": {"type": "category", "data": count_grouped[category].astype(str).tolist(), "axisLabel": {"rotate": 24}},
                            "yAxis": {"type": "value"},
                            "series": [
                                {
                                    "name": "记录数",
                                    "type": "bar",
                                    "barMaxWidth": 34,
                                    "data": [clean_json_value(value) for value in count_grouped["记录数"].tolist()],
                                }
                            ],
                        },
                    }
                )

            box_labels, box_rows = _boxplot_rows(df, category, target_column)
            if box_rows:
                charts.append(
                    {
                        "id": _safe_chart_id("boxplot", category, target_column),
                        "title": f"{category} 的 {target_column} 分布",
                        "type": "boxplot",
                        "reason": "箱线图能同时查看分类下的中位数、波动范围和异常高低值。",
                        "option": {
                            "tooltip": {"trigger": "item"},
                            "grid": {"left": 62, "right": 18, "top": 42, "bottom": 72},
                            "xAxis": {"type": "category", "data": box_labels, "axisLabel": {"rotate": 24}},
                            "yAxis": {"type": "value"},
                            "series": [{"name": target_column, "type": "boxplot", "data": box_rows}],
                        },
                    }
                )

    histogram_columns: list[str] = []
    if target_column:
        histogram_columns.append(target_column)
    histogram_columns.extend([column for column in numeric_columns if column not in histogram_columns])
    for column in histogram_columns[:3]:
        labels, counts = _histogram_data(df[column])
        if labels:
            charts.append(
                {
                    "id": _safe_chart_id("histogram", column),
                    "title": f"{column} 数值分布",
                    "type": "bar",
                    "reason": "查看数值主要集中在哪些区间，便于发现高低价位、异常大单或异常数量。",
                    "option": {
                        "tooltip": {"trigger": "axis"},
                        "grid": {"left": 54, "right": 18, "top": 42, "bottom": 66},
                        "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 28}},
                        "yAxis": {"type": "value"},
                        "series": [{"name": "记录数", "type": "bar", "barMaxWidth": 32, "data": counts}],
                    },
                }
            )

    if len(numeric_columns) >= 2:
        scatter_pairs: list[tuple[str, str]] = []
        if target_column and target_column in numeric_columns:
            scatter_pairs = [(column, target_column) for column in numeric_columns if column != target_column][:3]
        if not scatter_pairs:
            scatter_pairs = [(numeric_columns[0], numeric_columns[1])]
        for index, (x_col, y_col) in enumerate(scatter_pairs):
            scatter = [
                [clean_json_value(row[x_col]), clean_json_value(row[y_col])]
                for _, row in df[[x_col, y_col]].dropna().head(300).iterrows()
            ]
            if not scatter:
                continue
            charts.append(
                {
                    "id": "scatter" if index == 0 else _safe_chart_id("scatter", x_col, y_col),
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

    factor_payload = _factor_analysis_payload(df, numeric_columns)
    if factor_payload:
        factor_names = factor_payload["factor_names"]
        factor_columns = factor_payload["columns"]
        loadings = factor_payload["loadings"]
        heatmap_data = []
        for row_index, column in enumerate(factor_columns):
            for factor_index, _factor_name in enumerate(factor_names):
                heatmap_data.append([factor_index, row_index, clean_json_value(round(float(loadings[row_index, factor_index]), 3))])
        charts.append(
            {
                "id": "factor_loading_heatmap",
                "title": "因子载荷热力图",
                "type": "heatmap",
                "reason": "通过因子分析把多个数值字段压缩为少数综合因子，观察每个字段主要归属于哪个因子。",
                "option": {
                    "tooltip": {"position": "top"},
                    "grid": {"left": 96, "right": 24, "top": 42, "bottom": 72},
                    "xAxis": {"type": "category", "data": factor_names},
                    "yAxis": {"type": "category", "data": factor_columns},
                    "visualMap": {
                        "min": -factor_payload["loading_limit"],
                        "max": factor_payload["loading_limit"],
                        "calculable": True,
                        "orient": "horizontal",
                        "bottom": 0,
                    },
                    "series": [{"type": "heatmap", "data": heatmap_data, "label": {"show": True}}],
                },
            }
        )

        charts.append(
            {
                "id": "factor_contribution_bar",
                "title": "因子贡献率",
                "type": "bar",
                "reason": "展示每个综合因子能解释多少数据差异，用于判断主要经营变化集中在哪些因子上。",
                "option": {
                    "tooltip": {"trigger": "axis"},
                    "grid": {"left": 52, "right": 18, "top": 42, "bottom": 46},
                    "xAxis": {"type": "category", "data": factor_names},
                    "yAxis": {"type": "value", "name": "%"},
                    "series": [
                        {
                            "name": "贡献率",
                            "type": "bar",
                            "barMaxWidth": 36,
                            "data": [clean_json_value(value) for value in factor_payload["contribution"]],
                        }
                    ],
                },
            }
        )

        if factor_payload["scores"].shape[1] >= 2:
            score_data = [
                [clean_json_value(round(float(row[0]), 3)), clean_json_value(round(float(row[1]), 3)), index + 1]
                for index, row in enumerate(factor_payload["scores"][:300])
            ]
            charts.append(
                {
                    "id": "factor_score_scatter",
                    "title": "因子1 与 因子2 得分分布",
                    "type": "scatter",
                    "reason": "把每条记录映射到前两个综合因子上，适合发现相似订单群体和离群记录。",
                    "option": {
                        "tooltip": {"trigger": "item"},
                        "grid": {"left": 52, "right": 18, "top": 42, "bottom": 46},
                        "xAxis": {"type": "value", "name": factor_names[0]},
                        "yAxis": {"type": "value", "name": factor_names[1]},
                        "series": [{"type": "scatter", "symbolSize": 9, "data": score_data}],
                    },
                }
            )

        ordered_indexes = factor_payload["importance_order"][: min(10, len(factor_columns))]
        charts.append(
            {
                "id": "factor_key_fields_bar",
                "title": "因子关键字段强度",
                "type": "bar",
                "reason": "按综合载荷强度排序，帮助判断哪些数值字段最能代表整体数据变化。",
                "option": {
                    "tooltip": {"trigger": "axis"},
                    "grid": {"left": 54, "right": 18, "top": 42, "bottom": 68},
                    "xAxis": {
                        "type": "category",
                        "data": [factor_columns[index] for index in ordered_indexes],
                        "axisLabel": {"rotate": 24},
                    },
                    "yAxis": {"type": "value"},
                    "series": [
                        {
                            "name": "综合载荷强度",
                            "type": "bar",
                            "barMaxWidth": 34,
                            "data": [clean_json_value(round(float(factor_payload["importance"][index]), 3)) for index in ordered_indexes],
                        }
                    ],
                },
            }
        )

        top_feature_indexes = factor_payload["top_feature_indexes"]
        radar_columns = [factor_columns[index] for index in top_feature_indexes]
        charts.append(
            {
                "id": "factor_profile_radar",
                "title": "因子画像雷达图",
                "type": "radar",
                "reason": "展示每个因子在关键字段上的相对强弱，适合给综合因子命名并理解其业务含义。",
                "option": {
                    "tooltip": {},
                    "legend": {"bottom": 0, "type": "scroll"},
                    "radar": {
                        "indicator": [{"name": column, "max": 100} for column in radar_columns],
                        "radius": "62%",
                    },
                    "series": [
                        {
                            "type": "radar",
                            "data": [
                                {
                                    "name": factor_name,
                                    "value": [
                                        clean_json_value(
                                            round(
                                                abs(float(loadings[column_index, factor_index]))
                                                / factor_payload["loading_limit"]
                                                * 100,
                                                2,
                                            )
                                        )
                                        for column_index in top_feature_indexes
                                    ],
                                }
                                for factor_index, factor_name in enumerate(factor_names)
                            ],
                        }
                    ],
                },
            }
        )

    if categorical_columns and target_column and len(numeric_columns) >= 2:
        category = categorical_columns[0]
        radar_metrics = [target_column, *[column for column in numeric_columns if column != target_column]][:4]
        grouped = df.groupby(category, as_index=False)[radar_metrics].mean(numeric_only=True).dropna()
        if not grouped.empty:
            sort_column = target_column if target_column in grouped.columns else radar_metrics[0]
            grouped = grouped.sort_values(sort_column, ascending=False).head(5)
            max_values = {column: float(grouped[column].max()) or 1 for column in radar_metrics}
            charts.append(
                {
                    "id": _safe_chart_id("radar", category),
                    "title": f"{category} 综合指标雷达图",
                    "type": "radar",
                    "reason": "把多个数值指标压缩到同一张图中，适合比较头部类别的综合表现。",
                    "option": {
                        "tooltip": {},
                        "legend": {"bottom": 0, "type": "scroll"},
                        "radar": {
                            "indicator": [{"name": column, "max": 100} for column in radar_metrics],
                            "radius": "62%",
                        },
                        "series": [
                            {
                                "type": "radar",
                                "data": [
                                    {
                                        "name": str(row[category]),
                                        "value": [
                                            clean_json_value(round(float(row[column]) / max_values[column] * 100, 2))
                                            for column in radar_metrics
                                        ],
                                    }
                                    for _, row in grouped.iterrows()
                                ],
                            }
                        ],
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
    """Read a spreadsheet-like data file, clean common problems, and return chart recommendations."""
    raw_df = _read_tabular_file(file_path)
    original_rows, original_columns = raw_df.shape

    df = raw_df.dropna(how="all").dropna(axis=1, how="all").copy()
    df.columns = _normalize_columns(df.columns.tolist())

    for column in df.columns:
        df[column] = _try_convert_numeric(df[column])
        df[column] = _try_convert_date(column, df[column])

    missing_before = {column: int(df[column].isna().sum()) for column in df.columns}
    filled_missing = _fill_missing_values(df)
    business_cleaning = _clean_sales_business_values(df)
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
        "business_cleaning": business_cleaning,
        "numeric_columns": detected["numeric_columns"],
        "date_columns": detected["date_columns"],
        "categorical_columns": detected["categorical_columns"],
        "target_column": pick_target_column(df),
        "date_column": pick_date_column(df),
        "source_format": file_path.suffix.lower().lstrip("."),
    }

    charts = build_chart_options(df)
    recommendations = build_recommendations(charts)
    return df, profile, recommendations, charts
