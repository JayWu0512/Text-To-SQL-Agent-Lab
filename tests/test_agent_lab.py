import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.agent import _context, run
from lib.benchmarks import answer_key_for, load_benchmarks
from lib.evaluation import evaluate_results
from lib.llm import PROVIDERS, _resolve_api_key, _response_text, test_connection
from lib import retrieval
from lib.sql_safety import validate_sql_safety


class SqlSafetyTests(unittest.TestCase):
    def test_safe_select_is_accepted(self):
        self.assertTrue(validate_sql_safety("SELECT * FROM customers;")["safe"])

    def test_mutation_and_cte_mutation_are_rejected(self):
        self.assertFalse(validate_sql_safety("DELETE FROM customers")["safe"])
        self.assertFalse(validate_sql_safety("WITH changed AS (DELETE FROM customers RETURNING *) SELECT * FROM changed")["safe"])

    def test_multiple_statements_are_rejected(self):
        self.assertFalse(validate_sql_safety("SELECT 1; SELECT 2")["safe"])

    def test_parser_rejects_a_mutating_cte(self):
        self.assertFalse(validate_sql_safety("WITH changed AS (UPDATE customers SET customer_city = 'x' RETURNING *) SELECT * FROM changed")["safe"])


class EvaluationTests(unittest.TestCase):
    def test_equivalent_unordered_results_pass(self):
        expected = {"columns": ["state", "revenue"], "rows": [["SP", 10.0], ["RJ", 20.0]]}
        actual = {"columns": ["state", "revenue"], "rows": [["RJ", "20.0000001"], ["SP", 10]]}
        self.assertEqual(evaluate_results(actual, expected)["status"], "PASS")

    def test_order_is_respected_when_required(self):
        expected = {"columns": ["id"], "rows": [[1], [2]]}
        actual = {"columns": ["id"], "rows": [[2], [1]]}
        self.assertEqual(evaluate_results(actual, expected, order_sensitive=True)["status"], "FAIL")

    def test_partial_result_is_not_silently_correct(self):
        expected = {"columns": ["id"], "rows": [[1], [2], [3]]}
        actual = {"columns": ["id"], "rows": [[1], [2]]}
        evaluation = evaluate_results(actual, expected)
        self.assertEqual(evaluation["status"], "FAIL")
        self.assertEqual(evaluation["missing_rows"], 1)
        self.assertEqual(evaluation["unexpected_rows"], 0)

    def test_equivalent_values_pass_when_only_column_aliases_differ(self):
        expected = {"columns": ["revenue"], "rows": [[10.0]]}
        actual = {"columns": ["total_revenue"], "rows": [[10.0]]}
        evaluation = evaluate_results(actual, expected)
        self.assertEqual(evaluation["status"], "PASS")
        self.assertIn("aliases differ", evaluation["reason"])


class DataTests(unittest.TestCase):
    def test_serverless_chroma_cache_uses_tmp(self):
        with patch.dict(os.environ, {"VERCEL": "1", "HOME": "/read-only"}, clear=True):
            retrieval._configure_serverless_cache()
            self.assertEqual(os.environ["HOME"], "/tmp")
            self.assertEqual(os.environ["XDG_CACHE_HOME"], "/tmp/.cache")

    def test_chroma_cloud_client_uses_deployment_credentials(self):
        cloud = {"CHROMA_API_KEY": "key", "CHROMA_TENANT": "tenant", "CHROMA_DATABASE": "database"}
        with patch.dict(os.environ, cloud, clear=True), patch("chromadb.CloudClient") as client:
            retrieval._client()
        client.assert_called_once_with(api_key="key", tenant="tenant", database="database")

    def test_chroma_cloud_embeddings_require_openai_key(self):
        cloud = {"CHROMA_API_KEY": "key", "CHROMA_TENANT": "tenant", "CHROMA_DATABASE": "database"}
        with patch.dict(os.environ, cloud, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                retrieval._cloud_embedding_function()

    def test_benchmarks_load(self):
        self.assertGreaterEqual(len(load_benchmarks()), 3)

    def test_answer_key_is_available_only_for_a_benchmark_question(self):
        answer_key = answer_key_for("Find the third delivered purchase for each customer, ordered by customer ID.")
        self.assertIn("ground_truth_sql", answer_key)
        self.assertIsNone(answer_key_for("An unbenchmarked question"))

    def test_value_retrieval_uses_the_stored_state_value(self):
        context = _context("Show delivered sales in São Paulo (SP).", {"value_retrieval": True}, 4)
        self.assertIn("customer_state = 'SP'", context["values"][0]["document"])

    def test_ambiguity_stops_before_model_request(self):
        response = run("Who are our best customers?", "", "gpt-4.1-mini", {"business_glossary": True})
        self.assertTrue(response["clarification_needed"])
        self.assertIn("define", response["clarification_question"])

    def test_out_of_scope_question_stops_before_model_request(self):
        response = run("Write a poem about the ocean.", "", "gpt-4.1-mini", {"business_glossary": True})
        self.assertTrue(response["out_of_scope"])
        self.assertIn("SQL", response["scope_message"])

    def test_unrelated_words_do_not_accidentally_pass_scope_check(self):
        response = run("How do I style a border in CSS?", "", "gpt-4.1-mini", {"business_glossary": True})
        self.assertTrue(response["out_of_scope"])

    def test_seed_data_has_required_fields(self):
        root = Path(__file__).resolve().parents[1]
        examples = json.loads((root / "data" / "few-shot-examples.json").read_text())
        self.assertTrue(all({"question", "sql", "concepts", "tables", "difficulty"} <= set(item) for item in examples))


class LlmResponseTests(unittest.TestCase):
    def test_extracts_text_from_raw_responses_api_output(self):
        payload = {"output": [{"type": "message", "content": [
            {"type": "output_text", "text": '{"ok": true}'},
        ]}]}
        self.assertEqual(_response_text(payload), '{"ok": true}')

    def test_accepts_sdk_convenience_output_text_when_present(self):
        self.assertEqual(_response_text({"output_text": "ready"}), "ready")

    def test_duke_gateway_uses_its_openai_compatible_responses_endpoint(self):
        self.assertEqual(PROVIDERS["duke"]["responses_url"], "https://litellm.oit.duke.edu/v1/responses")
        self.assertEqual(PROVIDERS["duke"]["models_url"], "https://litellm.oit.duke.edu/v1/models")

    def test_duke_uses_the_deployment_key_when_no_browser_key_is_given(self):
        with patch.dict(os.environ, {"DUKE_API_KEY": "deployment-key"}, clear=True):
            self.assertEqual(_resolve_api_key("", "duke"), "deployment-key")

    def test_openai_uses_the_deployment_key_when_no_browser_key_is_given(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "deployment-key"}, clear=True):
            self.assertEqual(_resolve_api_key("", "openai"), "deployment-key")

    @patch("lib.llm._request")
    def test_connection_uses_a_simple_non_structured_request(self, request):
        test_connection("sk-test", "gpt-4.1-mini")
        self.assertFalse(request.call_args.kwargs["structured"])


if __name__ == "__main__":
    unittest.main()
