"""Local server for Text-to-SQL Agent Lab; does not log keys or passwords."""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from lib.database import execute_read_only, make_engine, schema_documents
from lib.llm import list_models, test_connection
from lib.retrieval import chroma_status, seed_collections
from lib.benchmarks import answer_key_for
from lib.service import run_pipeline

HOST, PORT = "127.0.0.1", 8766
ROOT = Path(__file__).resolve().parent
engine = None


def load_local_env() -> None:
    """Load simple KEY=VALUE entries from the ignored local .env file."""
    env_file = ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text().splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key and not key.startswith("#"):
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


load_local_env()


def respond(handler, status, payload):
    body = json.dumps(payload, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def body(handler):
    size = int(handler.headers.get("Content-Length", "0"))
    if not 0 < size <= 100_000:
        raise ValueError("Request body is missing or too large.")
    return json.loads(handler.rfile.read(size).decode("utf-8"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in {"/", "/index.html", "/text-to-sql"}:
            self.path = "/index.html"
            return super().do_GET()
        if path == "/api/health":
            return respond(self, HTTPStatus.OK, {"connected": engine is not None, "chroma": chroma_status(), "mode": "local"})
        return super().do_GET()

    def do_POST(self):
        global engine
        try:
            payload = body(self)
            path = urlparse(self.path).path
            if path == "/api/connect":
                new_engine = make_engine(payload.get("connection_url"), payload.get("password"))
                execute_read_only(new_engine, "SELECT 1")
                if engine is not None:
                    engine.dispose()
                engine = new_engine
                try:
                    counts = seed_collections(schema_documents(engine))
                    message = "Connected to Supabase and indexed retrieval context: " + ", ".join(f"{name} {count}" for name, count in counts.items()) + "."
                except Exception:
                    message = "Connected to Supabase. Retrieval indexing was unavailable; the agent will use the base schema context."
                return respond(self, HTTPStatus.OK, {"message": message})
            if path == "/api/query":
                if engine is None:
                    raise ValueError("Connect to Supabase first.")
                return respond(self, HTTPStatus.OK, execute_read_only(engine, str(payload.get("sql", ""))))
            if path == "/api/test-llm":
                return respond(self, HTTPStatus.OK, test_connection(str(payload.get("api_key", "")), str(payload.get("model", "gpt-4.1-mini")), str(payload.get("provider", "openai"))))
            if path == "/api/models":
                return respond(self, HTTPStatus.OK, list_models(str(payload.get("api_key", "")), str(payload.get("provider", "openai"))))
            if path == "/api/text-to-sql":
                return respond(self, HTTPStatus.OK, run_pipeline(payload, engine))
            if path == "/api/benchmark-answer":
                answer_key = answer_key_for(str(payload.get("question", "")))
                if answer_key is None:
                    raise ValueError("No answer key is available for this question.")
                return respond(self, HTTPStatus.OK, answer_key)
            if path == "/api/seed-chroma":
                if engine is None:
                    raise ValueError("Connect to Supabase before indexing live schema metadata.")
                return respond(self, HTTPStatus.OK, {"collections": seed_collections(schema_documents(engine))})
            respond(self, HTTPStatus.NOT_FOUND, {"error": "Not found."})
        except (ValueError, json.JSONDecodeError) as error:
            respond(self, HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception:
            respond(self, HTTPStatus.BAD_GATEWAY, {"error": "The request failed. Check the connection and try again."})

    def log_message(self, _format, *_args):
        return


if __name__ == "__main__":
    print(f"Open http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
