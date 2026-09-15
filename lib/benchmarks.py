from __future__ import annotations

import json
from pathlib import Path


def load_benchmarks() -> list[dict]:
    return json.loads((Path(__file__).resolve().parents[1] / "data" / "text-to-sql-benchmark.json").read_text())


def benchmark_for(question: str) -> dict | None:
    normalized = question.strip().lower()
    return next((item for item in load_benchmarks() if item["question"].lower() == normalized), None)


def answer_key_for(question: str) -> dict | None:
    """Return the evaluator-owned answer key only after an explicit student action."""
    benchmark = benchmark_for(question)
    if not benchmark:
        return None
    return {"id": benchmark["id"], "ground_truth_sql": benchmark["ground_truth_sql"]}
