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


from sqlalchemy import text


def get_dialect_name(engine: Optional[Engine] = None, default: str = "mysql") -> str:
    if engine is not None:
        name = engine.dialect.name.lower()
        if name in ("sqlite", "postgresql", "mysql"):
            return name
    return default


def check_cartesian_joins(sql: str, dialect: str = "mysql") -> list[str]:
    warnings = []
    try:
        parsed = sqlglot.parse_one(sql, dialect=dialect)
        if not parsed:
            return warnings

        joins = list(parsed.find_all(sqlglot.exp.Join))
        for j in joins:
            # Check if join lacks ON / USING condition and isn't explicitly CROSS or NATURAL
            has_condition = bool(j.args.get("on") or j.args.get("using"))
            kind = str(j.kind or "").upper()
            if not has_condition and kind not in ("CROSS", "NATURAL"):
                table_name = getattr(j.this, "name", str(j.this))
                warnings.append(f"Unconstrained join on '{table_name}' without ON/USING condition (Cartesian product risk).")

        # Comma-separated tables in FROM without WHERE
        from_node = parsed.find(sqlglot.exp.From)
        if from_node and from_node.expressions and len(from_node.expressions) > 1:
            where_node = parsed.find(sqlglot.exp.Where)
            if not where_node:
                warnings.append("Comma-separated FROM tables with no WHERE filter clause (Cartesian product risk).")

    except Exception:
        pass
    return warnings


def audit_query_performance(sql: str, engine: Engine, dialect: str = "mysql") -> dict:
    warnings = check_cartesian_joins(sql, dialect)
    explain_output = ""

    try:
        with engine.connect() as conn:
            d = engine.dialect.name.lower()
            if d == "sqlite":
                result = conn.execute(text(f"EXPLAIN QUERY PLAN {sql}"))
                rows = result.fetchall()
                explain_lines = [f"{row[3]}" if len(row) > 3 else str(row) for row in rows]
                explain_output = "\n".join(explain_lines)
                if any("SCAN" in line and "orders" in line for line in explain_lines):
                    warnings.append("Full table scan on large table orders.")
            elif d == "mysql":
                result = conn.execute(text(f"EXPLAIN {sql}"))
                rows = result.fetchall()
                explain_output = str(rows)
            else:
                result = conn.execute(text(f"EXPLAIN {sql}"))
                explain_output = str(result.fetchall())
    except Exception as e:
        explain_output = f"EXPLAIN unavailable: {str(e)}"

    return {
        "explain_plan": explain_output,
        "warnings": warnings,
    }


def validate_sql(sql: str, engine: Optional[Engine] = None, dialect: Optional[str] = None) -> dict:
    errors = []
    warnings = []

    d = dialect or get_dialect_name(engine)
    upper_sql = sql.upper()

    for keyword in DESTRUCTIVE_KEYWORDS:
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, upper_sql):
            errors.append(f"Destructive keyword '{keyword}' is not allowed.")

    try:
        parsed = sqlglot.parse_one(sql, dialect=d)
    except Exception as e:
        errors.append(f"SQL parse error: {str(e)}")
        return {"valid": False, "errors": errors, "warnings": warnings}

    if engine is not None and parsed is not None:
        schema = get_schema_as_dict(engine)
        schema_errors = _validate_against_schema(sql, schema, dialect=d)
        errors.extend(schema_errors)

    # Performance and quality warnings
    cartesian_warnings = check_cartesian_joins(sql, dialect=d)
    warnings.extend(cartesian_warnings)

    if not re.search(r'\bLIMIT\b', upper_sql):
        warning_msg = "Warning: Query has no LIMIT clause. Large result sets may be slow."
        errors.append(warning_msg)
        warnings.append(warning_msg)

    blocking_errors = [e for e in errors if not e.startswith("Warning:")]

    return {
        "valid": len(blocking_errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def _validate_against_schema(sql: str, schema: dict, dialect: str = "mysql") -> list[str]:
    errors = []
    try:
        parsed = sqlglot.parse_one(sql, dialect=dialect)
        if parsed is None:
            return errors

        # Extract Common Table Expression (CTE) names (e.g., WITH order_revenue AS (...))
        cte_names = set()
        for cte in parsed.find_all(sqlglot.exp.CTE):
            alias = cte.alias_or_name or (cte.alias and getattr(cte.alias, "name", str(cte.alias)))
            if alias:
                cte_names.add(str(alias).lower())

        table_refs = set()
        for node in parsed.walk():
            if isinstance(node, sqlglot.exp.Table):
                table_name = node.name.lower()
                # Exclude CTE aliases from physical database table validation
                if table_name and table_name not in cte_names:
                    table_refs.add(table_name)

        known_tables = {t.lower() for t in schema.keys()}
        for tbl in table_refs:
            if tbl and tbl not in known_tables:
                errors.append(f"Table '{tbl}' does not exist in the database.")

    except Exception:
        pass

    return errors


def is_safe_sql(sql: str, dialect: str = "mysql") -> bool:
    result = validate_sql(sql, dialect=dialect)
    destructive_errors = [e for e in result["errors"] if "Destructive keyword" in e]
    return len(destructive_errors) == 0
