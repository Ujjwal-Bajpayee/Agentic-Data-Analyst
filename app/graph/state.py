from typing import TypedDict, Any, Optional


class AgentState(TypedDict):
    question: str
    intent: Optional[str]
    plan: list[str]
    schema_context: Optional[str]
    generated_sql: Optional[str]
    sql_purpose: Optional[str]
    sql_assumptions: list[str]
    validation_errors: list[str]
    query_result: Any
    execution_metadata: Optional[dict]
    execution_error: Optional[str]
    analysis: Optional[str]
    visualization_path: Optional[str]
    final_answer: Optional[str]
    iteration_count: int
    run_id: str
    db_config: dict
    groq_api_key: str
    groq_model: Optional[str]
