"""Actual Chroma-backed retrieval; no context is fabricated when unavailable."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _cloud_configured() -> bool:
    return all(os.environ.get(name) for name in ("CHROMA_API_KEY", "CHROMA_TENANT", "CHROMA_DATABASE"))


def _local_path() -> str | None:
    if os.environ.get("CHROMA_PATH"):
        return os.environ["CHROMA_PATH"]
    if os.environ.get("VERCEL"):
        return None
    return str(ROOT / ".chroma")


def chroma_status() -> dict:
    try:
        import chromadb  # noqa: F401
    except ImportError:
        return {"configured": False, "message": "Install chromadb to enable retrieval."}
    if _cloud_configured():
        return {"configured": True, "message": "Chroma Cloud is configured."}
    if os.environ.get("CHROMA_URL"):
        return {"configured": True, "message": "Remote Chroma is configured."}
    if _local_path():
        return {"configured": True, "message": "Local Chroma is configured."}
    return {"configured": False, "message": "Set Chroma Cloud credentials or CHROMA_URL for remote Chroma."}


def _client():
    import chromadb
    if _cloud_configured():
        return chromadb.CloudClient(api_key=os.environ["CHROMA_API_KEY"], tenant=os.environ["CHROMA_TENANT"],
                                    database=os.environ["CHROMA_DATABASE"])
    remote_url = os.environ.get("CHROMA_URL")
    if remote_url:
        from urllib.parse import urlparse
        parsed = urlparse(remote_url)
        headers = {"x-chroma-token": os.environ["CHROMA_API_KEY"]} if os.environ.get("CHROMA_API_KEY") else None
        return chromadb.HttpClient(host=parsed.hostname or "localhost", port=parsed.port or (443 if parsed.scheme == "https" else 8000),
                                   ssl=parsed.scheme == "https", headers=headers,
                                   tenant=os.environ.get("CHROMA_TENANT", "default_tenant"),
                                   database=os.environ.get("CHROMA_DATABASE", "default_database"))
    path = _local_path()
    if not path:
        raise RuntimeError(chroma_status()["message"])
    return chromadb.PersistentClient(path=path)


def _collection(name: str):
    return _client().get_or_create_collection(name)


def retrieve(name: str, question: str, limit: int) -> list[dict]:
    if not chroma_status()["configured"]:
        return []
    collection = _collection(name)
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[question], n_results=min(max(1, min(limit, 10)), collection.count()), include=["documents", "metadatas", "distances"])
    return [{"document": document, "metadata": metadata or {}, "distance": round(distance, 3)}
            for document, metadata, distance in zip(results["documents"][0], results["metadatas"][0], results["distances"][0])]


def seed_collections(schema_docs: list[dict] | None = None) -> dict:
    """Seed glossary/examples and optional live database schema into Chroma."""
    client = _client()
    glossary = json.loads((ROOT / "data" / "business-glossary.json").read_text())
    examples = json.loads((ROOT / "data" / "few-shot-examples.json").read_text())
    sources = {
        "business_glossary": [{"id": f"glossary:{item['term']}", "document": f"{item['term']}: {item['definition']}", "metadata": {"term": item["term"]}} for item in glossary],
        "sql_examples": [{"id": f"example:{index}", "document": f"Question: {item['question']}\nSQL:\n{item['sql']}", "metadata": {"question": item["question"], "difficulty": item["difficulty"]}} for index, item in enumerate(examples)],
        "schema_docs": schema_docs or [],
    }
    counts = {}
    for name, docs in sources.items():
        collection = client.get_or_create_collection(name)
        if docs:
            collection.upsert(ids=[doc["id"] for doc in docs], documents=[doc["document"] for doc in docs], metadatas=[doc["metadata"] for doc in docs])
        counts[name] = len(docs)
    return counts
