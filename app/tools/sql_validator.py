import re
import sqlglot
from typing import Optional
from app.tools.schema import get_schema_as_dict
from sqlalchemy.engine import Engine


DESTRUCTIVE_KEYWORDS = {
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
    "TRUNCATE", "CREATE", "GRANT", "REVOKE", "REPLACE",
    "MERGE", "LOAD", "CALL", "EXEC", "EXECUTE",
}


def validate_sql(sql: str, engine: Optional[Engine] = None) -> dict:
    errors = []

    upper_sql = sql.upper()
    for keyword in DESTRUCTIVE_KEYWORDS:
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, upper_sql):
            errors.append(f"Destructive keyword '{keyword}' is not allowed.")

    try:
        parsed = sqlglot.parse_one(sql, dialect="mysql")
    except Exception as e:
        errors.append(f"SQL parse error: {str(e)}")
        return {"valid": False, "errors": errors}

    if engine is not None and parsed is not None:
        schema = get_schema_as_dict(engine)
        schema_errors = _validate_against_schema(sql, schema)
        errors.extend(schema_errors)

    if not re.search(r'\bLIMIT\b', upper_sql):
        errors.append("Warning: Query has no LIMIT clause. Large result sets may be slow.")

    return {"valid": len(errors) == 0, "errors": errors}


def _validate_against_schema(sql: str, schema: dict) -> list[str]:
    errors = []
    try:
        parsed = sqlglot.parse_one(sql, dialect="mysql")
        if parsed is None:
            return errors

        table_refs = set()
        for node in parsed.walk():
            if isinstance(node, sqlglot.exp.Table):
                table_name = node.name.lower()
                if table_name:
                    table_refs.add(table_name)

        known_tables = {t.lower() for t in schema.keys()}
        for tbl in table_refs:
            if tbl and tbl not in known_tables:
                errors.append(f"Table '{tbl}' does not exist in the database.")

    except Exception:
        pass

    return errors


def is_safe_sql(sql: str) -> bool:
    result = validate_sql(sql)
    destructive_errors = [e for e in result["errors"] if "Destructive keyword" in e]
    return len(destructive_errors) == 0
