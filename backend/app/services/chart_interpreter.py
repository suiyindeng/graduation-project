import contextlib
import io
import warnings
from typing import Any

import numpy as np
import pandas as pd

from app.services.data_cleaner import clean_json_value, pick_target_column


def _format_number(value: float | int | None) -> str:
    if value is None or not np.isfinite(float(value)):
        return "-"
    number = float(value)
    if abs(number) >= 100000000:
        return f"{number / 100000000:.2f} 亿"
    if abs(number) >= 10000:
        return f"{number / 10000:.2f} 万"
    if number.is_integer():
        return f"{int(number)}"
    return f"{number:.2f}"


def _as_number(value: Any) -> float | None:
    if isinstance(value, (list, tuple)) and value:
        value = value[-1]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number


def _axis_option(option: dict[str, Any], key: str) -> dict[str, Any]:
    axis = option.get(key, {})
    if isinstance(axis, list):
        return axis[0] if axis and isinstance(axis[0], dict) else {}
    return axis if isinstance(axis, dict) else {}


def _series_option(chart: dict[str, Any]) -> dict[str, Any]:
    series = (chart.get("option") or {}).get("series", [])
    if isinstance(series, list) and series and isinstance(series[0], dict):
        return series[0]
    return {}


def _extract_named_values(chart: dict[str, Any]) -> list[dict[str, Any]]:
    option = chart.get("option") or {}
    series = _series_option(chart)
    data = series.get("data") or []
    chart_type = chart.get("type")
    values: list[dict[str, Any]] = []

    if chart_type == "pie":
        for index, item in enumerate(data):
            if isinstance(item, dict):
                name = str(item.get("name", f"项目 {index + 1}"))
                number = _as_number(item.get("value"))
            else:
                name = f"项目 {index + 1}"
                number = _as_number(item)
            if number is not None:
                values.append({"name": name, "value": number})
        return values

    labels = _axis_option(option, "xAxis").get("data") or []
    for index, item in enumerate(data):
        name = str(labels[index]) if index < len(labels) else f"项目 {index + 1}"
        number = None
        if isinstance(item, dict):
            name = str(item.get("name", name))
            number = _as_number(item.get("value"))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            name = str(item[0])
            number = _as_number(item[1])
        else:
            number = _as_number(item)
        if number is not None:
            values.append({"name": name, "value": number})
    return values


def _extract_scatter_points(chart: dict[str, Any]) -> list[tuple[float, float]]:
    data = _series_option(chart).get("data") or []
    points: list[tuple[float, float]] = []
    for item in data:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        x_value = _as_number(item[0])
        y_value = _as_number(item[1])
        if x_value is not None and y_value is not None:
            points.append((x_value, y_value))
    return points


def _extract_heatmap_pairs(chart: dict[str, Any]) -> list[dict[str, Any]]:
    option = chart.get("option") or {}
    x_labels = _axis_option(option, "xAxis").get("data") or []
    y_labels = _axis_option(option, "yAxis").get("data") or []
    data = _series_option(chart).get("data") or []
    pairs: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        try:
            x_index = int(item[0])
            y_index = int(item[1])
        except (TypeError, ValueError):
            continue
        if x_index == y_index:
            continue
        value = _as_number(item[2])
        if value is None:
            continue
        x_name = str(x_labels[x_index]) if x_index < len(x_labels) else str(x_index)
        y_name = str(y_labels[y_index]) if y_index < len(y_labels) else str(y_index)
        pairs.append({"x": x_name, "y": y_name, "value": value})
    return pairs


def _extract_heatmap_cells(chart: dict[str, Any]) -> list[dict[str, Any]]:
    option = chart.get("option") or {}
    x_labels = _axis_option(option, "xAxis").get("data") or []
    y_labels = _axis_option(option, "yAxis").get("data") or []
    data = _series_option(chart).get("data") or []
    cells: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        try:
            x_index = int(item[0])
            y_index = int(item[1])
        except (TypeError, ValueError):
            continue
        value = _as_number(item[2])
        if value is None:
            continue
        cells.append(
            {
                "x": str(x_labels[x_index]) if x_index < len(x_labels) else str(x_index),
                "y": str(y_labels[y_index]) if y_index < len(y_labels) else str(y_index),
                "value": value,
            }
        )
    return cells


def _trend_description(values: list[dict[str, Any]]) -> tuple[str, list[str]]:
    if len(values) < 2:
        return "样本点较少，主要用于查看单个阶段的数值大小。", []

    first = values[0]["value"]
    last = values[-1]["value"]
    change = last - first
    change_rate = (change / first * 100) if first else 0
    direction = "基本平稳" if abs(change_rate) < 5 else "上升" if change > 0 else "下降"
    summary = (
        f"从 {values[0]['name']} 到 {values[-1]['name']}，数值由 {_format_number(first)} "
        f"变为 {_format_number(last)}，整体{direction}，变化约 {_format_number(abs(change))}。"
    )
    suggestions = []
    if direction == "上升":
        suggestions.append("如果这是销售额或数量，说明近期需求有增强迹象，可重点观察库存和交付能力。")
    elif direction == "下降":
        suggestions.append("如果这是销售额或数量，说明近期需求可能回落，应谨慎判断备货和促销节奏。")
    else:
        suggestions.append("整体变化不大，适合继续观察单个阶段的异常高点或低点。")
    return summary, suggestions


