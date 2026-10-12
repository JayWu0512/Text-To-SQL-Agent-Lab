"""Vercel handler for the static lab and secure request-scoped APIs."""

from __future__ import annotations

import json
import hmac
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from lib.database import execute_read_only, make_engine, schema_documents
from lib.llm import list_models, test_connection
from lib.retrieval import chroma_status, seed_collections
from lib.benchmarks import answer_key_for
from lib.service import run_pipeline

ROOT = Path(__file__).resolve().parent.parent


def request_path(raw_path: str) -> str:
    parsed = urlparse(raw_path)
    route = parse_qs(parsed.query).get("route", [""])[0]
    return f"/api/{route}" if route else parsed.path


def respond(handler, status, payload):
    data = json.dumps(payload, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def authorize_chroma_seed(token: str) -> None:
    expected = os.environ.get("CHROMA_SEED_TOKEN", "")
    if not expected:
        raise ValueError("Set CHROMA_SEED_TOKEN before indexing Chroma Cloud.")
    if not hmac.compare_digest(token, expected):
        raise ValueError("Invalid Chroma indexing token.")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = request_path(self.path)
        if path == "/api/health":
            return respond(self, HTTPStatus.OK, {"mode": "vercel", "connected": bool(os.environ.get("SUPABASE_CONNECTION_URL")), "chroma": chroma_status()})
        file = ROOT / "index.html" if path in {"/", "/text-to-sql", "/index.html"} else (ROOT / path.lstrip("/"))
        if file.is_file() and ROOT in file.resolve().parents:
            data = file.read_bytes(); content_type = mimetypes.guess_type(str(file))[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        respond(self, HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 100_000:
                raise ValueError("Request body is missing or too large.")
            payload, path = json.loads(self.rfile.read(size).decode("utf-8")), request_path(self.path)
            if path == "/api/test-llm":
                return respond(self, HTTPStatus.OK, test_connection(str(payload.get("api_key", "")), str(payload.get("model", "gpt-4.1-mini")), str(payload.get("provider", "openai"))))
            if path == "/api/models":
                return respond(self, HTTPStatus.OK, list_models(str(payload.get("api_key", "")), str(payload.get("provider", "openai"))))
            if path == "/api/benchmark-answer":
                answer_key = answer_key_for(str(payload.get("question", "")))
                if answer_key is None:
                    raise ValueError("No answer key is available for this question.")
                return respond(self, HTTPStatus.OK, answer_key)
            if path == "/api/seed-chroma":
                authorize_chroma_seed(str(payload.get("token", "")))
            engine = make_engine(serverless=True) if path in {"/api/query", "/api/text-to-sql", "/api/seed-chroma"} else None
            try:
                if path == "/api/query": return respond(self, HTTPStatus.OK, execute_read_only(engine, str(payload.get("sql", ""))))
                if path == "/api/text-to-sql": return respond(self, HTTPStatus.OK, run_pipeline(payload, engine))
                if path == "/api/seed-chroma": return respond(self, HTTPStatus.OK, {"collections": seed_collections(schema_documents(engine))})
            finally:
                if engine is not None: engine.dispose()
            respond(self, HTTPStatus.NOT_FOUND, {"error": "Not found."})
        except (ValueError, json.JSONDecodeError) as error:
            respond(self, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception:
            respond(self, HTTPStatus.BAD_GATEWAY, {"error": "The request failed. Check configuration and try again."})

    def log_message(self, _format, *_args):
        return
