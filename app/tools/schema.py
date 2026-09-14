from sqlalchemy import inspect, Engine
from functools import lru_cache
from typing import Optional


def get_database_schema(engine: Engine) -> str:
    return _build_schema_string(engine)


def _build_schema_string(engine: Engine) -> str:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    parts = []

    for table in tables:
        columns = inspector.get_columns(table)
        pk = inspector.get_pk_constraint(table)
        fks = inspector.get_foreign_keys(table)
        indexes = inspector.get_indexes(table)

        col_lines = []
        for col in columns:
            nullable = "" if col["nullable"] else " NOT NULL"
            col_lines.append(f"  {col['name']} {str(col['type'])}{nullable}")

        pk_names = pk.get("constrained_columns", [])
        if pk_names:
            col_lines.append(f"  PRIMARY KEY ({', '.join(pk_names)})")

        for fk in fks:
            ref_table = fk["referred_table"]
            local_cols = ", ".join(fk["constrained_columns"])
            ref_cols = ", ".join(fk["referred_columns"])
            col_lines.append(f"  FOREIGN KEY ({local_cols}) REFERENCES {ref_table}({ref_cols})")

        for idx in indexes:
            if not idx.get("unique"):
                idx_cols = ", ".join(idx["column_names"])
                col_lines.append(f"  INDEX {idx['name']} ({idx_cols})")

        table_block = f"TABLE {table}:\n" + "\n".join(col_lines)
        parts.append(table_block)

    return "\n\n".join(parts)


def get_schema_as_dict(engine: Engine) -> dict:
    inspector = inspect(engine)
    schema = {}
    for table in inspector.get_table_names():
        columns = inspector.get_columns(table)
        schema[table] = {
            "columns": {col["name"]: str(col["type"]) for col in columns},
            "foreign_keys": inspector.get_foreign_keys(table),
        }
    return schema