def _top_bottom_findings(values: list[dict[str, Any]], top_word: str = "最高") -> list[str]:
    if not values:
        return ["图表中没有可计算的有效数值。"]
    ordered = sorted(values, key=lambda item: item["value"], reverse=True)
    highest = ordered[0]
    lowest = ordered[-1]
    average = sum(item["value"] for item in values) / len(values)
    return [
        f"{top_word}的是「{highest['name']}」，数值为 {_format_number(highest['value'])}。",
        f"最低的是「{lowest['name']}」，数值为 {_format_number(lowest['value'])}。",
        f"平均水平约为 {_format_number(average)}，高于平均值的项目需要优先关注。",
    ]


def _field_value_explanation(value_name: str) -> str:
    field = str(value_name)
    if any(keyword in field for keyword in ["记录数", "订单数", "数量", "销量", "件数"]):
        return f"「{field}」表示记录或商品的数量，数值越大代表该时间段或类别出现得越多。"
    if any(keyword in field for keyword in ["金额", "销售额", "收入", "支出", "实付", "付款", "总额"]):
        return f"「{field}」表示金额类指标，通常可理解为销售规模、收入规模或支出规模。"
    if any(keyword in field for keyword in ["单价", "价格", "均价", "平均"]):
        return f"「{field}」表示平均水平或价格水平，适合观察高低变化，不等同于总销售规模。"
    if "折扣" in field:
        return f"「{field}」表示折扣水平，数值越低通常代表优惠力度越大。"
    if "评分" in field:
        return f"「{field}」表示评价分数，数值越高通常代表客户反馈越好。"
    return f"「{field}」来自清洗后的同名字段，数值越大代表该指标在当前维度下越高。"


def _named_value_example(values: list[dict[str, Any]], label_name: str, value_name: str) -> str | None:
    if not values:
        return None
    item = values[0]
    return (
        f"例如「{item['name']}」对应的数值为 {_format_number(item['value'])}，"
        f"表示这个{label_name}下的「{value_name}」为 {_format_number(item['value'])}。"
    )


def _named_value_range(values: list[dict[str, Any]], value_name: str) -> str | None:
    if not values:
        return None
    numbers = [item["value"] for item in values]
    return (
        f"本图中「{value_name}」的可视化数值范围约为 "
        f"{_format_number(min(numbers))} 到 {_format_number(max(numbers))}。"
    )


