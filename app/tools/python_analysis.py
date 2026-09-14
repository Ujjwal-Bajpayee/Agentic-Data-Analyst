import pandas as pd
import numpy as np
from typing import Any


class AnalysisResult:
    def __init__(self, summary: str, stats: dict):
        self.summary = summary
        self.stats = stats


def descriptive_stats(df: pd.DataFrame) -> dict:
    numeric = df.select_dtypes(include=[np.number])
    if numeric.empty:
        return {}
    desc = numeric.describe().to_dict()
    return desc


def detect_outliers(df: pd.DataFrame, column: str) -> dict:
    if column not in df.columns:
        return {"error": f"Column '{column}' not found"}
    series = pd.to_numeric(df[column], errors="coerce").dropna()
    if series.empty:
        return {"outliers_count": 0}
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = series[(series < lower) | (series > upper)]
    return {
        "outliers_count": int(len(outliers)),
        "lower_bound": float(lower),
        "upper_bound": float(upper),
        "outlier_values": outliers.tolist()[:20],
    }


def percentage_change(df: pd.DataFrame, value_col: str, sort_col: str | None = None) -> pd.DataFrame:
    if value_col not in df.columns:
        return df
    out = df.copy()
    if sort_col and sort_col in df.columns:
        out = out.sort_values(sort_col)
    out[f"{value_col}_pct_change"] = out[value_col].pct_change() * 100
    return out


def correlation_matrix(df: pd.DataFrame) -> dict:
    numeric = df.select_dtypes(include=[np.number])
    if numeric.shape[1] < 2:
        return {}
    return numeric.corr().round(4).to_dict()


def null_report(df: pd.DataFrame) -> dict:
    nulls = df.isnull().sum()
    pct = (nulls / len(df) * 100).round(2)
    return {col: {"null_count": int(nulls[col]), "null_pct": float(pct[col])} for col in df.columns}


def validate_result(df: pd.DataFrame) -> dict:
    issues = []
    if df.empty:
        issues.append("Result set is empty.")
        return {"ok": False, "issues": issues}

    null_info = null_report(df)
    high_null_cols = [c for c, v in null_info.items() if v["null_pct"] > 50]
    if high_null_cols:
        issues.append(f"High null rate (>50%) in columns: {high_null_cols}")

    numeric = df.select_dtypes(include=[np.number])
    for col in numeric.columns:
        col_lower = col.lower()
        col_min = numeric[col].min()
        is_monetary = "revenue" in col_lower or "amount" in col_lower or "price" in col_lower
        if is_monetary and col_min < 0:
            issues.append(f"Column '{col}' has negative values which may be unexpected for a monetary metric.")

    return {"ok": len(issues) == 0, "issues": issues}
