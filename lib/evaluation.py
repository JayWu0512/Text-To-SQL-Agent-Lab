"""Execution-result evaluator. SQL strings are deliberately never compared."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation


def _value(value, tolerance: float):
    if value is None:
        return ("null", None)
    try:
        numeric = Decimal(str(value))
        return ("number", round(float(numeric) / tolerance) if tolerance else float(numeric))
    except (InvalidOperation, ValueError):
        return ("text", str(value).strip())


def _rows(result: dict, tolerance: float):
    return [tuple(_value(value, tolerance) for value in row) for row in result.get("rows", [])]


def evaluate_results(actual: dict, expected: dict, order_sensitive: bool = False, tolerance: float = 1e-6) -> dict:
    actual_columns, expected_columns = actual.get("columns", []), expected.get("columns", [])
    if len(actual_columns) != len(expected_columns):
        return {"status": "FAIL", "accuracy": 0, "reason": "Output column counts differ.", "overlap_rows": 0,
                "missing_rows": len(expected.get("rows", [])), "unexpected_rows": len(actual.get("rows", []))}
    actual_rows, expected_rows = _rows(actual, tolerance), _rows(expected, tolerance)
    if order_sensitive:
        equal = actual_rows == expected_rows
        if not equal and Counter(actual_rows) == Counter(expected_rows):
            return {"status": "FAIL", "accuracy": 0, "reason": "Rows are correct but their required ordering differs.",
                    "overlap_rows": len(actual_rows), "missing_rows": 0, "unexpected_rows": 0}
    else:
        equal = Counter(actual_rows) == Counter(expected_rows)
    if equal:
        reason = "Execution results are equivalent." if actual_columns == expected_columns else "Execution results are equivalent; column aliases differ."
        return {"status": "PASS", "accuracy": 100, "reason": reason,
                "overlap_rows": len(actual_rows), "missing_rows": 0, "unexpected_rows": 0}
    actual_counts, expected_counts = Counter(actual_rows), Counter(expected_rows)
    overlap = sum((actual_counts & expected_counts).values())
    denominator = max(len(actual_rows), len(expected_rows), 1)
    accuracy = round(100 * overlap / denominator, 1)
    status = "NEAR MATCH" if accuracy >= 70 else "FAIL"
    return {"status": status, "accuracy": accuracy, "reason": "Rows differ from the benchmark result.",
            "overlap_rows": overlap, "missing_rows": sum((expected_counts - actual_counts).values()),
            "unexpected_rows": sum((actual_counts - expected_counts).values())}
