from sqlalchemy import create_engine, event, text, URL
from sqlalchemy.pool import QueuePool
from sqlalchemy.engine import Engine
from app.config import settings
from typing import Optional, Tuple


_engine: Optional[Engine] = None


def build_engine(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    timeout: int = settings.query_timeout,
) -> Engine:
    db_url = URL.create(
        drivername="mysql+pymysql",
        username=user,
        password=password,
        host=host,
        port=port,
        database=database,
        query={"charset": "utf8mb4"},
    )
    engine = create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 10,
            "read_timeout": timeout,
            "write_timeout": timeout,
        },
    )

    @event.listens_for(engine, "connect")
    def set_readonly(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("SET SESSION TRANSACTION READ ONLY")
        cursor.close()

    return engine


def get_engine(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
) -> Engine:
    global _engine
    h = host or settings.mysql_host
    p = port or settings.mysql_port
    u = user or settings.mysql_user
    pw = password or settings.mysql_password
    db = database or settings.mysql_database

    if _engine is None:
        _engine = build_engine(h, p, u, pw, db)
    return _engine


def reset_engine() -> None:
    global _engine
    if _engine:
        _engine.dispose()
    _engine = None


def test_connection(engine: Engine) -> Tuple[bool, Optional[str]]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        return False, str(e)
