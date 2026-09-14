from app.db.queries import execute_query, QueryResult
from app.tools.sql_validator import validate_sql, is_safe_sql
from sqlalchemy.engine import Engine
from app.config import settings


class ExecutionError(Exception):
    pass


def safe_execute(sql: str, engine: Engine, max_rows: int = settings.max_rows) -> QueryResult:
    validation = validate_sql(sql, engine)
    destructive_errors = [e for e in validation["errors"] if "Destructive keyword" in e]
    if destructive_errors:
        raise ExecutionError(f"SQL blocked by safety validator: {destructive_errors}")

    try:
        result = execute_query(sql, engine, max_rows)
        return result
    except Exception as e:
        raise ExecutionError(str(e))
