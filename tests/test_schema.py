import pytest
import pandas as pd
import numpy as np
from app.tools.python_analysis import (
    descriptive_stats,
    detect_outliers,
    percentage_change,
    correlation_matrix,
    null_report,
    validate_result,
)


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "month": ["Jan", "Feb", "Mar", "Apr", "May"],
        "revenue": [1000.0, 1200.0, 900.0, 1500.0, 1100.0],
        "orders": [50, 60, 45, 75, 55],
    })


def test_descriptive_stats_numeric(sample_df):
    stats = descriptive_stats(sample_df)
    assert "revenue" in stats
    assert "count" in stats["revenue"]


def test_descriptive_stats_empty():
    df = pd.DataFrame({"name": ["a", "b"]})
    stats = descriptive_stats(df)
    assert stats == {}


def test_detect_outliers_finds_outlier():
    df = pd.DataFrame({"val": [10, 12, 11, 10, 200, 11, 9]})
    result = detect_outliers(df, "val")
    assert result["outliers_count"] > 0


def test_detect_outliers_no_outlier(sample_df):
    result = detect_outliers(sample_df, "revenue")
    assert "outliers_count" in result


def test_detect_outliers_missing_column(sample_df):
    result = detect_outliers(sample_df, "nonexistent")
    assert "error" in result


def test_percentage_change(sample_df):
    result = percentage_change(sample_df, "revenue", "month")
    assert "revenue_pct_change" in result.columns


def test_percentage_change_missing_column(sample_df):
    result = percentage_change(sample_df, "nonexistent")
    assert "revenue" in result.columns


def test_correlation_matrix(sample_df):
    result = correlation_matrix(sample_df)
    assert "revenue" in result
    assert "orders" in result["revenue"]


def test_correlation_matrix_single_column():
    df = pd.DataFrame({"a": [1, 2, 3]})
    result = correlation_matrix(df)
    assert result == {}


def test_null_report(sample_df):
    report = null_report(sample_df)
    assert "revenue" in report
    assert report["revenue"]["null_count"] == 0


def test_null_report_with_nulls():
    df = pd.DataFrame({"a": [1, None, 3], "b": [None, None, None]})
    report = null_report(df)
    assert report["a"]["null_count"] == 1
    assert report["b"]["null_pct"] == 100.0


def test_validate_result_empty():
    df = pd.DataFrame()
    result = validate_result(df)
    assert not result["ok"]
    assert any("empty" in i.lower() for i in result["issues"])


def test_validate_result_ok(sample_df):
    result = validate_result(sample_df)
    assert "ok" in result
