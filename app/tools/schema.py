from sqlalchemy import inspect, Engine
from functools import lru_cache
from typing import Optional


import re
from typing import Optional, Tuple


def get_database_schema(engine: Engine, tables: Optional[list[str]] = None) -> str:
    return _build_schema_string(engine, tables=tables)


def _build_schema_string(engine: Engine, tables: Optional[list[str]] = None) -> str:
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()
    target_tables = [t for t in all_tables if t in tables] if tables else all_tables
    parts = []

    for table in target_tables:
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


def prune_schema_for_question(
    engine: Engine,
    question: str,
    plan: Optional[list[str]] = None,
    max_tables: int = 6,
) -> Tuple[str, list[str]]:
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()

    if len(all_tables) <= max_tables:
        return _build_schema_string(engine, all_tables), all_tables

    query_text = (question + " " + " ".join(plan or [])).lower()
    tokens = set(re.findall(r"\b[a-zA-Z0-9_]{2,}\b", query_text))

    SYNONYM_MAP = {
        "revenue": ["price", "amount", "unit_price", "orders", "order_items", "payments"],
        "sales": ["orders", "order_items", "payments", "amount", "quantity", "price"],
        "cost": ["price", "unit_price", "amount"],
        "user": ["customers", "customer", "customer_id"],
        "buyer": ["customers", "customer", "customer_id"],
        "client": ["customers", "customer", "customer_id"],
        "product": ["products", "product_id", "categories", "category"],
        "item": ["products", "order_items"],
        "purchase": ["orders", "payments"],
        "spend": ["payments", "amount", "orders"],
        "trend": ["created_at", "updated_at", "date"],
        "discount": ["discount_amount"],
    }
    expanded_tokens = set(tokens)
    for tok in tokens:
        if tok in SYNONYM_MAP:
            expanded_tokens.update(SYNONYM_MAP[tok])

    table_scores: dict[str, float] = {}
    fks_by_table: dict[str, list[str]] = {}

    for tbl in all_tables:
        score = 0.0
        tbl_lower = tbl.lower()
        if tbl_lower in expanded_tokens:
            score += 15.0
        elif any(tok in tbl_lower or tbl_lower in tok for tok in expanded_tokens):
            score += 8.0

        cols = inspector.get_columns(tbl)
        for col in cols:
            c_name = col["name"].lower()
            if c_name in expanded_tokens:
                score += 5.0
            elif any(tok in c_name for tok in expanded_tokens):
                score += 2.0

        fks = inspector.get_foreign_keys(tbl)
        referred = [fk["referred_table"] for fk in fks if fk.get("referred_table")]
        fks_by_table[tbl] = referred

        table_scores[tbl] = score

    # Boost bridging tables through foreign key relationships
    for tbl, refs in fks_by_table.items():
        if table_scores.get(tbl, 0) > 5:
            for ref in refs:
                if ref in table_scores:
                    table_scores[ref] += 4.0

    sorted_tables = sorted(all_tables, key=lambda t: table_scores.get(t, 0), reverse=True)
    selected = sorted_tables[:max_tables]

    # Ensure selected tables maintain valid join foreign keys if missing
    for tbl in list(selected):
        for ref in fks_by_table.get(tbl, []):
            if ref in all_tables and ref not in selected and len(selected) < max_tables + 2:
                selected.append(ref)

    schema_str = _build_schema_string(engine, tables=selected)
    return schema_str, selected


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
