import pytest
from app.tools.sql_validator import validate_sql, is_safe_sql


def test_rejects_drop():
    result = validate_sql("DROP TABLE users")
    assert not result["valid"]
    assert any("DROP" in e for e in result["errors"])


def test_rejects_delete():
    result = validate_sql("DELETE FROM users WHERE id = 1")
    assert not result["valid"]
    assert any("DELETE" in e for e in result["errors"])


def test_rejects_update():
    result = validate_sql("UPDATE users SET name = 'x' WHERE id = 1")
    assert not result["valid"]
    assert any("UPDATE" in e for e in result["errors"])


def test_rejects_insert():
    result = validate_sql("INSERT INTO users (name) VALUES ('x')")
    assert not result["valid"]
    assert any("INSERT" in e for e in result["errors"])


def test_rejects_truncate():
    result = validate_sql("TRUNCATE TABLE orders")
    assert not result["valid"]
    assert any("TRUNCATE" in e for e in result["errors"])


def test_rejects_create():
    result = validate_sql("CREATE TABLE new_table (id INT)")
    assert not result["valid"]
    assert any("CREATE" in e for e in result["errors"])


def test_allows_select():
    result = validate_sql("SELECT id, name FROM users LIMIT 10")
    destructive = [e for e in result["errors"] if "Destructive keyword" in e]
    assert len(destructive) == 0


def test_warns_missing_limit():
    result = validate_sql("SELECT id, name FROM users")
    limit_warnings = [e for e in result["errors"] if "LIMIT" in e]
    assert len(limit_warnings) > 0


def test_parse_error_returns_false():
    result = validate_sql("THIS IS NOT SQL @@@@")
    assert not result["valid"]


def test_is_safe_sql_returns_true_for_select():
    assert is_safe_sql("SELECT id FROM users LIMIT 5") is True


def test_is_safe_sql_returns_false_for_drop():
    assert is_safe_sql("DROP TABLE users") is False


def test_complex_select_is_safe():
    sql = """
    SELECT c.name, SUM(oi.quantity * oi.unit_price) AS revenue
    FROM customers c
    JOIN orders o ON c.id = o.customer_id
    JOIN order_items oi ON o.id = oi.order_id
    GROUP BY c.name
    ORDER BY revenue DESC
    LIMIT 10
    """
    assert is_safe_sql(sql) is True


def test_case_insensitive_drop():
    result = validate_sql("drop table users")
    assert not result["valid"]
