# Text-to-SQL Agent Lab

An interactive, standalone follow-on to SQL Practice Lab. This course teaches how a production-minded Text-to-SQL agent turns a business question into safe, inspectable SQL through retrieval, planning, execution, validation, and repair.

It also includes hands-on material on schema design, explainability, transparency, accountability, and an experiment that compares readable and ambiguous data schemas in Databricks Genie.

## What learners can do

- Work through guided stages: understand the question, retrieve context, use examples, plan, generate SQL, validate it, and repair failures.
- Build a configurable agent in the **Experiment Lab**, run it against a connected Supabase database, inspect its evidence, and compare runs.
- Explore **Database Design for Text-to-SQL**, including naming conventions, primary/foreign keys, table grain, and documentation.
- Download original or ambiguously named datasets for a controlled Genie comparison.
- Learn practical XAI concepts with trace, perturbation, permission, audit-trail, and incident-investigation simulations.

Illustrative teaching examples are clearly labelled. Live experiment results come only from the configured local server and database.

## Run locally

Requirements: Python 3.10+ and a Supabase/PostgreSQL database containing the Olist `customers`, `orders`, `order_items`, and `products` tables.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 text_to_sql_server.py
```

Then open [http://127.0.0.1:8766](http://127.0.0.1:8766). Do not open `index.html` directly: the server provides the API endpoints used by the lab.

Convenience launchers are available in `scripts/` for macOS and Windows:

- `Open_Text_to_SQL_Agent_Lab.command` / `.bat`
- `Build_Text_to_SQL_Chroma.command` / `.bat`

`../SQL-Practice-Lab` is a read-only sibling reference project and is never modified by this app.

## Quick start

1. Start the local server and open the site.
2. In **Connections**, select an API provider, enter its key and model, then use **Test API connection**.
3. Enter a Supabase Session pooler URL (port 5432) and its password, then connect.
4. Wait for the app to index retrieval context.
5. Open **Experiment Lab**, select a challenge and an agent configuration, then run and compare experiments.

The built-in challenges have evaluator-owned expected outputs. Custom questions are useful for exploration but are not benchmarked.

## Providers and data handling

The UI supports:

- **OpenAI** — default model: `gpt-4.1-mini`.
- **Duke AI Gateway** — use a newly generated Duke key and select `GPT 4.1` or a model returned by **Load available models**. Requests use Duke's OpenAI-compatible Responses endpoint.

API keys remain in page memory for the current session only. They are not written to source code, browser storage, a database, or server logs. The server uses an eight-second, read-only database transaction and caps displayed query results at 200 rows.

## Retrieval and evaluation

ChromaDB stores a local index at `.chroma/` with compact retrieval documents:

| Collection | Source | Purpose |
| --- | --- | --- |
| `business_glossary` | `data/business-glossary.json` | Business definitions and domain terms. |
| `sql_examples` | `data/few-shot-examples.json` | Verified question-to-SQL patterns. |
| `schema_docs` | Supabase `information_schema` | Live table, column, and foreign-key metadata. |

The full Olist dataset, database password, API keys, and evaluator ground-truth SQL are not indexed. Reconnect Supabase after changing glossary, example, or schema content; run `seed_chroma.py --with-schema` to build an index from the terminal with database credentials available.

For exact benchmark questions, the evaluator executes generated and reference SQL and compares result values, duplicates, numeric tolerance, and required ordering. It does not compare SQL strings, and a near match never counts as correct.

## Course data

- `data/business-glossary.json` — retrieval definitions.
- `data/few-shot-examples.json` — verified SQL examples.
- `data/text-to-sql-benchmark.json` — evaluator-owned benchmark questions and SQL.
- `data/ambiguous_schema_instructor_key.json` — instructor-only mapping between the ambiguous schema's files/columns and the original schema.

The **Try It in Genie** lesson links to download packages for the readable original schema and a schema whose filenames and columns have been anonymized. Upload one package to each separate Genie space, ask the same question, and compare what metadata each system needs. This is a learning experiment, not an accuracy claim.

## Project structure

- `index.html` — course, guided lessons, interactive simulations, and experiment UI.
- `text_to_sql_server.py` — local development server and API routes.
- `api/index.py` — Vercel API handler.
- `lib/agent.py` — ambiguity checks, context construction, and prompts.
- `lib/llm.py` — request-scoped OpenAI-compatible provider adapter.
- `lib/retrieval.py` — Chroma configuration, indexing, and retrieval.
- `lib/database.py` / `lib/sql_safety.py` — read-only execution and SQL guardrails.
- `lib/evaluation.py` / `lib/service.py` — result evaluation and bounded repair orchestration.

The app exposes concise plans, retrieved context, execution results, validation, and repair history. It does not request or display hidden chain-of-thought.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

Tests cover SQL safety, mutation rejection, benchmark and retrieval data, result-set evaluation, ambiguity/scope checks, and OpenAI-compatible API response handling.

## Deploying on Vercel

`vercel.json` routes requests through `api/index.py`. Configure `SUPABASE_CONNECTION_URL` and `SUPABASE_DATABASE_PASSWORD` as deployment environment variables. For Chroma Cloud, also configure `CHROMA_API_KEY`, `CHROMA_TENANT`, and `CHROMA_DATABASE`.

Create the `business_glossary`, `sql_examples`, and `schema_docs` collections in Chroma Cloud. To index them once from the deployed lab, set a secret `CHROMA_SEED_TOKEN` in Vercel, then select **Seed Chroma from database** in the lab and enter that token. The endpoint upserts the project glossary and verified SQL examples plus the live Supabase schema metadata. The token is required so visitors cannot re-index the collections.

Alternatively, with the same environment variables set locally, run:

```sh
python3 seed_chroma.py --cloud --with-schema
```

Set `DUKE_API_KEY` only when the deployment should use Duke AI Gateway on behalf of visitors; the browser never receives this key and learners select only a model. Protect a shared deployment with authentication or rate limits before public use. Use least-privilege database credentials and add production controls such as RBAC, query-cost limits, monitoring, audit-safe telemetry, and human review before connecting real organizational data.
