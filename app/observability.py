import uuid
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from app.config import settings


def _get_log_path() -> Path:
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "runs.jsonl"


def new_run_id() -> str:
    return str(uuid.uuid4())


def log_run(run_id: str, payload: dict) -> None:
    record = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    with open(_get_log_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def get_run(run_id: str) -> dict | None:
    log_path = _get_log_path()
    if not log_path.exists():
        return None
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                if record.get("run_id") == run_id:
                    return record
            except json.JSONDecodeError:
                continue
    return None
