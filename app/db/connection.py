from sqlalchemy import create_engine, event, text, URL
from sqlalchemy.pool import QueuePool
from sqlalchemy.engine import Engine
from app.config import settings
from typing import Optional, Tuple


from pathlib import Path

_engine: Optional[Engine] = None


from sqlalchemy import inspect


def get_demo_db_path() -> Path:
    db_dir = Path(__file__).parent.parent.parent / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "demo_ecommerce.db"


def ensure_demo_database() -> Engine:
    engine = build_engine(dialect="sqlite")
    inspector = inspect(engine)
    if len(inspector.get_table_names()) == 0:
        from app.db.seed_demo import seed_database
        seed_database(engine)
    return engine


def build_engine(
    host: Optional[str] = "localhost",
    port: Optional[int] = 3306,
    user: Optional[str] = "root",
    password: Optional[str] = "",
    database: Optional[str] = "",
    dialect: Optional[str] = "mysql",
    timeout: int = settings.query_timeout,
) -> Engine:
    d = (dialect or "mysql").lower()

    if d in ("sqlite", "sqlite3") or (database and str(database).endswith(".db")) or host == "sqlite":
        db_path = database if (database and str(database).endswith(".db")) else str(get_demo_db_path())
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine

    elif d in ("postgres", "postgresql"):
        db_url = URL.create(
            drivername="postgresql+psycopg2",
            username=user,
            password=password,
            host=host,
            port=port or 5432,
            database=database,
        )
        return create_engine(db_url, poolclass=QueuePool, pool_size=5, pool_pre_ping=True)

    else:
        db_url = URL.create(
            drivername="mysql+pymysql",
            username=user,
            password=password,
            host=host,
            port=port or 3306,
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
            try:
                cursor.execute("SET SESSION TRANSACTION READ ONLY")
            except Exception:
                pass
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
