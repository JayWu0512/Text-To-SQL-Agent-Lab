"""Read-only PostgreSQL connection and metadata helpers."""

from __future__ import annotations

import os
from time import perf_counter
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.pool import NullPool

from .sql_safety import validate_sql_safety

MAX_ROWS = 200


def make_engine(connection_url: str | None = None, password: str | None = None, serverless: bool = False) -> Engine:
    connection_url = connection_url or os.environ.get("SUPABASE_CONNECTION_URL", "")
    password = password or os.environ.get("SUPABASE_DATABASE_PASSWORD", "")
    if not connection_url or not password:
        raise ValueError("Connect to Supabase before executing SQL.")
    parsed = urlparse(connection_url.replace(":[YOUR-PASSWORD]@", ":placeholder@"))
    if parsed.scheme not in {"postgresql", "postgres"} or not parsed.username or not parsed.hostname:
        raise ValueError("Use a valid PostgreSQL Session pooler URL.")
    kwargs = {"connect_args": {"sslmode": "require", **({"prepare_threshold": None} if serverless else {})},
              "pool_pre_ping": not serverless}
    if serverless:
        kwargs["poolclass"] = NullPool
    return create_engine(URL.create("postgresql+psycopg", username=parsed.username, password=password,
                                    host=parsed.hostname, port=parsed.port or 5432,
                                    database=parsed.path.lstrip("/") or "postgres"), **kwargs)


def execute_read_only(engine: Engine, sql: str) -> dict:
    safety = validate_sql_safety(sql)
    if not safety["safe"]:
        raise ValueError(safety["reason"])
    started = perf_counter()
    with engine.connect() as connection:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '8s'"))
            result = connection.execute(text(safety["sql"]))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchmany(MAX_ROWS)]
    return {"columns": columns, "rows": rows, "truncated": len(rows) == MAX_ROWS,
            "execution_ms": round((perf_counter() - started) * 1000, 1)}


def schema_documents(engine: Engine) -> list[dict]:
    column_rows = execute_read_only(engine, """SELECT table_name, column_name, data_type
        FROM information_schema.columns WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position""")["rows"]
    fk_rows = execute_read_only(engine, """SELECT tc.table_name, kcu.column_name,
        ccu.table_name, ccu.column_name FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'""")["rows"]
    tables: dict[str, list[str]] = {}
    for table, column, data_type in column_rows:
        tables.setdefault(table, []).append(f"{column} ({data_type})")
    relationships: dict[str, list[str]] = {}
    for table, column, other_table, other_column in fk_rows:
        relationships.setdefault(table, []).append(f"{table}.{column} → {other_table}.{other_column}")
    return [{"id": f"schema:{table}", "document": f"Table: {table}\nColumns: " + ", ".join(columns) +
             ("\nRelationships: " + "; ".join(relationships[table]) if table in relationships else ""),
             "metadata": {"kind": "schema", "table": table}} for table, columns in tables.items()]
