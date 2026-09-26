"""Gradient-boosted RT-price model versus the deterministic score (DES-GM-ML).

Trained on >= 28 days, tested on the following >= 7 days; reports both
Spearman values plus permutation importances. No model is served by the API.
"""

from datetime import date, datetime

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

FEATURES = (
    "hour_of_day",
    "peak_flag",
    "temperature",
    "price_spread",
    "load_pressure",
    "outage_pressure",
    "congestion_pressure",
    "population_weight",
)
MIN_TRAIN_DAYS = 28
MIN_TEST_DAYS = 7


def _row_date(row: dict) -> str:
    stamp = row["delivery_hour"]
    if isinstance(stamp, str):
        return stamp[:10]
    if isinstance(stamp, datetime | date):
        return stamp.isoformat()[:10]
    return str(stamp)[:10]


def split_by_date(
    rows: list[dict], train: tuple[date, date], test: tuple[date, date]
) -> tuple[list[dict], list[dict]]:
    """Split rows into inclusive train/test date ranges, preserving order."""
    if test[0] <= train[1]:
        raise ValueError(f"train {train} and test {test} ranges overlap")
    train_days = (train[1] - train[0]).days + 1
    if train_days < MIN_TRAIN_DAYS:
        raise ValueError(f"train range has {train_days} days, need {MIN_TRAIN_DAYS}")
    test_days = (test[1] - test[0]).days + 1
    if test_days < MIN_TEST_DAYS:
        raise ValueError(f"test range has {test_days} days, need {MIN_TEST_DAYS}")
    lo_train, hi_train = train[0].isoformat(), train[1].isoformat()
    lo_test, hi_test = test[0].isoformat(), test[1].isoformat()
    train_rows, test_rows = [], []
    for row in rows:
        day = _row_date(row)
        if lo_train <= day <= hi_train:
            train_rows.append(row)
        elif lo_test <= day <= hi_test:
            test_rows.append(row)
    return train_rows, test_rows


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        average = (start + end) / 2 + 1
        for index in range(start, end + 1):
            ranks[order[index]] = average
        start = end + 1
    return ranks


def spearman(left: list[float], right: list[float]) -> float:
    """Spearman rank correlation (average ranks, 0.0 when undefined)."""
    xs = _ranks([float(value) for value in left])
    ys = _ranks([float(value) for value in right])
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(xs, ys, strict=True))
    den_x = sum((a - mean_x) ** 2 for a in xs) ** 0.5
    den_y = sum((b - mean_y) ** 2 for b in ys) ** 0.5
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def evaluate(rows: list[dict], train: tuple[date, date], test: tuple[date, date]) -> dict:
    """Train on train, score deterministic and model Spearman on test."""
    train_rows, test_rows = split_by_date(rows, train, test)
    features = list(FEATURES)
    x_train = np.array([[row[name] for name in features] for row in train_rows])
    y_train = np.array([row["realized_rt"] for row in train_rows])
    x_test = np.array([[row[name] for name in features] for row in test_rows])
    y_test = np.array([row["realized_rt"] for row in test_rows])
    model = HistGradientBoostingRegressor(random_state=0)
    model.fit(x_train, y_train)
    predictions = [float(value) for value in model.predict(x_test)]
    realized = [float(value) for value in y_test]
    importances = permutation_importance(model, x_test, y_test, random_state=0)
    return {
        "model": model,
        "predictions": predictions,
        "spearman_score": spearman([row["deterministic_score"] for row in test_rows], realized),
        "spearman_model": spearman(predictions, realized),
        "importances": {
            name: float(value)
            for name, value in zip(features, importances.importances_mean, strict=True)
        },
    }
