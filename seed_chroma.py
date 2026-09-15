"""Build the local Chroma index used by Text-to-SQL Agent Lab."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from lib.database import make_engine, schema_documents
from lib.retrieval import seed_collections


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Text-to-SQL Lab's local Chroma index.")
    parser.add_argument("--path", default=str(ROOT / ".chroma"), help="Local Chroma folder (default: ./.chroma)")
    parser.add_argument("--with-schema", action="store_true", help="Also index live schema metadata using SUPABASE_CONNECTION_URL and SUPABASE_DATABASE_PASSWORD.")
    args = parser.parse_args()

    # This utility intentionally targets a project-local Chroma folder, even if
    # a remote Chroma environment variable happens to be configured elsewhere.
    os.environ.pop("CHROMA_URL", None)
    os.environ["CHROMA_PATH"] = str(Path(args.path).resolve())
    engine = None
    try:
        schema_docs = None
        if args.with_schema:
            engine = make_engine()
            schema_docs = schema_documents(engine)
        counts = seed_collections(schema_docs)
    except Exception as error:
        print(f"Chroma index was not built: {error}")
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    print(f"Chroma index ready: {Path(os.environ['CHROMA_PATH'])}")
    print("Indexed sources:")
    print("  data/business-glossary.json  -> business_glossary")
    print("  data/few-shot-examples.json  -> sql_examples")
    if args.with_schema:
        print("  Supabase information_schema  -> schema_docs")
    else:
        print("  schema_docs                  -> not included (use --with-schema after setting Supabase environment variables)")
    print("Collection document counts: " + ", ".join(f"{name}={count}" for name, count in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
