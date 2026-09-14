import time
import uuid
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine
from app.config import settings


class QueryResult:
    def __init__(self, df: pd.DataFrame, execution_time_ms: float, rows_returned: int, query_id: str):
        self.df = df
        self.execution_time_ms = execution_time_ms
        self.rows_returned = rows_returned
        self.query_id = query_id

    def to_dict(self) -> dict:
        return {
            "execution_time_ms": round(self.execution_time_ms, 2),
            "rows_returned": self.rows_returned,
            "query_id": self.query_id,
        }


def execute_query(sql: str, engine: Engine, max_rows: int = settings.max_rows) -> QueryResult:
    query_id = str(uuid.uuid4())[:8]
    start = time.monotonic()

    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.fetchmany(max_rows)
        columns = list(result.keys())

    elapsed = (time.monotonic() - start) * 1000
    df = pd.DataFrame(rows, columns=columns)

    return QueryResult(
        df=df,
        execution_time_ms=elapsed,
        rows_returned=len(df),
        query_id=query_id,
    )
