"""Conservative, read-only SQL policy shared by every execution path."""

from __future__ import annotations

import re

from sqlglot import exp, parse_one

FORBIDDEN = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|COPY|GRANT|REVOKE|TRUNCATE|VACUUM|CALL|DO|MERGE)\b", re.I)
STARTS_READ_ONLY = re.compile(r"^(SELECT|WITH|EXPLAIN)\b", re.I)


def validate_sql_safety(sql: str) -> dict:
    statement = sql.strip()
    if not statement:
        return {"safe": False, "reason": "Generate a SQL query first."}
    if statement.endswith(";"):
        statement = statement[:-1].strip()
    if ";" in statement:
        return {"safe": False, "reason": "Only one SQL statement may be executed."}
    if not STARTS_READ_ONLY.match(statement):
        return {"safe": False, "reason": "Only SELECT, WITH, and EXPLAIN queries are allowed."}
    try:
        tree = parse_one(statement, dialect="postgres")
    except Exception:
        return {"safe": False, "reason": "The SQL could not be parsed safely."}
    mutating_nodes = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create, exp.Merge, exp.Grant, exp.Revoke)
    if any(isinstance(node, mutating_nodes) for node in tree.walk()):
        return {"safe": False, "reason": "Write operations are disabled in this teaching runner."}
    match = FORBIDDEN.search(statement)
    if match:
        return {"safe": False, "reason": f"{match.group(1).upper()} is not allowed in this read-only lab."}
    # SELECT ... FOR UPDATE is a write lock even though it starts with SELECT.
    if re.search(r"\bFOR\s+(UPDATE|SHARE|NO\s+KEY\s+UPDATE|KEY\s+SHARE)\b", statement, re.I):
        return {"safe": False, "reason": "Locking SELECT clauses are not allowed."}
    return {"safe": True, "sql": statement}
