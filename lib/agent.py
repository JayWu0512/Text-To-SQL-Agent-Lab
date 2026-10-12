"""Composable agent orchestration for the guided stages and playground."""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import retrieval
from .llm import generate_json
from .sql_safety import validate_sql_safety

ROOT = Path(__file__).resolve().parents[1]
GLOSSARY = json.loads((ROOT / "data" / "business-glossary.json").read_text())
VALUE_HINTS = {
    "são paulo": "The stored value for São Paulo is customers.customer_state = 'SP'.",
    "sao paulo": "The stored value for São Paulo is customers.customer_state = 'SP'.",
}
SCOPE_TERMS = (
    "sql", "postgres", "database", "schema", "table", "column", "query", "select", "join", "group by",
    "order by", "window function", "row_number", "cte", "customer", "customers", "order", "orders",
    "purchase", "purchases", "revenue", "sales", "product", "products", "category", "categories", "item", "items", "freight",
    "delivery", "delivered", "state", "city", "seller", "payment", "olist", "customer_id", "customer_unique_id",
    "order_id", "order_items", "order_status", "order_purchase_timestamp", "freight_value", "customer_state",
)
SCOPE_MESSAGE = (
    "This lab only accepts SQL and data-analysis questions about the course dataset "
    "(customers, orders, products, sales, and delivery data)."
)

STAGES = {
    "baseline": {"business_glossary": False, "schema_retrieval": False, "few_shot": False, "planning": False, "validation": False, "self_correction": False},
    "domain": {"business_glossary": True, "schema_retrieval": False, "few_shot": False, "planning": False, "validation": False, "self_correction": False},
    "rag": {"business_glossary": True, "schema_retrieval": True, "few_shot": False, "planning": False, "validation": False, "self_correction": False},
    "few-shot": {"business_glossary": True, "schema_retrieval": True, "few_shot": True, "planning": False, "validation": False, "self_correction": False},
    "planning": {"business_glossary": True, "schema_retrieval": True, "few_shot": True, "planning": True, "validation": False, "self_correction": False},
    "validation": {"business_glossary": True, "schema_retrieval": True, "few_shot": True, "planning": True, "validation": True, "self_correction": True},
}


def _ambiguous(question: str) -> str | None:
    if "best customer" in question.lower() or "best customers" in question.lower():
        return "How should “best customer” be defined: total revenue, number of purchases, average order value, or another metric?"
    return None


def _out_of_scope(question: str) -> bool:
    lowered = question.lower()
    return not any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in SCOPE_TERMS)


def _context(question: str, options: dict, top_k: int) -> dict:
    context = {"schema": [], "definitions": [], "examples": [], "values": []}
    if options.get("business_glossary"):
        context["definitions"] = [{"document": f"{item['term']}: {item['definition']}", "metadata": {"term": item["term"]}} for item in GLOSSARY]
    if options.get("schema_retrieval"):
        context["schema"] = retrieval.retrieve("schema_docs", question, top_k)
        context["definitions"] = retrieval.retrieve("business_glossary", question, top_k) or context["definitions"]
    if options.get("few_shot"):
        context["examples"] = retrieval.retrieve("sql_examples", question, top_k)
    if options.get("value_retrieval"):
        lowered = question.lower()
        context["values"] = [{"document": hint} for phrase, hint in VALUE_HINTS.items() if phrase in lowered]
    return context


def _prompt(question: str, context: dict, options: dict, repair_feedback: str = "") -> str:
    sections = ["Database dialect: PostgreSQL.", "Basic schema context: customers(customer_id, customer_unique_id, customer_city, customer_state); orders(order_id, customer_id, order_status, order_purchase_timestamp); order_items(order_id, order_item_id, product_id, price, freight_value).", "Return this JSON shape: {clarification_needed:boolean, clarification_question:string|null, tables:string[], assumptions:string[], plan:string[], sql:string, confidence:number}.", "A plan is a brief list of observable SQL steps, never private reasoning.", f"User question: {question}"]
    if context["schema"]:
        sections.append("Retrieved schema:\n" + "\n\n".join(item["document"] for item in context["schema"]))
    if context["definitions"]:
        sections.append("Business definitions:\n" + "\n".join(item["document"] for item in context["definitions"]))
    if context["examples"]:
        sections.append("Similar examples (adapt them; do not copy blindly):\n" + "\n\n".join(item["document"] for item in context["examples"]))
    if context["values"]:
        sections.append("Retrieved database values:\n" + "\n".join(item["document"] for item in context["values"]))
    if options.get("planning"):
        sections.append("Include a concise, student-visible query plan before generating SQL.")
    if repair_feedback:
        sections.append("The prior SQL was rejected or failed: " + repair_feedback + ". Return a corrected query using the supplied context.")
    sections.append("Generate exactly one safe read-only SELECT or WITH query. Do not use write operations.")
    sections.append("When a verified example exactly matches the course challenge, preserve its output grain, filters, ordering, aliases, and type casts unless the new question explicitly changes them.")
    return "\n\n".join(sections)


def run(question: str, api_key: str, model: str, options: dict, top_k: int = 4, repair_feedback: str = "", provider: str = "openai") -> dict:
    question = question.strip()
    if not question:
        raise ValueError("Enter a business question first.")
    if _out_of_scope(question):
        return {"out_of_scope": True, "scope_message": SCOPE_MESSAGE, "repair_history": []}
    clarification = _ambiguous(question)
    if clarification:
        return {"clarification_needed": True, "clarification_question": clarification, "context": _context(question, options, top_k), "repair_history": []}
    context = _context(question, options, top_k)
    response = generate_json(api_key, model, _prompt(question, context, options, repair_feedback), provider)
    response["context"] = context
    response["retrieval_state"] = retrieval.chroma_status()
    response["repair_history"] = []
    if response.get("sql") and options.get("validation"):
        response["validation"] = validate_sql_safety(response["sql"])
    return response
