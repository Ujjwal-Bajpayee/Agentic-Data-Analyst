import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from app.graph.state import AgentState
from app.db.connection import build_engine
from app.tools.schema import get_database_schema
from app.tools.sql_validator import validate_sql, audit_query_performance, get_dialect_name
from app.tools.sql_executor import safe_execute, ExecutionError
from app.config import settings


class SQLOutput(BaseModel):
    sql: str
    purpose: str
    assumptions: list[str]


def _get_system_prompt(dialect: str = "mysql") -> str:
    dialect_clean = dialect.upper()
    dialect_specific_guidelines = ""
    if dialect.lower() == "sqlite":
        dialect_specific_guidelines = """- Use SQLite syntax (e.g. strftime('%Y-%m', col) for date formatting, date('now', '-30 days')).
- SQLite does not have FULL OUTER JOIN, use LEFT JOIN or UNION."""
    elif dialect.lower() == "postgresql":
        dialect_specific_guidelines = """- Use PostgreSQL syntax (e.g. TO_CHAR(col, 'YYYY-MM'), CURRENT_DATE - INTERVAL '30 days')."""
    else:
        dialect_specific_guidelines = """- Use MySQL 8.0+ syntax (e.g. DATE_FORMAT(col, '%Y-%m'), NOW() - INTERVAL 30 DAY)."""

    return f"""You are a senior {dialect_clean} SQL generation specialist.

Given a business question, an analytical plan, and a database schema, generate a single, highly-optimized {dialect_clean}-compatible SQL query.

Rules:
- Never invent tables or columns. Strictly use what exists in the provided schema.
- Never use SELECT *. Explicitly list all required columns with meaningful aliases.
- Use appropriate JOINs and aggregations with correct ON clauses. Avoid unconstrained Cartesian joins.
- Use window functions (e.g. ROW_NUMBER(), RANK(), LAG()) when comparing across groups or time periods where supported.
- Always include a LIMIT clause unless performing a single-row aggregate.
- Never generate destructive SQL (DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE).
{dialect_specific_guidelines}

Return a JSON object with:
- "sql": the complete {dialect_clean} SQL query
- "purpose": a one-sentence description of what this query calculates
- "assumptions": list of assumptions made (empty list if none)

Return valid JSON only."""


def _call_llm(state: AgentState, error_context: str = "", dialect: str = "mysql") -> SQLOutput:
    model_name = state.get("groq_model") or settings.groq_model
    llm = ChatGroq(api_key=state["groq_api_key"], model=model_name)

    correction_note = ""
    if error_context:
        correction_note = f"\n\nPrevious SQL attempt failed or had issues:\n{error_context}\n\nPlease generate a corrected, performant query."

    user_message = f"""Question: {state['question']}

Analytical Plan:
{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(state['plan']))}

Database Schema (Pruned to Relevant Entities):
{state['schema_context']}

Previous attempts: {state['iteration_count']}
Target Dialect: {dialect}
{correction_note}

Return valid JSON only."""

    messages = [
        SystemMessage(content=_get_system_prompt(dialect)),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    content = response.content.strip()

    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1])

    try:
        parsed = json.loads(content)
        return SQLOutput(**parsed)
    except Exception:
        sql_start = content.find("SELECT")
        if sql_start == -1:
            sql_start = content.find("select")
        extracted = content[sql_start:] if sql_start != -1 else content
        return SQLOutput(sql=extracted, purpose="Extracted from response", assumptions=[])


def run_sql_agent(state: AgentState) -> dict:
    db = state["db_config"]
    dialect = db.get("dialect") or ("sqlite" if db.get("host") == "sqlite" or str(db.get("database", "")).endswith(".db") else "mysql")

    engine = build_engine(
        host=db.get("host", "localhost"),
        port=int(db.get("port", 3306)) if db.get("port") else 3306,
        user=db.get("user", "root"),
        password=db.get("password", ""),
        database=db.get("database", ""),
        dialect=dialect,
    )

    error_context = state.get("execution_error") or ""
    if state.get("validation_errors"):
        error_context = "; ".join(state["validation_errors"])

    output = _call_llm(state, error_context=error_context, dialect=dialect)
    validation = validate_sql(output.sql, engine, dialect=dialect)
    perf_audit = audit_query_performance(output.sql, engine, dialect=dialect)
    all_warnings = list(validation.get("warnings", [])) + list(perf_audit.get("warnings", []))

    if not validation["valid"]:
        destructive_errors = [e for e in validation["errors"] if "Destructive keyword" in e]
        blocking_msg = "SQL blocked: destructive operation detected" if destructive_errors else "; ".join(validation["errors"])
        return {
            "generated_sql": output.sql,
            "sql_purpose": output.purpose,
            "sql_assumptions": output.assumptions,
            "validation_errors": validation["errors"],
            "query_warnings": all_warnings,
            "explain_plan": perf_audit.get("explain_plan"),
            "execution_error": blocking_msg,
            "query_result": None,
            "execution_metadata": None,
            "iteration_count": state["iteration_count"] + 1,
        }

    try:
        result = safe_execute(output.sql, engine)
        return {
            "generated_sql": output.sql,
            "sql_purpose": output.purpose,
            "sql_assumptions": output.assumptions,
            "validation_errors": [],
            "query_warnings": all_warnings,
            "explain_plan": perf_audit.get("explain_plan"),
            "query_result": result.df,
            "execution_metadata": result.to_dict(),
            "execution_error": None,
            "iteration_count": state["iteration_count"] + 1,
        }
    except ExecutionError as e:
        return {
            "generated_sql": output.sql,
            "sql_purpose": output.purpose,
            "sql_assumptions": output.assumptions,
            "validation_errors": validation["errors"],
            "query_warnings": all_warnings,
            "explain_plan": perf_audit.get("explain_plan"),
            "query_result": None,
            "execution_metadata": None,
            "execution_error": str(e),
            "iteration_count": state["iteration_count"] + 1,
        }
