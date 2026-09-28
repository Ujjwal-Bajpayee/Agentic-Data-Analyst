from typing import Optional
from langgraph.graph import StateGraph, END
from app.graph.state import AgentState
from app.agents.planner import run_planner
from app.agents.sql_agent import run_sql_agent
from app.agents.analysis_agent import run_analysis_agent
from app.agents.visualization_agent import run_visualization_agent
from app.db.connection import build_engine
from app.tools.schema import get_database_schema, prune_schema_for_question
from app.config import settings


def schema_node(state: AgentState) -> dict:
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
    schema, selected_tables = prune_schema_for_question(
        engine=engine,
        question=state["question"],
        plan=state.get("plan"),
        max_tables=6,
    )
    return {"schema_context": schema, "selected_tables": selected_tables}


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


def build_initial_state(
    question: str,
    db_config: dict,
    groq_api_key: str,
    run_id: str,
    groq_model: Optional[str] = None,
) -> AgentState:
    return {
        "question": question,
        "intent": None,
        "plan": [],
        "schema_context": None,
        "selected_tables": [],
        "generated_sql": None,
        "sql_purpose": None,
        "sql_assumptions": [],
        "validation_errors": [],
        "query_warnings": [],
        "explain_plan": None,
        "query_result": None,
        "execution_metadata": None,
        "execution_error": None,
        "analysis": None,
        "visualization_path": None,
        "plotly_spec": None,
        "final_answer": None,
        "step_trace": [],
        "iteration_count": 0,
        "run_id": run_id,
        "db_config": db_config,
        "groq_api_key": groq_api_key,
        "groq_model": groq_model or settings.groq_model,
    }


def stream_workflow(
    question: str,
    db_config: dict,
    groq_api_key: str,
    run_id: str,
    groq_model: Optional[str] = None,
):
    workflow = get_workflow()
    current_state = build_initial_state(question, db_config, groq_api_key, run_id, groq_model)

    for event in workflow.stream(current_state):
        for node_name, node_update in event.items():
            if isinstance(node_update, dict):
                current_state.update(node_update)
            step_record = {
                "node": node_name,
                "update": {k: v for k, v in (node_update or {}).items() if k not in ("query_result", "schema_context")},
            }
            current_state.setdefault("step_trace", []).append(step_record)
            yield {
                "node": node_name,
                "node_update": node_update,
                "current_state": current_state,
            }


def run_workflow(
    question: str,
    db_config: dict,
    groq_api_key: str,
    run_id: str,
    groq_model: Optional[str] = None,
) -> AgentState:
    final_state = None
    for step in stream_workflow(question, db_config, groq_api_key, run_id, groq_model):
        final_state = step["current_state"]

    if final_state is None:
        workflow = get_workflow()
        initial_state = build_initial_state(question, db_config, groq_api_key, run_id, groq_model)
        final_state = workflow.invoke(initial_state)

    return final_state
