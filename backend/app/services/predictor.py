from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from app.services.data_cleaner import clean_json_value, pick_date_column, pick_target_column


def _try_pycaret_regression(df: pd.DataFrame, target_column: str) -> tuple[str, dict[str, Any]] | None:
    """Try PyCaret when installed; failures fall back to deterministic sklearn models."""
    try:
        from pycaret.regression import compare_models, pull, setup  # type: ignore
    except Exception:
        return None

    try:
        setup(df, target=target_column, session_id=2026, verbose=False, html=False)
        compare_models(sort="MAE", n_select=1)
        leaderboard = pull()
        best_name = str(leaderboard.iloc[0].get("Model", "PyCaret AutoML"))
        return "PyCaret AutoML", {"best_model": best_name}
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

    pycaret_info = _try_pycaret_regression(pd.concat([features, target], axis=1), target_column)

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
        algorithm = f"{pycaret_info[0]} 辅助比较 + {algorithm}"

    metrics = {
        "mae": round(best_mae, 3),
        "r2": round(best_r2, 3),
        "training_rows": int(len(target)),
        "pycaret": pycaret_info[1] if pycaret_info else None,
    }
    summary = (
        f"系统以 {target_column} 为预测目标，"
        f"使用 {algorithm} 生成未来 {periods} 期预测，"
        f"验证集 MAE 为 {metrics['mae']}。"
    )

    return {
        "target_column": target_column,
        "date_column": date_column,
        "algorithm": algorithm,
        "metrics": {key: clean_json_value(value) for key, value in metrics.items()},
        "predictions": prediction_rows,
        "summary": summary,
    }