def _compact_items(items: list[str | None]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _safe_profile_list(profile: dict[str, Any], key: str, df: pd.DataFrame) -> list[str]:
    return [column for column in profile.get(key, []) if column in df.columns]


def _prepare_model_frame(df: pd.DataFrame, profile: dict[str, Any]) -> tuple[pd.DataFrame, str | None, list[str], list[str]]:
    prepared = pd.DataFrame(index=df.index)
    numeric_columns: list[str] = []
    categorical_columns: list[str] = []

    for column in df.columns:
        converted = pd.to_numeric(df[column], errors="coerce")
        if converted.notna().mean() >= 0.65:
            prepared[column] = converted
            numeric_columns.append(column)

    target_column = profile.get("target_column")
    if target_column not in numeric_columns:
        target_column = pick_target_column(prepared[numeric_columns]) if numeric_columns else None
    if not target_column:
        return prepared, None, numeric_columns, categorical_columns

    for column in _safe_profile_list(profile, "date_columns", df):
        converted = pd.to_datetime(df[column], errors="coerce")
        if converted.notna().mean() >= 0.55:
            prepared[f"{column}_月份"] = converted.dt.month.astype("float")
            prepared[f"{column}_季度"] = converted.dt.quarter.astype("float")
            numeric_columns.extend([f"{column}_月份", f"{column}_季度"])

    for column in _safe_profile_list(profile, "categorical_columns", df):
        if column == target_column:
            continue
        unique_count = df[column].nunique(dropna=True)
        if 2 <= unique_count <= 30:
            prepared[column] = df[column].fillna("未知").astype(str)
            categorical_columns.append(column)
        if len(categorical_columns) >= 6:
            break

    prepared = prepared.dropna(subset=[target_column])
    return prepared, target_column, numeric_columns, categorical_columns


def _statistical_importance(
    model_df: pd.DataFrame,
    target_column: str,
    numeric_columns: list[str],
    categorical_columns: list[str],
) -> list[dict[str, Any]]:
    target = pd.to_numeric(model_df[target_column], errors="coerce")
    target_std = float(target.std()) if target.notna().sum() >= 2 else 0.0
    insights: list[dict[str, Any]] = []

    for column in numeric_columns:
        if column == target_column or column not in model_df.columns:
            continue
        pair = pd.DataFrame(
            {
                "feature": pd.to_numeric(model_df[column], errors="coerce"),
                "target": target,
            }
        ).dropna()
        if len(pair) < 3 or pair["feature"].nunique() < 2:
            continue
        corr = float(pair["feature"].corr(pair["target"]))
        if not np.isfinite(corr):
            continue
        direction = "正向" if corr > 0 else "反向" if corr < 0 else "关系弱"
        insights.append(
            {
                "name": column,
                "type": "数值字段",
                "score": round(abs(corr), 3),
                "direction": direction,
                "explanation": f"「{column}」与「{target_column}」呈{direction}关系，相关强度约为 {abs(corr):.2f}。",
            }
        )

    for column in categorical_columns:
        if column not in model_df.columns:
            continue
        group = model_df[[column, target_column]].dropna().groupby(column)[target_column].mean().sort_values(ascending=False)
        if len(group) < 2:
            continue
        spread = float(group.iloc[0] - group.iloc[-1])
        score = abs(spread / target_std) if target_std else 0.0
        insights.append(
            {
                "name": column,
                "type": "分类字段",
                "score": round(score, 3),
                "direction": "分组差异",
                "explanation": f"按「{column}」分组后，「{group.index[0]}」的平均「{target_column}」较高，分组差异值得关注。",
            }
        )

    return sorted(insights, key=lambda item: item["score"], reverse=True)[:6]


def _try_pycaret_model(
    model_df: pd.DataFrame,
    target_column: str,
    feature_columns: list[str],
) -> dict[str, Any] | None:
    try:
        from pycaret.regression import compare_models, pull, setup  # type: ignore
    except Exception as exc:
        return {"available": False, "reason": f"PyCaret 未安装或未启用：{exc}"}

    if len(model_df) < 12 or len(feature_columns) < 1 or model_df[target_column].nunique(dropna=True) < 2:
        return {"available": False, "reason": "有效数据量不足，暂不进行 PyCaret 自动建模。"}

    training_df = model_df[[*feature_columns, target_column]].copy()
    if len(training_df) > 500:
        training_df = training_df.sample(n=500, random_state=2026)

    try:
        output_buffer = io.StringIO()
        fold = min(3, max(2, len(training_df) // 6))
        with warnings.catch_warnings(), contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
            warnings.simplefilter("ignore")
            setup(
                data=training_df,
                target=target_column,
                session_id=2026,
                preprocess=True,
                numeric_imputation="median",
                categorical_imputation="mode",
                normalize=True,
                normalize_method="zscore",
                fold=fold,
                verbose=False,
                html=False,
                log_experiment=False,
                system_log=False,
            )
            best_model = compare_models(include=["lr", "ridge", "rf"], sort="MAE", n_select=1, verbose=False)
            leaderboard = pull()
        best_row = leaderboard.iloc[0] if not leaderboard.empty else pd.Series(dtype="object")
        metrics = {}
        for key in ("MAE", "R2", "RMSE"):
            value = best_row.get(key)
            if value is not None and not pd.isna(value):
                metrics[key.lower()] = clean_json_value(float(value))

        model_importance: list[dict[str, Any]] = []
        raw_values = None
        if hasattr(best_model, "feature_importances_"):
            raw_values = getattr(best_model, "feature_importances_")
        elif hasattr(best_model, "coef_"):
            raw_values = np.abs(np.ravel(getattr(best_model, "coef_")))
        if raw_values is not None and len(raw_values) == len(feature_columns):
            for column, score in zip(feature_columns, raw_values, strict=False):
                model_importance.append(
                    {
                        "name": column,
                        "type": "模型特征",
                        "score": clean_json_value(float(abs(score))),
                        "direction": "模型重要度",
                        "explanation": f"PyCaret 最佳模型认为「{column}」对「{target_column}」的解释权重较高。",
                    }
                )

        return {
            "available": True,
            "best_model": str(best_row.get("Model", type(best_model).__name__)),
            "metrics": metrics,
            "importance": sorted(model_importance, key=lambda item: item["score"] or 0, reverse=True)[:6],
            "fold": fold,
        }
    except Exception as exc:
        return {"available": False, "reason": f"PyCaret 建模未成功：{exc}"}


def _build_model_context(df: pd.DataFrame, profile: dict[str, Any]) -> dict[str, Any]:
    model_df, target_column, numeric_columns, categorical_columns = _prepare_model_frame(df, profile)
    if not target_column:
        return {
            "engine": "统计规则",
            "target_column": None,
            "plain_summary": "当前数据没有稳定的数值目标字段，系统先提供图表读法和基础统计解读。",
            "preprocessing": [],
            "important_features": [],
            "metrics": {},
        }

    feature_columns = [column for column in model_df.columns if column != target_column]
    fallback_importance = _statistical_importance(model_df, target_column, numeric_columns, categorical_columns)
    pycaret_result = _try_pycaret_model(model_df, target_column, feature_columns)
    pycaret_ok = bool(pycaret_result and pycaret_result.get("available"))
    importance = pycaret_result.get("importance") if pycaret_ok else []
    if not importance:
        importance = fallback_importance

    if pycaret_ok:
        engine = "PyCaret 自动建模"
        best_model = pycaret_result.get("best_model", "PyCaret 最佳模型")
        plain_summary = (
            f"PyCaret 已把「{target_column}」作为解释目标，完成缺失值处理、类别编码、标准化和自动模型比较，"
            f"当前最佳模型为「{best_model}」。下面的图表解释会结合模型关注字段和图表本身的高低变化。"
        )
        metrics = pycaret_result.get("metrics", {})
    else:
        engine = "统计规则"
        best_model = None
        reason = pycaret_result.get("reason") if pycaret_result else "PyCaret 未返回有效结果。"
        plain_summary = (
            f"当前未完成 PyCaret 自动建模，原因：{reason} 系统先用清洗后数据的相关性和分组差异解释图表。"
        )
        metrics = {}

    return {
        "engine": engine,
        "target_column": target_column,
        "best_model": best_model,
        "plain_summary": plain_summary,
        "preprocessing": ["缺失值处理", "类别编码", "数值标准化", "自动比较模型"] if pycaret_ok else ["相关性计算", "分组均值比较"],
        "important_features": importance,
        "metrics": metrics,
    }


def _model_sentence(fields: list[str], model_context: dict[str, Any]) -> str:
    target = model_context.get("target_column")
    features = model_context.get("important_features") or []
    if not target or not features:
        return "模型信息不足时，优先根据图中的最高点、最低点和变化方向进行判断。"

    field_set = {field for field in fields if field}
    matched = next((item for item in features if item.get("name") in field_set), None)
    focus = matched or features[0]
    engine = model_context.get("engine", "模型")
    return (
        f"{engine}提示：「{focus['name']}」与「{target}」的关系值得优先关注。"
        f"{focus.get('explanation', '')}"
    )


def _interpret_line(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    values = _extract_named_values(chart)
    value_name = _series_option(chart).get("name") or model_context.get("target_column") or "数值"
    trend_text, business_notes = _trend_description(values)
    findings = _top_bottom_findings(values)
    fields = ["时间", str(value_name)]
    return {
        "plain_language": f"这是一张趋势图，用来观察「{value_name}」随时间是否上升、下降或保持稳定。",
        "how_to_read": [
            "横轴通常是月份或日期，纵轴是对应时间段的汇总数值。",
            "线条越高，代表该时间段的数值越大；连续上扬代表趋势增强。",
            "尖峰和低谷往往对应活动、淡旺季、异常订单或数据录入问题。",
        ],
        "data_meaning": _compact_items([
            f"每一个点表示一个时间段的「{value_name}」汇总结果。",
            _field_value_explanation(str(value_name)),
            _named_value_example(values, "时间段", str(value_name)),
            _named_value_range(values, str(value_name)),
            "面积阴影用于强调走势，不代表额外字段。",
        ]),
        "key_findings": [trend_text, *findings],
        "business_questions": [
            "最高月份是否有促销、节假日或大客户订单？",
            "低谷月份是否存在缺货、渠道投放减少或异常退货？",
            *business_notes,
        ],
        "fields": fields,
    }


def _interpret_bar(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    values = _extract_named_values(chart)
    value_name = _series_option(chart).get("name") or model_context.get("target_column") or "数值"
    x_name = _axis_option(chart.get("option") or {}, "xAxis").get("name") or "分类"
    ordered = sorted(values, key=lambda item: item["value"], reverse=True)
    total = sum(item["value"] for item in values) or 0
    top_share = (ordered[0]["value"] / total * 100) if ordered and total else 0
    findings = _top_bottom_findings(values, "贡献最高")
    if ordered and total:
        findings.append(f"头部项目「{ordered[0]['name']}」约占当前图表总量的 {top_share:.1f}%。")
    fields = [str(x_name), str(value_name)]
    return {
        "plain_language": f"这是一张对比图，用来比较不同{fields[0]}在「{value_name}」上的贡献大小。",
        "how_to_read": [
            "每根柱子代表一个类别，柱子越高代表贡献越大。",
            "先看最高的几根柱子，它们通常是重点产品、重点地区或重点渠道。",
            "再看明显偏低的柱子，判断是自然低需求还是经营问题。",
        ],
        "data_meaning": _compact_items([
            f"横轴代表{fields[0]}，纵轴代表「{value_name}」的汇总值。",
            _field_value_explanation(str(value_name)),
            _named_value_example(values, str(fields[0]), str(value_name)),
            _named_value_range(values, str(value_name)),
            "柱子高度就是该类别对应的数值大小，两个柱子的高低差可以直接理解为两类之间的差距。",
            "排序靠前的类别通常更值得优先分析。",
        ]),
        "key_findings": findings,
        "business_questions": [
            "头部类别是否应增加库存、陈列或渠道资源？",
            "尾部类别是否需要优化价格、促销或下架策略？",
        ],
        "fields": fields,
    }


def _interpret_pie(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    values = _extract_named_values(chart)
    value_name = _series_option(chart).get("name") or model_context.get("target_column") or "数值"
    ordered = sorted(values, key=lambda item: item["value"], reverse=True)
    total = sum(item["value"] for item in values) or 0
    top3 = sum(item["value"] for item in ordered[:3])
    findings = _top_bottom_findings(values, "占比最高")
    if total:
        findings.append(f"前三项合计约占 {top3 / total * 100:.1f}%，可用来判断销售是否集中在少数类别。")
    return {
        "plain_language": f"这是一张占比图，用来查看「{value_name}」主要由哪些类别构成。",
        "how_to_read": [
            "扇区越大，代表该类别占整体比例越高。",
            "优先看最大扇区和前三个扇区，它们决定了整体结构。",
            "如果小扇区过多，说明类别比较分散，后续可合并为“其他”。",
        ],
        "data_meaning": _compact_items([
            f"每个扇区代表一个类别在「{value_name}」中的占比。",
            _field_value_explanation(str(value_name)),
            _named_value_example(values, "类别", str(value_name)),
            "扇区上的百分比表示该类别占全部已展示类别总量的比例。",
            "同一张饼图中，扇区越大，说明该类别占用的业务份额越高。",
            "占比图适合看结构，不适合精确比较细小差异。",
        ]),
        "key_findings": findings,
        "business_questions": [
            "销售是否过度依赖少数品类或渠道？",
            "低占比类别是潜力品类，还是应减少投入的长尾品类？",
        ],
        "fields": ["分类", str(value_name)],
    }


def _interpret_scatter(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    option = chart.get("option") or {}
    x_name = _axis_option(option, "xAxis").get("name") or "横轴字段"
    y_name = _axis_option(option, "yAxis").get("name") or "纵轴字段"
    points = _extract_scatter_points(chart)
    corr = None
    if len(points) >= 3:
        x_values = [point[0] for point in points]
        y_values = [point[1] for point in points]
        corr = float(np.corrcoef(x_values, y_values)[0, 1])
        if not np.isfinite(corr):
            corr = None
    relation = "关系较弱"
    if corr is not None:
        relation = "正向关系" if corr >= 0.35 else "反向关系" if corr <= -0.35 else "关系较弱"
    example = (
        f"例如一个点位于横轴 {_format_number(points[0][0])}、纵轴 {_format_number(points[0][1])}，"
        f"表示这条记录的「{x_name}」为 {_format_number(points[0][0])}，"
        f"「{y_name}」为 {_format_number(points[0][1])}。"
        if points
        else None
    )
    return {
        "plain_language": f"这是一张关系图，用来观察「{x_name}」和「{y_name}」是否一起变化。",
        "how_to_read": [
            "每个点通常代表一条清洗后的销售记录。",
            "点从左下到右上分布，说明两个字段可能同增同减。",
            "点从左上到右下分布，说明两个字段可能一高一低。",
            "远离大多数点的记录可能是异常订单或特殊业务场景。",
        ],
        "data_meaning": _compact_items([
            f"横向位置代表「{x_name}」，纵向位置代表「{y_name}」。",
            example,
            "图中的数字不是排名，而是每条记录在两个字段上的真实数值坐标。",
            "点越密集，说明这一区间的数据越常见。",
        ]),
        "key_findings": [
            f"当前散点整体呈{relation}。"
            + (f" 相关系数约为 {corr:.2f}。" if corr is not None else ""),
            "建议重点检查远离主体分布的点，它们可能影响平均值和预测模型。",
        ],
        "business_questions": [
            "高单价是否真的带来高销售额，还是销量被压低？",
            "异常点是否来自大客户订单、退货、录入错误或特殊折扣？",
        ],
        "fields": [str(x_name), str(y_name)],
    }


def _interpret_heatmap(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    pairs = _extract_heatmap_pairs(chart)
    unique_pairs = []
    seen = set()
    for pair in pairs:
        key = tuple(sorted([pair["x"], pair["y"]]))
        if key in seen:
            continue
        seen.add(key)
        unique_pairs.append(pair)
    ordered = sorted(unique_pairs, key=lambda item: abs(item["value"]), reverse=True)
    findings = []
    for pair in ordered[:3]:
        relation = "同向变化" if pair["value"] > 0 else "反向变化"
        findings.append(f"「{pair['x']}」与「{pair['y']}」呈{relation}，相关系数约为 {pair['value']:.2f}。")
    if not findings:
        findings.append("当前热力图没有明显的强相关字段。")
    example = (
        f"例如「{ordered[0]['x']}」与「{ordered[0]['y']}」的相关系数约为 {ordered[0]['value']:.2f}，"
        "表示二者线性变化关系较强。"
        if ordered
        else None
    )
    return {
        "plain_language": "这是一张相关性热力图，用来快速发现哪些数值字段之间关系更紧密。",
        "how_to_read": [
            "数值接近 1 表示两个字段更可能一起升高或一起降低。",
            "数值接近 -1 表示一个升高时另一个可能降低。",
            "数值接近 0 表示线性关系较弱，不能单独作为判断依据。",
        ],
        "data_meaning": _compact_items([
            "每个格子代表两个数值字段之间的相关系数。",
            "相关系数范围是 -1 到 1：越接近 1 越同向，越接近 -1 越反向，越接近 0 关系越弱。",
            example,
            "颜色只是辅助强调强弱，最终要结合具体数值和业务场景判断。",
        ]),
        "key_findings": findings,
        "business_questions": [
            "强相关字段是否存在重复含义，例如单价、数量和总金额？",
            "负相关字段是否反映折扣、价格带或客户类型差异？",
        ],
        "fields": list({item for pair in ordered[:3] for item in (pair["x"], pair["y"])}),
    }


def _interpret_factor_loading(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    cells = _extract_heatmap_cells(chart)
    ordered = sorted(cells, key=lambda item: abs(item["value"]), reverse=True)
    findings = []
    for cell in ordered[:5]:
        relation = "正向" if cell["value"] >= 0 else "反向"
        findings.append(f"「{cell['y']}」在「{cell['x']}」上的载荷较高，方向为{relation}，载荷值约 {cell['value']:.2f}。")
    if not findings:
        findings.append("当前字段之间没有形成明显的高载荷因子。")
    example = (
        f"例如「{ordered[0]['y']}」在「{ordered[0]['x']}」上的载荷值约为 {ordered[0]['value']:.2f}，"
        "说明这个字段与该综合因子的关联较强。"
        if ordered
        else None
    )
    return {
        "plain_language": "这是一张因子载荷热力图，用来说明每个原始字段更接近哪个综合因子。",
        "how_to_read": [
            "横轴是系统提取出的综合因子，纵轴是原始数值字段。",
            "颜色越深或绝对值越大，说明该字段越能代表这个因子。",
            "正值表示同向影响，负值表示反向影响；读业务含义时主要看绝对值大小。",
        ],
        "data_meaning": _compact_items([
            "载荷可以理解为字段和综合因子的关系强度。",
            "载荷值通常看绝对值：越接近 1 关系越强，越接近 0 关系越弱。",
            "正数表示同向关系，负数表示反向关系。",
            example,
            "同一因子下高载荷字段越集中，这个因子的业务含义越容易解释。",
        ]),
        "key_findings": findings,
        "business_questions": [
            "同一个因子下的高载荷字段是否都指向同一种业务现象？",
            "可以把因子命名为价格因子、销量因子、客单因子或规模因子吗？",
        ],
        "fields": list({item["y"] for item in ordered[:5]}),
    }


def _interpret_factor_contribution(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    values = _extract_named_values(chart)
    ordered = sorted(values, key=lambda item: item["value"], reverse=True)
    total = sum(item["value"] for item in values)
    findings = _top_bottom_findings(values, "解释力最高")
    if total:
        first_two = sum(item["value"] for item in ordered[:2])
        findings.append(f"前两个因子合计解释约 {first_two:.1f}% 的数据差异。")
    example = (
        f"例如「{ordered[0]['name']}」贡献率为 {_format_number(ordered[0]['value'])}%，"
        "表示它解释了这部分比例的数据差异。"
        if ordered
        else None
    )
    return {
        "plain_language": "这是一张因子贡献率图，用来判断哪些综合因子最能解释数据变化。",
        "how_to_read": [
            "柱子越高，说明该因子能解释的数据差异越多。",
            "通常优先解释贡献率最高的前两个或前三个因子。",
            "如果第一个因子特别高，说明多数变化可被一个核心经营因素概括。",
        ],
        "data_meaning": _compact_items([
            "贡献率表示该因子解释整体数据差异的比例。",
            example,
            "多个因子贡献率相加越高，说明这些因子越能概括原始数据中的主要变化。",
            "它不是销售额占比，而是模型对字段变化结构的概括能力。",
        ]),
        "key_findings": findings,
        "business_questions": [
            "贡献率最高的因子是否可解释为主经营驱动？",
            "低贡献因子是否只是细节差异，是否需要重点关注？",
        ],
        "fields": [item["name"] for item in ordered[:3]],
    }


def _interpret_factor_score_scatter(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    points = _extract_scatter_points(chart)
    x_name = _axis_option(chart.get("option") or {}, "xAxis").get("name") or "因子1"
    y_name = _axis_option(chart.get("option") or {}, "yAxis").get("name") or "因子2"
    findings = ["每个点代表一条清洗后的记录在两个综合因子上的得分位置。"]
    if points:
        x_values = [point[0] for point in points]
        y_values = [point[1] for point in points]
        findings.append(f"{x_name} 得分范围约 {_format_number(min(x_values))} 到 {_format_number(max(x_values))}。")
        findings.append(f"{y_name} 得分范围约 {_format_number(min(y_values))} 到 {_format_number(max(y_values))}。")
    return {
        "plain_language": "这是一张因子得分散点图，用来查看不同订单或记录在综合因子空间中的分布。",
        "how_to_read": [
            "每个点是一条数据记录，横轴和纵轴是两个最主要的综合因子。",
            "点聚在一起，说明这些记录结构相似。",
            "离主体很远的点，可能是特殊订单、异常金额、特殊客户或录入问题。",
        ],
        "data_meaning": _compact_items([
            "因子得分不是原始金额，而是记录在综合因子上的相对位置。",
            "横轴和纵轴的正负值表示记录相对平均水平的位置，正值更偏向该因子的正方向，负值更偏向反方向。",
            "离 0 越远，说明这条记录在该综合因子上的特征越明显。",
            "它适合做分群和异常观察，不适合直接当作销售额使用。",
        ]),
        "key_findings": findings,
        "business_questions": [
            "离群点是否对应特殊客户、大额订单或异常数据？",
            "密集区域是否可作为常规订单画像？",
        ],
        "fields": [str(x_name), str(y_name)],
    }


def _interpret_factor_key_fields(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    values = _extract_named_values(chart)
    findings = _top_bottom_findings(values, "综合强度最高")
    return {
        "plain_language": "这是一张因子关键字段强度图，用来找出哪些原始字段最能代表整体数据变化。",
        "how_to_read": [
            "柱子越高，说明该字段在综合因子中的权重越强。",
            "靠前字段通常是后续解释经营变化时最该优先看的字段。",
            "如果多个字段强度接近，说明数据变化不是由单一字段决定。",
        ],
        "data_meaning": _compact_items([
            "综合载荷强度来自字段在多个因子上的载荷大小。",
            _named_value_example(values, "字段", "综合载荷强度"),
            _named_value_range(values, "综合载荷强度"),
            "柱子越高，说明该字段越能代表数据里的主要变化结构。",
            "它表示解释力强弱，不表示字段本身数值大小。",
        ]),
        "key_findings": findings,
        "business_questions": [
            "高强度字段是否与销售额、数量、单价或折扣有关？",
            "这些字段能否作为后续经营分析的核心指标？",
        ],
        "fields": [item["name"] for item in values[:5]],
    }


def _interpret_factor_profile(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    option = chart.get("option") or {}
    indicators = [item.get("name") for item in (option.get("radar") or {}).get("indicator", []) if isinstance(item, dict)]
    series_data = _series_option(chart).get("data") or []
    findings = []
    for item in series_data[:4]:
        if not isinstance(item, dict):
            continue
        values = item.get("value") or []
        if not values:
            continue
        max_index = int(np.argmax(values))
        if max_index < len(indicators):
            findings.append(f"「{item.get('name', '某因子')}」在「{indicators[max_index]}」上最突出。")
    if not findings:
        findings.append("当前因子画像没有明显突出的关键字段。")
    return {
        "plain_language": "这是一张因子画像雷达图，用来给每个综合因子寻找业务含义。",
        "how_to_read": [
            "每条线代表一个综合因子。",
            "线条在某个字段方向越靠外，说明该因子越受这个字段影响。",
            "可以根据最突出的字段给因子命名，例如价格因子、规模因子或订单活跃因子。",
        ],
        "data_meaning": _compact_items([
            "雷达值是载荷归一化后的相对强度，不是原始字段数值。",
            "每个方向的数值范围通常是 0 到 100，越靠外表示该因子越受这个字段影响。",
            "不同因子的线条可用于比较谁更依赖某个字段，但不能直接当作金额或数量。",
            "它帮助理解因子含义，适合写入论文中的因子命名过程。",
        ]),
        "key_findings": findings,
        "business_questions": [
            "每个因子最适合用什么业务名称概括？",
            "哪些因子可用于后续用户分群、订单分群或经营建议？",
        ],
        "fields": [str(item) for item in indicators],
    }


def _interpret_boxplot(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    option = chart.get("option") or {}
    labels = _axis_option(option, "xAxis").get("data") or []
    data = _series_option(chart).get("data") or []
    medians: list[dict[str, Any]] = []
    for index, row in enumerate(data):
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        median = _as_number(row[2])
        spread = None
        high = _as_number(row[4])
        low = _as_number(row[0])
        if high is not None and low is not None:
            spread = high - low
        if median is not None:
            medians.append({"name": str(labels[index]) if index < len(labels) else f"分类 {index + 1}", "value": median, "spread": spread})
    ordered = sorted(medians, key=lambda item: item["value"], reverse=True)
    findings = _top_bottom_findings(ordered, "中位数最高") if ordered else ["箱线图中没有足够的有效分布数据。"]
    widest = max(ordered, key=lambda item: item.get("spread") or 0) if ordered else None
    if widest and widest.get("spread") is not None:
        findings.append(f"「{widest['name']}」的波动范围较大，最高最低差约 {_format_number(widest['spread'])}。")
    return {
        "plain_language": "这是一张箱线图，用来比较不同分类下数值的典型水平和波动范围。",
        "how_to_read": [
            "盒子中间的线通常代表中位数，更适合看典型水平。",
            "盒子越高或上下须越长，说明该分类内部波动越大。",
            "波动很大的分类需要检查是否存在异常大单、退货或录入问题。",
        ],
        "data_meaning": _compact_items([
            "每个分类展示最小值、下四分位数、中位数、上四分位数和最大值。",
            "盒子中间线是中位数，表示该分类较典型的一条记录水平。",
            "盒子上下边界表示中间 50% 数据的范围，范围越宽代表波动越大。",
            "上下须表示更低和更高的正常范围，超出主体的点通常要重点检查。",
            "箱线图不强调总量，而强调分布和稳定性。",
        ]),
        "key_findings": findings,
        "business_questions": [
            "哪个分类的典型销售表现更好？",
            "哪个分类波动更大，是否需要拆分客户或订单场景？",
        ],
        "fields": ["分类", model_context.get("target_column") or "数值"],
    }


def _interpret_treemap(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    values = _extract_named_values(chart)
    findings = _top_bottom_findings(values, "面积最大")
    total = sum(item["value"] for item in values) or 0
    ordered = sorted(values, key=lambda item: item["value"], reverse=True)
    if ordered and total:
        findings.append(f"最大板块「{ordered[0]['name']}」约占 {ordered[0]['value'] / total * 100:.1f}%。")
    return {
        "plain_language": "这是一张矩形树图，用面积大小表示不同类别的贡献大小。",
        "how_to_read": [
            "矩形面积越大，代表该类别贡献越高。",
            "先看最大的几个矩形，它们通常是经营重点。",
            "如果面积集中在少数矩形，说明业务集中度较高。",
        ],
        "data_meaning": _compact_items([
            "每个矩形代表一个分类项目。",
            "面积大小代表该分类的汇总数值。",
            _field_value_explanation(str(model_context.get("target_column") or "数值")),
            _named_value_example(values, "分类", str(model_context.get("target_column") or "数值")),
            "矩形越大，说明该分类在整体中的业务份额越高。",
        ]),
        "key_findings": findings,
        "business_questions": [
            "销售是否集中在少数类别？",
            "头部类别是否应该增加运营资源，长尾类别是否应优化？",
        ],
        "fields": ["分类", model_context.get("target_column") or "数值"],
    }


def _interpret_radar(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    option = chart.get("option") or {}
    indicators = [item.get("name") for item in (option.get("radar") or {}).get("indicator", []) if isinstance(item, dict)]
    series_data = _series_option(chart).get("data") or []
    findings = []
    for item in series_data[:3]:
        if not isinstance(item, dict):
            continue
        values = item.get("value") or []
        if not values:
            continue
        max_index = int(np.argmax(values))
        if max_index < len(indicators):
            findings.append(f"「{item.get('name', '某类别')}」在「{indicators[max_index]}」上相对更突出。")
    if not findings:
        findings.append("雷达图用于综合比较多个指标，当前没有明显突出的单项。")
    return {
        "plain_language": "这是一张雷达图，用来对比不同类别在多个指标上的综合表现。",
        "how_to_read": [
            "图形越靠外，代表该指标相对表现越强。",
            "面积越大，通常说明综合表现越强，但仍要看具体指标。",
            "某一方向特别突出，说明该类别在对应指标上有优势。",
        ],
        "data_meaning": _compact_items([
            "每个方向代表一个数值指标。",
            "这里的值经过归一化，适合比较强弱，不代表原始金额或数量。",
            "雷达图中 100 通常代表当前展示类别中的最高水平，其他数值表示相对最高水平的比例。",
            "某个方向越靠外，说明该类别在这个指标上越接近当前最高表现。",
        ]),
        "key_findings": findings,
        "business_questions": [
            "哪些类别综合表现更平衡？",
            "哪些类别只在单个指标突出，是否存在短板？",
        ],
        "fields": [str(item) for item in indicators],
    }


def _interpret_chart(chart: dict[str, Any], model_context: dict[str, Any]) -> dict[str, Any]:
    chart_type = chart.get("type", "chart")
    chart_id = str(chart.get("id") or "")
    if chart_id == "factor_loading_heatmap":
        detail = _interpret_factor_loading(chart, model_context)
        type_label = "因子载荷热力图"
    elif chart_id == "factor_contribution_bar":
        detail = _interpret_factor_contribution(chart, model_context)
        type_label = "因子贡献率图"
    elif chart_id == "factor_score_scatter":
        detail = _interpret_factor_score_scatter(chart, model_context)
        type_label = "因子得分散点图"
    elif chart_id == "factor_key_fields_bar":
        detail = _interpret_factor_key_fields(chart, model_context)
        type_label = "因子关键字段图"
    elif chart_id == "factor_profile_radar":
        detail = _interpret_factor_profile(chart, model_context)
        type_label = "因子画像雷达图"
    elif chart_type == "line":
        detail = _interpret_line(chart, model_context)
        type_label = "趋势图"
    elif chart_type == "bar":
        detail = _interpret_bar(chart, model_context)
        type_label = "柱状对比图"
    elif chart_type == "pie":
        detail = _interpret_pie(chart, model_context)
        type_label = "占比图"
    elif chart_type == "scatter":
        detail = _interpret_scatter(chart, model_context)
        type_label = "散点关系图"
    elif chart_type == "heatmap":
        detail = _interpret_heatmap(chart, model_context)
        type_label = "相关性热力图"
    elif chart_type == "boxplot":
        detail = _interpret_boxplot(chart, model_context)
        type_label = "箱线分布图"
    elif chart_type == "treemap":
        detail = _interpret_treemap(chart, model_context)
        type_label = "矩形树图"
    elif chart_type == "radar":
        detail = _interpret_radar(chart, model_context)
        type_label = "雷达图"
    else:
        detail = {
            "plain_language": chart.get("reason", "这张图用于辅助理解清洗后的数据。"),
            "how_to_read": ["先看坐标轴或图例，再看数值高低和异常位置。"],
            "data_meaning": ["图中数值来自清洗后的数据表。"],
            "key_findings": ["该图表类型暂未配置专门解释，系统提供通用读图建议。"],
            "business_questions": ["这张图是否能回答当前经营问题？"],
            "fields": [],
        }
        type_label = str(chart_type)

    fields = [str(field) for field in detail.get("fields", []) if field]
    return {
        "id": chart.get("id"),
        "title": chart.get("title", "未命名图表"),
        "type": chart_type,
        "type_label": type_label,
        "reason": chart.get("reason", ""),
        "model_insight": _model_sentence(fields, model_context),
        **detail,
    }


def analyze_dataset_charts(
    df: pd.DataFrame,
    profile: dict[str, Any],
    charts: list[dict[str, Any]],
    filename: str,
    dataset_id: int,
) -> dict[str, Any]:
    """Explain chart results with PyCaret-assisted modeling and readable rules."""
    model_context = _build_model_context(df, profile)
    chart_analyses = [_interpret_chart(chart, model_context) for chart in charts]
    target_column = model_context.get("target_column") or "主要数值字段"

    return {
        "dataset_id": dataset_id,
        "filename": filename,
        "engine": model_context.get("engine", "统计规则"),
        "summary": {
            "rows": int(df.shape[0]),
            "columns": int(df.shape[1]),
            "chart_count": len(charts),
            "target_column": target_column,
        },
        "model_insight": model_context,
        "charts": chart_analyses,
        "reading_tips": [
            "先看图表标题，确认它回答的是趋势、对比、占比还是字段关系。",
            "再看坐标轴、图例和数值单位，确认柱高、点位、百分比或相关系数分别代表什么。",
            "再看最高点、最低点和变化方向，这些通常对应最需要解释的业务现象。",
            "最后结合 PyCaret 提示的关键字段，判断哪些因素更可能影响主要经营指标。",
        ],
    }
