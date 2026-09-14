from typing import Optional
from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.agents.planner import run_planner
from app.agents.sql_agent import run_sql_agent
from app.agents.analysis_agent import run_analysis_agent
from app.agents.visualization_agent import run_visualization_agent
from app.db.connection import build_engine
from app.tools.schema import get_database_schema
from app.config import settings


def schema_node(state: AgentState) -> dict:
    db = state["db_config"]
    engine = build_engine(
        host=db["host"],
        port=db["port"],
        user=db["user"],
        password=db["password"],
        database=db["database"],
    )
    schema = get_database_schema(engine)
    return {"schema_context": schema}


def should_retry(state: AgentState) -> str:
    if state.get("query_result") is not None:
        import pandas as pd
        df = state["query_result"]
        if isinstance(df, pd.DataFrame) and not df.empty:
            return "analyze"
    if state["iteration_count"] >= settings.max_sql_retries:
        return "analyze"
    if state.get("execution_error") or state.get("validation_errors"):
        return "sql_agent"
    return "analyze"


def build_workflow() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("planner", run_planner)
    graph.add_node("schema_explorer", schema_node)
    graph.add_node("sql_agent", run_sql_agent)
    graph.add_node("analysis_agent", run_analysis_agent)
    graph.add_node("visualization_agent", run_visualization_agent)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "schema_explorer")
    graph.add_edge("schema_explorer", "sql_agent")

    graph.add_conditional_edges(
        "sql_agent",
        should_retry,
        {
            "sql_agent": "sql_agent",
            "analyze": "analysis_agent",
        },
    )

    graph.add_edge("analysis_agent", "visualization_agent")
    graph.add_edge("visualization_agent", END)

    return graph.compile()


_compiled_workflow = None


def get_workflow():
    global _compiled_workflow
    if _compiled_workflow is None:
        _compiled_workflow = build_workflow()
    return _compiled_workflow


def run_workflow(
    question: str,
    db_config: dict,
    groq_api_key: str,
    run_id: str,
    groq_model: Optional[str] = None,
) -> AgentState:
    workflow = get_workflow()

    initial_state: AgentState = {
        "question": question,
        "intent": None,
        "plan": [],
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
        "run_id": run_id,
        "db_config": db_config,
        "groq_api_key": groq_api_key,
        "groq_model": groq_model or settings.groq_model,
    }

    result = workflow.invoke(initial_state)
    return result
