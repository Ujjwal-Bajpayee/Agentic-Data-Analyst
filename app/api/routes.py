import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Any
from app.graph.workflow import run_workflow, stream_workflow
from app.observability import new_run_id, log_run, get_run
from app.db.connection import ensure_demo_database, get_demo_db_path
from app.config import settings


router = APIRouter()


class AnalyzeRequest(BaseModel):
    question: str
    groq_api_key: Optional[str] = None
    groq_model: Optional[str] = None
    dialect: Optional[str] = "mysql"
    use_demo_db: Optional[bool] = False
    mysql_host: Optional[str] = None
    mysql_port: Optional[int] = 3306
    mysql_user: Optional[str] = None
    mysql_password: Optional[str] = None
    mysql_database: Optional[str] = None


class ExecutionInfo(BaseModel):
    status: str
    retries: int
    execution_time_ms: Optional[float] = None
    rows_returned: Optional[int] = None
    selected_tables: list[str] = []
    query_warnings: list[str] = []
    explain_plan: Optional[str] = None


class AnalyzeResponse(BaseModel):
    run_id: str
    answer: Optional[str]
    generated_sql: Optional[str]
    visualization: Optional[str]
    visualization_spec: Optional[dict] = None
    execution: ExecutionInfo


def _resolve_db_config(request: AnalyzeRequest) -> dict:
    if request.use_demo_db or request.dialect == "sqlite":
        ensure_demo_database()
        return {
            "dialect": "sqlite",
            "host": "sqlite",
            "database": str(get_demo_db_path()),
        }

    db_config = {
        "dialect": request.dialect or "mysql",
        "host": request.mysql_host or settings.mysql_host,
        "port": request.mysql_port or settings.mysql_port,
        "user": request.mysql_user or settings.mysql_user,
        "password": request.mysql_password or settings.mysql_password,
        "database": request.mysql_database or settings.mysql_database,
    }

    if not db_config.get("database"):
        ensure_demo_database()
        return {
            "dialect": "sqlite",
            "host": "sqlite",
            "database": str(get_demo_db_path()),
        }

    return db_config


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    if not request.question or len(request.question.strip()) < 3:
        raise HTTPException(status_code=400, detail="Question is too short.")
    if len(request.question) > 2000:
        raise HTTPException(status_code=400, detail="Question exceeds maximum length.")

    api_key = request.groq_api_key or settings.groq_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="Groq API key is required.")

    db_config = _resolve_db_config(request)
    run_id = new_run_id()

    try:
        result = run_workflow(
            question=request.question,
            db_config=db_config,
            groq_api_key=api_key,
            run_id=run_id,
            groq_model=request.groq_model or settings.groq_model,
        )

        exec_meta = result.get("execution_metadata") or {}
        status = "success" if result.get("query_result") is not None else "failed"

        log_run(run_id, {
            "question": request.question,
            "generated_sql": result.get("generated_sql"),
            "status": status,
            "retries": result.get("iteration_count", 0),
            "execution_time_ms": exec_meta.get("execution_time_ms"),
        })

        return AnalyzeResponse(
            run_id=run_id,
            answer=result.get("final_answer"),
            generated_sql=result.get("generated_sql"),
            visualization=result.get("visualization_path"),
            visualization_spec=result.get("plotly_spec"),
            execution=ExecutionInfo(
                status=status,
                retries=result.get("iteration_count", 0),
                execution_time_ms=exec_meta.get("execution_time_ms"),
                rows_returned=exec_meta.get("rows_returned"),
                selected_tables=result.get("selected_tables", []),
                query_warnings=result.get("query_warnings", []),
                explain_plan=result.get("explain_plan"),
            ),
        )

    except Exception as e:
        log_run(run_id, {"question": request.question, "status": "error", "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze/stream")
def analyze_stream(request: AnalyzeRequest):
    if not request.question or len(request.question.strip()) < 3:
        raise HTTPException(status_code=400, detail="Question is too short.")

    api_key = request.groq_api_key or settings.groq_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="Groq API key is required.")

    db_config = _resolve_db_config(request)
    run_id = new_run_id()

    def event_generator():
        try:
            for step in stream_workflow(
                question=request.question,
                db_config=db_config,
                groq_api_key=api_key,
                run_id=run_id,
                groq_model=request.groq_model or settings.groq_model,
            ):
                payload = {
                    "node": step["node"],
                    "run_id": run_id,
                    "update": {
                        k: v for k, v in step.get("node_update", {}).items()
                        if k not in ("query_result", "schema_context")
                    },
                }
                yield f"data: {json.dumps(payload)}\n\n"
            yield f"data: {json.dumps({'event': 'completed', 'run_id': run_id})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/runs/{run_id}")
def get_run_info(run_id: str):
    record = get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return record
