# Text-to-SQL Agent Lab

An interactive course for learning how a Text-to-SQL agent turns a business question into safe, inspectable SQL. It is the standalone follow-on to the read-only SQL Practice Lab reference project.

The lab uses the Olist Brazilian e-commerce dataset and teaches the practical controls around an agent workflow: business context, schema retrieval, verified examples, planning, read-only execution, evaluation, repair, and human review.

## Live site

Welcome to explore the live [Text-to-SQL Agent Lab](https://text-to-sql-agent-lab-ids706.vercel.app/).

## Project contribution

**Design question:** How can a learner judge whether a Text-to-SQL agent deserves trust, rather than trusting SQL merely because it executes?

This project is an interactive Responsible AI teaching resource that makes the normally hidden parts of a Text-to-SQL workflow available for inspection. Instead of presenting a chatbot that only returns SQL, it lets learners:

- configure the agent components that ground and constrain a query;
- inspect the retrieved context, concise plan, generated SQL, execution result, evaluation, and repair history for a run;
- compare observable output changes after changing a component; and
- distinguish a permission policy from a database operation through a safe, simulated policy control.

The contribution is a practical learning interface for connecting Text-to-SQL engineering decisions with Responsible AI questions about observability, behavioral explainability, transparency, accountability, and evaluation.

## Contents

- [What you can learn](#what-you-can-learn)
- [Run locally](#run-locally)
- [Use the lab](#use-the-lab)
- [Configuration](#configuration)
- [How the agent works](#how-the-agent-works)
- [Data, retrieval, and evaluation](#data-retrieval-and-evaluation)
- [Safety and privacy](#safety-and-privacy)
- [Limitations and future work](#limitations-and-future-work)
- [Project structure](#project-structure)
- [Development](#development)
- [Deploy on Vercel](#deploy-on-vercel)

## What you can learn

| Course area | Focus |
| --- | --- |
| Level 1 — Agent basics | When a workflow needs an agent instead of a single LLM response. |
| Level 2 — Text-to-SQL agent | How business context, schema retrieval, examples, planning, validation, and repair shape generated SQL. |
| Level 3 — Explainable AI | How to inspect a run, test observable changes in behavior, and set permission boundaries for agent actions. |
| Level 4 — Advanced | Production architecture, database design, and an enterprise extension with Trino. |

The live **Experiment Lab** lets learners configure an agent, run it against a connected PostgreSQL database, inspect the evidence used by the agent, and compare runs within the current browser tab.

## Run locally

### Requirements

- Python 3.10 or later
- A PostgreSQL/Supabase database with the Olist `customers`, `orders`, `order_items`, and `products` tables
- An API key for a supported model provider when running live agent experiments

### Start the server

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 text_to_sql_server.py
```

Open [http://127.0.0.1:8766](http://127.0.0.1:8766).

Do not open `index.html` with `file:///`: the page needs the local server for its API endpoints.

### Optional launchers

The `scripts/` directory includes convenience launchers for macOS and Windows:

| Start the lab | Build a local Chroma index |
| --- | --- |
| `Open_Text_to_SQL_Agent_Lab.command` / `.bat` | `Build_Text_to_SQL_Chroma.command` / `.bat` |

## Use the lab

1. In **Connections**, choose an API provider, enter an API key and model, and test the connection.
2. Enter a Supabase **Session pooler** URL on port `5432` and its password, then connect.
3. After connecting, the app indexes the available schema context for retrieval.
4. Open **Build & Test Your Agent**, select a benchmark challenge or write an in-scope question, choose components, and run the agent.
5. Inspect the plan, retrieved context, SQL, execution result, evaluation, and repair history. Compare two runs after changing one component.

Built-in benchmark questions have evaluator-owned expected outputs. Custom questions can be explored but are not benchmarked.

## Configuration

Copy the example file when local environment variables are needed:

```sh
cp .env.example .env
```

`.env` is ignored by Git. Do not commit API keys, passwords, or seed tokens.

| Variable | Used for | Required when |
| --- | --- | --- |
| `OPENAI_API_KEY` | OpenAI embeddings for Chroma Cloud; optionally local OpenAI-based workflows | Using Chroma Cloud with OpenAI embeddings |
| `DUKE_API_KEY` | Duke AI Gateway | Using the Gateway from a configured environment |
| `SUPABASE_CONNECTION_URL` | PostgreSQL/Supabase connection URL | Server-side or terminal-based database access |
| `SUPABASE_DATABASE_PASSWORD` | Password for the Supabase connection | Server-side or terminal-based database access |
| `CHROMA_API_KEY` | Chroma Cloud authentication | Using Chroma Cloud |
| `CHROMA_TENANT` | Chroma Cloud tenant | Using Chroma Cloud |
| `CHROMA_DATABASE` | Chroma Cloud database name | Using Chroma Cloud |
| `CHROMA_SEED_TOKEN` | Protects the deployed Chroma indexing endpoint | Seeding Chroma from Vercel |

For a local interactive run, the browser sends the selected provider key only with the current request. It is not written to source code, browser storage, or the project database.

## Prepare the course data

This repository includes retrieval documents and benchmark definitions, but it does **not** include the full Olist database or database credentials. Before running live queries, prepare a compatible PostgreSQL or Supabase database:

1. Download the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
2. Create a PostgreSQL or Supabase project and import the Olist CSV files while preserving their original column names.
3. Ensure the core tables are available: `customers`, `orders`, `order_items`, and `products`.
4. Confirm that the fields used by the course exist: `customers.customer_id`, `customers.customer_unique_id`, `customers.customer_state`, `orders.order_id`, `orders.customer_id`, `orders.order_status`, `orders.order_purchase_timestamp`, `order_items.order_id`, `order_items.product_id`, `order_items.price`, and `order_items.freight_value`.
5. Copy the project's **Session pooler** connection URL on port `5432`, leave the `[YOUR-PASSWORD]` placeholder in the URL, and enter the actual password separately in the lab.

The supplied benchmark SQL assumes the Olist table names and fields above. If you use another dataset or rename its schema, you can still explore custom questions, but the course benchmarks and retrieval examples will no longer be directly comparable.

## How the agent works

```text
Business question
       ↓
Business definitions, schema, examples, and value hints
       ↓
Optional concise plan → SQL generation → SQL safety validation
       ↓
Read-only execution → benchmark evaluation → optional bounded repair
```

Agent components are independently selectable in the Experiment Lab:

| Component | Purpose |
| --- | --- |
| Business Semantics | Supplies course glossary definitions for terms such as revenue and delivered orders. |
| Schema Linking | Retrieves relevant tables, columns, and foreign-key relationships. |
| Example Retrieval | Retrieves verified question-to-SQL patterns. |
| Planning | Requests a short, student-visible SQL plan. |
| Validation | Parses generated SQL and blocks unsafe statements before execution. |
| Self-Correction | Allows up to two repair attempts after a validation or database error. |

The lab displays structured evidence—context, plans, SQL, execution status, evaluation, and repair history—not hidden model chain-of-thought.

## Data, retrieval, and evaluation

### Retrieval collections

| Collection | Source | Role |
| --- | --- | --- |
| `business_glossary` | `data/business-glossary.json` | Business definitions and domain language. |
| `sql_examples` | `data/few-shot-examples.json` | Verified SQL patterns for similar questions. |
| `schema_docs` | Supabase `information_schema` | Live table, column, and foreign-key metadata. |

Without cloud configuration, Chroma uses the local `.chroma/` directory. Reconnect Supabase after changing schema-related context, or seed from the terminal:

```sh
python3 seed_chroma.py --with-schema
```

### Benchmarks

`data/text-to-sql-benchmark.json` contains course benchmark questions and evaluator-owned ground-truth SQL. For an exact benchmark question, the evaluator executes both queries and compares returned values, duplicates, numeric tolerance, and required ordering. It does not compare SQL text; an executable query is not automatically correct.

### Course data

| File | Purpose |
| --- | --- |
| `data/business-glossary.json` | Retrieval definitions. |
| `data/few-shot-examples.json` | Verified few-shot SQL examples. |
| `data/text-to-sql-benchmark.json` | Benchmark prompts and ground-truth queries. |
| `data/ambiguous_schema_instructor_key.json` | Instructor-only mapping for the readable-versus-ambiguous schema exercise. |

The **Try It in Genie** lesson provides packages for a controlled comparison between readable and anonymized schemas. It is a teaching activity, not an accuracy claim.

## Safety and privacy

### Database controls

- Only one `SELECT`, `WITH`, or `EXPLAIN` statement is accepted.
- Write, DDL, and privilege operations—including `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, and locking `SELECT` clauses—are blocked.
- Every database transaction is marked read-only.
- Queries have an eight-second timeout and results are capped at 200 rows.

### Credential handling

- The local server binds to `127.0.0.1`.
- Browser-entered provider keys are request-scoped and never persisted by the app.
- Keep Supabase passwords, API keys, and `CHROMA_SEED_TOKEN` outside the repository.
- Use least-privilege database credentials and production controls such as authentication, RBAC, rate limits, monitoring, and human review before connecting organizational data.

## Limitations and future work

This is a teaching artifact, not a production Text-to-SQL deployment or a claim that any one agent configuration is universally best.

### Current limitations

- The live workflow and benchmark examples are tailored to the Olist schema; results may not transfer to other domains, schemas, or business vocabularies.
- LLM output can vary by provider, model version, prompt behavior, and run. A passing execution-based benchmark result is evidence for that question and configuration, not a guarantee of general correctness.
- Behavioral comparisons reveal observable sensitivity to changed inputs; they do not reveal private model reasoning or establish a general causal explanation of model behavior.
- The lab does not include a user study, expert review, or a production monitoring dataset.
- The permission interface in Level 3 is an educational simulation. It does not enforce RBAC, create an enterprise audit trail, or replace database-level authorization.
- The read-only controls reduce risk in this lab, but a real deployment also needs authentication, tenant isolation, query-cost controls, monitoring, incident response, and domain-specific review.

### Future directions

- Evaluate the same workflow across more benchmark questions, datasets, models, and repeated runs.
- Add a versioned experiment log and aggregate comparison view for reproducible classroom studies.
- Test the interface with learners and practitioners to evaluate whether the evidence shown improves appropriate trust and debugging.
- Connect policy decisions to real identity, authorization, and audit systems in a governed deployment.

## Project structure

```text
.
├── index.html                 # Course UI, guided lessons, and Experiment Lab
├── text_to_sql_server.py      # Local development server
├── api/index.py               # Vercel serverless handler
├── lib/
│   ├── agent.py               # Prompt construction and agent components
│   ├── database.py            # Read-only PostgreSQL access and schema discovery
│   ├── evaluation.py          # Result-set evaluation
│   ├── llm.py                 # OpenAI-compatible provider adapter
│   ├── retrieval.py           # Chroma indexing and retrieval
│   ├── service.py             # Execution and bounded repair orchestration
│   └── sql_safety.py          # SQL safety policy
├── data/                      # Glossary, examples, benchmarks, and course data
├── assets/                    # Course diagrams and branding
├── scripts/                   # macOS and Windows launchers
├── tests/                     # Unit tests
├── seed_chroma.py             # Terminal-based retrieval indexing
└── vercel.json                # Vercel routing and function configuration
```

## Development

### Run tests

```sh
python3 -m unittest discover -s tests -v
```

Tests cover SQL safety, mutation rejection, benchmark data, retrieval data, result-set evaluation, ambiguity and scope checks, and OpenAI-compatible response handling.

### Health check

With the local server running:

```sh
curl http://127.0.0.1:8766/api/health
```

## Deploy on Vercel

`vercel.json` routes API traffic through `api/index.py`. The production app uses request-scoped database engines, so configure these variables in the Vercel project settings:

| Deployment need | Vercel environment variables |
| --- | --- |
| Live PostgreSQL execution | `SUPABASE_CONNECTION_URL`, `SUPABASE_DATABASE_PASSWORD` |
| Chroma Cloud retrieval | `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE`, `OPENAI_API_KEY` |
| Protected cloud indexing | `CHROMA_SEED_TOKEN` |
| Duke AI Gateway | `DUKE_API_KEY` |

Create the `business_glossary`, `sql_examples`, and `schema_docs` collections in Chroma Cloud. To seed them from the deployed lab, set `CHROMA_SEED_TOKEN`, then use **Seed Chroma from database** and provide that token. The endpoint resets and repopulates the three course collections, so treat this as a privileged maintenance operation.

Alternatively, seed Chroma Cloud from a trusted terminal with the same environment variables:

```sh
python3 seed_chroma.py --cloud --with-schema
```

## License

See [LICENSE](LICENSE).
