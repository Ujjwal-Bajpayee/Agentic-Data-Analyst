import pytest
import pandas as pd
from app.db.connection import build_engine, ensure_demo_database, test_connection as check_db_connection, get_demo_db_path
from app.tools.schema import prune_schema_for_question
from app.tools.sql_validator import validate_sql, audit_query_performance, check_cartesian_joins
from app.agents.visualization_agent import _build_plotly_figure
from fastapi.testclient import TestClient
from main import app


def test_ensure_demo_database():
    engine = ensure_demo_database()
    ok, err = check_db_connection(engine)
    assert ok is True
    assert err is None


def test_schema_pruning_relevance():
    engine = ensure_demo_database()
    schema_str, selected = prune_schema_for_question(
        engine,
        question="Which customer has the highest spend?",
        plan=["Join customers and orders", "Sum payment amounts"],
        max_tables=4,
    )
    assert len(selected) > 0
    assert "customers" in selected or "orders" in selected


def test_cartesian_join_detection():
    # Query with multiple comma-separated tables and no WHERE
    bad_sql = "SELECT * FROM orders, customers LIMIT 10"
    warnings = check_cartesian_joins(bad_sql, dialect="sqlite")
    assert any("Cartesian" in w for w in warnings)


def test_audit_query_performance_explain():
    engine = ensure_demo_database()
    safe_sql = "SELECT id, status FROM orders LIMIT 5"
    audit = audit_query_performance(safe_sql, engine, dialect="sqlite")
    assert "explain_plan" in audit
    assert len(audit["explain_plan"]) > 0


def test_plotly_figure_builder():
    df = pd.DataFrame({
        "category": ["Electronics", "Apparel", "Books"],
        "revenue": [15000.50, 8200.00, 4300.20],
    })
    fig = _build_plotly_figure(df, "bar", "category", "revenue", "Revenue by Category")
    assert fig is not None
    spec = fig.to_dict()
    assert "data" in spec
    assert "layout" in spec


def test_fastapi_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cte_queries_pass_schema_validation():
    engine = ensure_demo_database()

    # Query with order_revenue CTE
    q1 = """
    WITH order_revenue AS (
        SELECT customer_id, SUM(quantity * unit_price) AS total_spent
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        GROUP BY customer_id
    )
    SELECT c.name, r.total_spent
    FROM customers c
    JOIN order_revenue r ON c.id = r.customer_id
    ORDER BY total_spent DESC
    LIMIT 5;
    """
    v1 = validate_sql(q1, engine=engine, dialect="sqlite")
    assert v1["valid"] is True
    assert not any("order_revenue" in e for e in v1["errors"])

    # Query with monthly CTE
    q2 = """
    WITH monthly AS (
        SELECT strftime('%Y-%m', created_at) AS month, COUNT(*) AS total_orders
        FROM orders
        GROUP BY month
    )
    SELECT month, total_orders FROM monthly LIMIT 10;
    """
    v2 = validate_sql(q2, engine=engine, dialect="sqlite")
    assert v2["valid"] is True
    assert not any("monthly" in e for e in v2["errors"])
