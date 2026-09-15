"""Request-level service operations; keys are accepted but never stored."""

from __future__ import annotations

from .agent import run
from .benchmarks import benchmark_for
from .database import execute_read_only
from .evaluation import evaluate_results


def run_pipeline(payload: dict, engine=None) -> dict:
    options = payload.get("options", {})
    result = run(str(payload.get("question", "")), str(payload.get("api_key", "")),
                 str(payload.get("model", "gpt-4.1-mini")), options, int(payload.get("top_k", 4)))
    if result.get("clarification_needed") or not result.get("sql"):
        return result
    attempts = [{"attempt": 1, "sql": result["sql"], "validation": result.get("validation")}]
    should_execute = bool(options.get("execute_sql"))
    max_repairs = 2 if options.get("self_correction") else 0
    for repair_number in range(max_repairs + 1):
        validation = result.get("validation")
        if validation and not validation["safe"]:
            failure = validation["reason"]
        elif not should_execute:
            break
        elif engine is None:
            result["execution_error"] = "Connect to Supabase before executing generated SQL."
            break
        else:
            try:
                result["execution"] = execute_read_only(engine, result["sql"])
                break
            except Exception as error:
                failure = str(error)
        if repair_number >= max_repairs:
            result["execution_error"] = failure
            break
        revised = run(str(payload.get("question", "")), str(payload.get("api_key", "")),
                      str(payload.get("model", "gpt-4.1-mini")), options, int(payload.get("top_k", 4)), failure)
        result = revised
        attempts.append({"attempt": repair_number + 2, "sql": result.get("sql", ""), "feedback": failure,
                         "validation": result.get("validation")})
    result["repair_history"] = attempts
    benchmark = benchmark_for(str(payload.get("question", "")))
    if benchmark and result.get("execution") and engine is not None:
        try:
            expected = execute_read_only(engine, benchmark["ground_truth_sql"])
            result["evaluation"] = evaluate_results(result["execution"], expected, benchmark["order_sensitive"])
            result["evaluation"].update({"expected_rows": len(expected["rows"]), "generated_rows": len(result["execution"]["rows"])})
        except Exception:
            result["evaluation"] = {"status": "UNAVAILABLE", "reason": "The benchmark result could not be executed."}
    elif benchmark:
        result["evaluation"] = {"status": "UNAVAILABLE", "reason": "Connect a database to run this benchmark."}
    return result
