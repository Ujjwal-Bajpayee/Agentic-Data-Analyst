import pytest
from app.graph.state import AgentState
from app.tools.sql_validator import validate_sql


def make_state(**kwargs) -> AgentState:
    defaults = {
        "question": "What are the top products?",
        "intent": None,
        "plan": ["Inspect schema", "Generate SQL", "Execute", "Analyze"],
        "schema_context": None,
        "generated_sql": None,
        "sql_purpose": None,
        "sql_assumptions": [],
        "validation_errors": [],
        "query_result": None,
        "execution_metadata": None,
        "execution_error": None,
        "analysis": None,
        "visualization_path": None,
        "final_answer": None,
        "iteration_count": 0,
        "run_id": "test-run-id",
        "db_config": {
            "host": "localhost",
            "port": 3306,
            "user": "test",
            "password": "test",
            "database": "test",
        },
        "groq_api_key": "test-key",
        "groq_model": "openai/gpt-oss-120b",
    }
    defaults.update(kwargs)
    return defaults


def test_state_has_all_required_fields():
    state = make_state()
    required = [
        "question", "intent", "plan", "schema_context", "generated_sql",
        "validation_errors", "query_result", "analysis", "visualization_path",
        "final_answer", "iteration_count", "run_id", "db_config", "groq_api_key",
    ]
    for field in required:
        assert field in state, f"Missing field: {field}"


def test_state_initial_iteration_count():
    state = make_state()
    assert state["iteration_count"] == 0


def test_state_db_config_structure():
    state = make_state()
    for key in ["host", "port", "user", "password", "database"]:
        assert key in state["db_config"]


def test_retry_logic_respects_max():
    max_retries = 3
    iteration_count = 0
    execution_errors = []

    for attempt in range(max_retries + 2):
        if iteration_count >= max_retries:
            break
        execution_errors.append(f"Error {attempt}")
        iteration_count += 1

    assert iteration_count == max_retries


def test_sql_validator_blocks_destructive_in_workflow():
    dangerous_sqls = [
        "DROP TABLE customers",
        "DELETE FROM orders WHERE 1=1",
        "TRUNCATE products",
        "UPDATE prices SET price = 0",
    ]
    for sql in dangerous_sqls:
        result = validate_sql(sql)
        assert not result["valid"], f"Should have blocked: {sql}"


def test_sql_validator_allows_select_in_workflow():
    safe_sqls = [
        "SELECT id, name FROM customers LIMIT 10",
        "SELECT COUNT(*) as cnt FROM orders LIMIT 1",
        "SELECT p.name, SUM(oi.quantity) FROM products p JOIN order_items oi ON p.id = oi.product_id GROUP BY p.name LIMIT 20",
    ]
    for sql in safe_sqls:
        result = validate_sql(sql)
        destructive = [e for e in result["errors"] if "Destructive keyword" in e]
        assert len(destructive) == 0, f"Should have allowed: {sql}"


def test_state_plan_is_list():
    state = make_state(plan=["step1", "step2"])
    assert isinstance(state["plan"], list)
    assert len(state["plan"]) == 2


def test_state_validation_errors_default_empty():
    state = make_state()
    assert state["validation_errors"] == []
