import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from app.graph.state import AgentState
from app.db.connection import build_engine
from app.tools.schema import get_database_schema
from app.tools.sql_validator import validate_sql
from app.tools.sql_executor import safe_execute, ExecutionError
from app.config import settings


class SQLOutput(BaseModel):
    sql: str
    purpose: str
    assumptions: list[str]


SYSTEM_PROMPT = """You are a MySQL SQL generation expert.

Given a business question, an analytical plan, and a database schema, generate a single MySQL-compatible SQL query.

Rules:
- Never invent tables or columns. Only use what exists in the schema.
- Never use SELECT *. Always name columns explicitly.
- Use appropriate JOINs and aggregations.
- Use window functions when comparing across groups or time periods.
- Always include a LIMIT clause.
- Never generate destructive SQL (DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE).
- Prefer readable aliases.

Return a JSON object with:
- "sql": the complete MySQL SQL query
- "purpose": a one-sentence description of what this query answers
- "assumptions": list of assumptions made (empty list if none)

Return valid JSON only."""


def _call_llm(state: AgentState, error_context: str = "") -> SQLOutput:
    model_name = state.get("groq_model") or settings.groq_model
    llm = ChatGroq(api_key=state["groq_api_key"], model=model_name)

    correction_note = ""
    if error_context:
        correction_note = f"\n\nPrevious SQL failed with error:\n{error_context}\n\nGenerate a corrected query."

    user_message = f"""Question: {state['question']}

Analytical Plan:
{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(state['plan']))}

Database Schema:
{state['schema_context']}

Previous attempts: {state['iteration_count']}
{correction_note}

Return valid JSON only."""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
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
    engine = build_engine(
        host=db["host"],
        port=db["port"],
        user=db["user"],
        password=db["password"],
        database=db["database"],
    )

    error_context = state.get("execution_error") or ""
    if state.get("validation_errors"):
        error_context = "; ".join(state["validation_errors"])

    output = _call_llm(state, error_context)
    validation = validate_sql(output.sql, engine)

    if not validation["valid"]:
        destructive_errors = [e for e in validation["errors"] if "Destructive keyword" in e]
        if destructive_errors:
            return {
                "generated_sql": output.sql,
                "sql_purpose": output.purpose,
                "sql_assumptions": output.assumptions,
                "validation_errors": validation["errors"],
                "execution_error": "SQL blocked: destructive operation detected",
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
            "query_result": None,
            "execution_metadata": None,
            "execution_error": str(e),
            "iteration_count": state["iteration_count"] + 1,
        }
