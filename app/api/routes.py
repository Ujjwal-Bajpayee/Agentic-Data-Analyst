import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.graph.workflow import run_workflow
from app.observability import new_run_id, log_run, get_run
from app.config import settings


router = APIRouter()


class AnalyzeRequest(BaseModel):
    question: str
    groq_api_key: Optional[str] = None
    groq_model: Optional[str] = None
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


class AnalyzeResponse(BaseModel):
    run_id: str
    answer: Optional[str]
    generated_sql: Optional[str]
    visualization: Optional[str]
    execution: ExecutionInfo


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    if not request.question or len(request.question.strip()) < 3:
        raise HTTPException(status_code=400, detail="Question is too short.")
    if len(request.question) > 2000:
        raise HTTPException(status_code=400, detail="Question exceeds maximum length.")

    api_key = request.groq_api_key or settings.groq_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="Groq API key is required.")

    db_config = {
        "host": request.mysql_host or settings.mysql_host,
        "port": request.mysql_port or settings.mysql_port,
        "user": request.mysql_user or settings.mysql_user,
        "password": request.mysql_password or settings.mysql_password,
        "database": request.mysql_database or settings.mysql_database,
    }

    for key, value in db_config.items():
        if not value:
            raise HTTPException(status_code=400, detail=f"MySQL {key} is required.")

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

        df = result.get("query_result")
        viz = result.get("visualization_path")

        return AnalyzeResponse(
            run_id=run_id,
            answer=result.get("final_answer"),
            generated_sql=result.get("generated_sql"),
            visualization=viz,
            execution=ExecutionInfo(
                status=status,
                retries=result.get("iteration_count", 0),
                execution_time_ms=exec_meta.get("execution_time_ms"),
                rows_returned=exec_meta.get("rows_returned"),
            ),
        )

    except Exception as e:
        log_run(run_id, {"question": request.question, "status": "error", "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/runs/{run_id}")
def get_run_info(run_id: str):
    record = get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return record
