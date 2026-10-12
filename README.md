# Text-to-SQL Agent Lab

An interactive next chapter for SQL Practice Lab. It is a standalone project that preserves the original tutorial and teaches why a production Text-to-SQL system is a pipeline—not merely an LLM prompt.

## Run locally

1. Create and activate a Python virtual environment (Python 3.10+ recommended).
2. Install requirements: `pip install -r requirements.txt`.
3. Start the local server: `python3 text_to_sql_server.py` (or open `scripts/Open_Text_to_SQL_Agent_Lab.command` on macOS).
4. Open `http://127.0.0.1:8766`.

The original `../SQL-Practice-Lab` folder is intentionally untouched. Use its Supabase setup guide to create and load the four Olist tables: `customers`, `orders`, `order_items`, and `products`.

## Quick start: run a Full Agent challenge

1. Start the app with `scripts/Open_Text_to_SQL_Agent_Lab.command`.
2. Open `http://127.0.0.1:8766` — do not open `index.html` directly.
3. In **Connections**, choose OpenAI or Duke AI Gateway, test its API key, then connect Supabase.
4. Wait for the database status to say that retrieval context was indexed.
5. Open **Experiment Lab**, choose **Full Agent**, select a built-in challenge, and run it.

The built-in intermediate and advanced challenges state their required ordering explicitly. They are paired with verified retrieval patterns so that Full Agent can use the same business definitions, schema path, and output contract as the evaluator. Custom questions remain open-ended experiments and are not guaranteed to match a benchmark.

## Connections and key handling

In the **Connections** card, paste a Supabase Session pooler URL (port 5432) and enter its password separately. The local server holds this database connection only in process memory. Every query is run inside a read-only transaction with an eight-second timeout and a 200-row display cap.

Enter an OpenAI key in the same card and test it. The key is held in the page's memory only for the current session:

- it is never written to source, a database, localStorage, or sessionStorage;
- it is sent only to the server endpoint needed for that request;
- it is never returned by an endpoint or written to server logs;
- errors intentionally do not repeat a key.

For OpenAI, the default model is `gpt-4.1-mini`; change it only to a model available to your OpenAI account. For Duke AI Gateway, choose **Duke AI Gateway**, paste a newly generated key from the Duke AI Dashboard, and use `GPT 4.1` (or an exact model name shown in your Duke model catalog). The lab sends Duke keys only to `https://litellm.oit.duke.edu/v1/responses`.

## ChromaDB retrieval: what is indexed

The RAG stages use a persistent local Chroma database at `.chroma/` automatically. It contains compact documents, not a copy of the full Olist dataset.

| Collection | Source | What the model can retrieve |
| --- | --- | --- |
| `business_glossary` | `data/business-glossary.json` | Definitions such as what counts as revenue, a customer, and a valid purchase. |
| `sql_examples` | `data/few-shot-examples.json` | Verified Question → SQL patterns for aggregation, joins, time grouping, ranking, and window functions. |
| `schema_docs` | Supabase `information_schema` after connection | Table names, columns, data types, and foreign-key relationships. |

When you connect Supabase locally, the app automatically indexes all three sources. If a learner uses retrieval before connecting a database, the glossary and verified examples can still initialize locally, but `schema_docs` stays empty until a database connection supplies live metadata.

### Build the local index without opening the app

On macOS, double-click `scripts/Build_Text_to_SQL_Chroma.command`. On Windows, run `scripts/Build_Text_to_SQL_Chroma.bat`. Both create or update the project-local folder:

```text
Text-To-SQL-Agent-Lab/
├── data/
│   ├── business-glossary.json
│   └── few-shot-examples.json
├── scripts/
│   ├── Build_Text_to_SQL_Chroma.command
│   └── Open_Text_to_SQL_Agent_Lab.command
└── .chroma/                 # generated local vector index
```

The builder reads the two JSON files in `data/` and indexes glossary and verified SQL-example documents. It does not require database credentials. To also index the live schema from a terminal, set `SUPABASE_CONNECTION_URL` and `SUPABASE_DATABASE_PASSWORD`, then run:

```sh
python3 seed_chroma.py --with-schema
```

The generated `.chroma/` folder is an index cache. Treat `data/` as the editable source of truth; do not manually edit files inside `.chroma/`.

The following data is **not** put in Chroma:

- Olist table rows or customer-level records;
- the Supabase password or OpenAI API key;
- evaluator ground-truth SQL from `data/text-to-sql-benchmark.json`;
- value matching hints such as `São Paulo → SP` — those are small deterministic rules in `lib/agent.py`, not vector retrieval.

Chroma's embedding function creates the vector index. To use a different local path, set it before launching the server:

```sh
export CHROMA_PATH="$PWD/.chroma"
python3 text_to_sql_server.py
```

To reindex after editing the glossary, examples, or database schema, reconnect Supabase. For a complete local rebuild, stop the server, delete only the project's `.chroma/` folder, then restart and reconnect.

For a remote server or Chroma Cloud, set these only in the server environment—never in browser code:

```text
CHROMA_URL=https://your-chroma-host
CHROMA_API_KEY=...
CHROMA_TENANT=...
CHROMA_DATABASE=...
```

## Content and benchmarks

- `data/business-glossary.json`: Add `{term, definition, tables}` entries, then reconnect Supabase to reindex Chroma.
- `data/few-shot-examples.json`: Add question-to-SQL examples with `concepts`, `tables`, and `difficulty`, then reconnect Supabase to reindex Chroma.
- `data/text-to-sql-benchmark.json`: Add `{id, question, ground_truth_sql, difficulty, concepts, order_sensitive}` records.

The evaluator never compares generated and reference SQL strings. For an exact benchmark question, it executes both read-only queries and compares result values, duplicates, numeric tolerance, and ordering when the question requires ordering. Equivalent column aliases such as `revenue` and `total_revenue` do not fail a correct answer. A near match is never treated as correct. Ground truth remains evaluator-owned, is not indexed in Chroma, and is never passed to the repair request.

## Architecture

The implementation is intentionally small and modular:

- `lib/retrieval.py` — Chroma configuration, seeding, and retrieval.
- `lib/agent.py` — guided-stage options, ambiguity detection, context construction, and prompts.
- `lib/llm.py` — request-scoped OpenAI adapter returning structured JSON.
- `lib/sql_safety.py` — conservative static SQL policy, including writable CTE detection.
- `lib/database.py` — read-only PostgreSQL execution and schema introspection.
- `lib/evaluation.py` — execution-result comparison.
- `lib/service.py` — bounded execution / repair orchestration (maximum two repairs).

The plan in the UI is a concise structured artifact. The lab neither requests nor displays hidden chain-of-thought.

## Tests

Run `python3 -m unittest discover -s tests -v`. The tests cover safe and unsafe SQL, CTE mutation blocking, benchmark loading, result-set equivalence, alias-tolerant evaluation, numeric tolerance, ordering, scope gating, and Responses API parsing.

## Vercel deployment

`vercel.json` routes the site through `api/index.py`. Set `SUPABASE_CONNECTION_URL` and `SUPABASE_DATABASE_PASSWORD` in Vercel environment variables for database execution, alongside the Chroma variables above when using RAG. The OpenAI key is deliberately not a deployment environment variable: it remains request-scoped from the learner's configuration card. Use a least-privilege database role in production, enforce row/query-cost limits, and add RBAC, monitoring, audit-safe telemetry, and human review before allowing real organizational data.
