import contextlib
import io
import warnings
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from app.services.data_cleaner import clean_json_value, pick_date_column, pick_target_column


def _metric_value(row: pd.Series, key: str) -> float | None:
    value = row.get(key)
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _try_pycaret_preprocessed_forecast(
    supervised_df: pd.DataFrame,
    target_column: str,
    future_features: pd.DataFrame,
) -> tuple[list[float], dict[str, Any]] | None:
    """Use PyCaret as the main AutoML engine when it is available."""
    try:
        from pycaret.regression import compare_models, finalize_model, predict_model, pull, setup  # type: ignore
    except Exception:
        return None

    try:
        fold = min(5, max(2, len(supervised_df) - 1))
        output_buffer = io.StringIO()
        with warnings.catch_warnings(), contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
            warnings.simplefilter("ignore")
            setup(
                supervised_df,
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
            best_model = compare_models(sort="MAE", n_select=1, exclude=["lightgbm"], verbose=False)
            leaderboard = pull()
            best_row = leaderboard.iloc[0] if not leaderboard.empty else pd.Series(dtype="object")
            final_model = finalize_model(best_model)
            prediction_frame = predict_model(final_model, data=future_features.copy(), verbose=False)
        prediction_column = next(
            (
                column
                for column in ("prediction_label", "Label")
                if column in prediction_frame.columns
            ),
            None,
        )
        if not prediction_column:
            extra_columns = [column for column in prediction_frame.columns if column not in future_features.columns]
            prediction_column = extra_columns[-1] if extra_columns else None
        if not prediction_column:
            return None

        predictions = pd.to_numeric(prediction_frame[prediction_column], errors="coerce").dropna().tolist()
        if len(predictions) != len(future_features):
            return None

        info = {
            "stage": "PyCaret 自动建模",
            "preprocessing": ["缺失值填补", "类别编码", "数值标准化", "自动模型比较", "最佳模型预测"],
            "best_model": str(best_row.get("Model", "PyCaret AutoML")),
            "excluded_models": ["LightGBM"],
            "mae": clean_json_value(_metric_value(best_row, "MAE")),
            "r2": clean_json_value(_metric_value(best_row, "R2")),
            "fold": fold,
        }
        return [float(value) for value in predictions], info
    except Exception:
        return None


def _prepare_supervised_frame(
    df: pd.DataFrame,
    target_column: str,
    date_column: str | None,
) -> tuple[pd.DataFrame, pd.Series, pd.Timestamp | None]:
    data = df.copy()
    last_date: pd.Timestamp | None = None
    if date_column:
        data[date_column] = pd.to_datetime(data[date_column], errors="coerce")
        data = data.dropna(subset=[date_column, target_column])
        grouped = data.groupby(data[date_column].dt.to_period("M"))[target_column].sum().reset_index()
        grouped[date_column] = grouped[date_column].dt.to_timestamp()
        grouped = grouped.sort_values(date_column)
        last_date = grouped[date_column].max()
        supervised = pd.DataFrame(
            {
                "index": np.arange(len(grouped), dtype=float),
                "month": grouped[date_column].dt.month.astype(float),
                "quarter": grouped[date_column].dt.quarter.astype(float),
                target_column: grouped[target_column].astype(float),
            }
        )
    else:
        data = data.dropna(subset=[target_column]).reset_index(drop=True)
        supervised = pd.DataFrame(
            {
                "index": np.arange(len(data), dtype=float),
                target_column: pd.to_numeric(data[target_column], errors="coerce"),
            }
        ).dropna()

    features = supervised.drop(columns=[target_column])
    target = supervised[target_column]
    return features, target, last_date


def _build_business_advice(
    target_column: str,
    periods: int,
    prediction_rows: list[dict[str, Any]],
    metrics: dict[str, Any],
    history: pd.Series,
) -> dict[str, Any]:
    """Turn model output into plain business guidance for non-technical users."""
    values = [
        float(row["predicted_value"])
        for row in prediction_rows
        if row.get("predicted_value") is not None and np.isfinite(float(row["predicted_value"]))
    ]
    if not values:
        return {}

    first = values[0]
    last = values[-1]
    average = float(np.mean(values))
    change = last - first
    change_rate = (change / first * 100) if first else 0.0
    abs_rate = abs(change_rate)
    direction = "stable" if abs_rate < 5 else "up" if change > 0 else "down"
    trend_label = "上升" if direction == "up" else "下降" if direction == "down" else "基本平稳"

    history_values = pd.to_numeric(history, errors="coerce").dropna()
    history_average = float(history_values.mean()) if not history_values.empty else None
    volatility_rate = float(np.std(values) / average * 100) if average else 0.0
    mae = metrics.get("mae")
    r2 = metrics.get("r2")
    mae_rate = (float(mae) / average * 100) if average and isinstance(mae, (int, float)) else None

    confidence_score = 0
    if isinstance(r2, (int, float)) and r2 >= 0.5:
        confidence_score += 2
    elif isinstance(r2, (int, float)) and r2 >= 0.1:
        confidence_score += 1
    elif isinstance(r2, (int, float)) and r2 < -0.1:
        confidence_score -= 1

    if mae_rate is None:
        confidence_score += 1
    elif mae_rate <= 25:
        confidence_score += 2
    elif mae_rate <= 45:
        confidence_score += 1
    else:
        confidence_score -= 1

    if len(history_values) >= 8:
        confidence_score += 1

    confidence = "较高" if confidence_score >= 3 else "中等" if confidence_score >= 1 else "较低"
    confidence_text = (
        "历史验证表现较好，可以作为计划参考。"
        if confidence == "较高"
        else "预测有参考价值，但仍需要结合业务经验判断。"
        if confidence == "中等"
        else "模型解释力偏弱，更适合看趋势方向，不建议单独作为最终决策依据。"
    )

    target_focus = "该指标"
    if any(keyword in target_column for keyword in ("金额", "销售额", "收入", "营收", "实付")):
        target_focus = "销售额和回款目标"
    elif any(keyword in target_column for keyword in ("数量", "销量", "件数")):
        target_focus = "备货数量和交付能力"
    elif any(keyword in target_column for keyword in ("价格", "单价")):
        target_focus = "价格带和毛利空间"

    plain_summary = (
        f"预测值整体波动不大，未来平均约为 {average:.2f}，可以按常规节奏安排经营计划。"
        if direction == "stable"
        else f"预测值从 {first:.2f} 变化到 {last:.2f}，变化约 {abs(change):.2f}，幅度约 {abs_rate:.1f}%。"
    )

    suggestions: list[str] = []
    if direction == "up":
        suggestions.append(f"{target_column} 有上升迹象，建议提前核对{target_focus}，避免需求上升时准备不足。")
    elif direction == "down":
        suggestions.append(f"{target_column} 有回落迹象，建议控制新增采购和库存压力，优先观察促销、渠道投放或产品结构是否需要调整。")
    else:
        suggestions.append(f"{target_column} 预计较平稳，建议维持当前节奏，并重点观察节假日、渠道活动或异常订单带来的短期波动。")

    if history_average:
        if average >= history_average * 1.15:
            suggestions.append("预测均值明显高于历史均值，可适当提高热销品类备货和销售资源投入。")
        elif average <= history_average * 0.85:
            suggestions.append("预测均值低于历史均值，建议谨慎设定采购计划，并优先提升库存周转。")

    if volatility_rate >= 25:
        suggestions.append("预测结果波动较明显，建议按高低峰分批备货，不要一次性压入过多库存。")

    if confidence == "较低":
        suggestions.append("当前数据对模型支持不足，建议补充更多历史销售记录后再作为经营决策依据。")

    method_note = (
        "本次预测已启用 PyCaret 完成缺失值处理、类别编码、标准化、自动模型比较和最佳模型预测。"
        if metrics.get("preprocess_engine") == "PyCaret"
        else "当前环境未启用 PyCaret，系统使用 scikit-learn 回退模型完成预测。"
    )

    return {
        "title": f"未来 {periods} 期{target_column}预计{trend_label}",
        "trend": direction,
        "trend_label": trend_label,
        "plain_summary": plain_summary,
        "confidence": confidence,
        "confidence_text": confidence_text,
        "average": round(average, 2),
        "change": round(change, 2),
        "change_rate": round(change_rate, 2),
        "mae_rate": round(mae_rate, 2) if mae_rate is not None else None,
        "history_average": round(history_average, 2) if history_average is not None else None,
        "volatility_rate": round(volatility_rate, 2),
        "suggestions": suggestions,
        "method_note": method_note,
    }


def forecast_dataframe(
    df: pd.DataFrame,
    periods: int = 6,
    target_column: str | None = None,
    date_column: str | None = None,
) -> dict[str, Any]:
    """Forecast future sales trend using PyCaret if available, otherwise sklearn."""
    target_column = target_column or pick_target_column(df)
    date_column = date_column or pick_date_column(df)
    if not target_column:
        raise ValueError("没有可预测的数值字段")

    df[target_column] = pd.to_numeric(df[target_column], errors="coerce")
    features, target, last_date = _prepare_supervised_frame(df, target_column, date_column)
    if len(target) < 3:
        raise ValueError("有效数据量太少，至少需要 3 条记录才能预测")

    test_size = 0.25 if len(target) >= 8 else 0.34
    x_train, x_test, y_train, y_test = train_test_split(features, target, test_size=test_size, shuffle=False)
    candidates = [
        ("线性回归", LinearRegression()),
        ("随机森林回归", RandomForestRegressor(n_estimators=120, random_state=2026)),
    ]

    best_name = ""
    best_model = None
    best_mae = float("inf")
    best_r2 = 0.0
    for name, model in candidates:
        model.fit(x_train, y_train)
        predictions = model.predict(x_test)
        mae = mean_absolute_error(y_test, predictions)
        r2 = r2_score(y_test, predictions) if len(y_test) > 1 else 0.0
        if mae < best_mae:
            best_name = name
            best_model = model
            best_mae = float(mae)
            best_r2 = float(r2)

    assert best_model is not None
    best_model.fit(features, target)
    start_index = int(features["index"].max()) + 1
    future_features = pd.DataFrame({"index": np.arange(start_index, start_index + periods, dtype=float)})
    if "month" in features.columns and last_date is not None:
        future_dates = pd.date_range(last_date + pd.offsets.MonthBegin(1), periods=periods, freq="MS")
        future_features["month"] = future_dates.month.astype(float)
        future_features["quarter"] = future_dates.quarter.astype(float)
    else:
        future_dates = [None] * periods

    supervised_df = pd.concat([features, target], axis=1)
    pycaret_result = _try_pycaret_preprocessed_forecast(
        supervised_df,
        target_column,
        future_features[features.columns],
    )
    pycaret_info = pycaret_result[1] if pycaret_result else None
    if pycaret_result:
        future_values = pycaret_result[0]
    else:
        future_values = best_model.predict(future_features[features.columns]).tolist()

    prediction_rows = []
    for index, value in enumerate(future_values):
        date_value = future_dates[index]
        prediction_rows.append(
            {
                "period": date_value.strftime("%Y-%m") if isinstance(date_value, (pd.Timestamp, datetime)) else f"未来第 {index + 1} 期",
                "predicted_value": round(float(max(0, value)), 2),
            }
        )

    algorithm = f"scikit-learn {best_name}"
    if pycaret_info:
        algorithm = f"PyCaret AutoML（{pycaret_info.get('best_model', '最佳回归模型')}）"

    metrics = {
        "mae": round(pycaret_info.get("mae", best_mae), 3) if pycaret_info and pycaret_info.get("mae") is not None else round(best_mae, 3),
        "r2": round(pycaret_info.get("r2", best_r2), 3) if pycaret_info and pycaret_info.get("r2") is not None else round(best_r2, 3),
        "training_rows": int(len(target)),
        "preprocess_engine": "PyCaret" if pycaret_info else "scikit-learn",
        "fallback_algorithm": f"scikit-learn {best_name}",
        "pycaret": pycaret_info,
    }
    business_advice = _build_business_advice(target_column, periods, prediction_rows, metrics, target)
    metrics["business_advice"] = business_advice

    first_suggestion = business_advice.get("suggestions", [""])[0] if business_advice else ""
    summary = (
        f"系统以 {target_column} 为预测目标，"
        f"使用 {algorithm} 生成未来 {periods} 期预测，"
        f"验证集 MAE 为 {metrics['mae']}。"
        f"{business_advice.get('plain_summary', '')}"
        f"{first_suggestion}"
    )

    return {
        "target_column": target_column,
        "date_column": date_column,
        "algorithm": algorithm,
        "metrics": {key: clean_json_value(value) for key, value in metrics.items()},
        "predictions": prediction_rows,
        "summary": summary,
    }
