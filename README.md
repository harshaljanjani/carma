### Carma

A FastAPI backend and Streamlit client that lets a user explore a used-car inventory through a
contextual conversation, book viewings, qualify leads, and be remembered across sessions. The 
design is data-driven.

![System Diagram](https://i.ibb.co/cKGPFznf/system-diagram-1.png)

### Quick start

Requires [uv](https://docs.astral.sh/uv/) and a [Google AI Studio](https://aistudio.google.com/) API key.
Commands below assume a Linux/WSL shell (bash).

```bash
python3 -m venv .venv
source .venv/bin/activate

uv sync
cp .env.example .env
# then edit .env and replace GEMINI_API_KEY with your key; it is auto-loaded (python-dotenv)
# on every run, so this persists across sessions. Alternatively, for the current shell only:
export GEMINI_API_KEY="your_google_ai_studio_key_here"
# one-time: build the enriched catalog (data/enriched.json)
uv run python -m assistant.enrich
```

`enrich` uses the LLM to normalise each listing when `GEMINI_API_KEY` is set, and falls back to a
regex extractor otherwise. Force a mode with `--llm` or `--regex`.

**Terminal 1 (Backend):**

```bash
uv run uvicorn main:app --reload --port 8000
```

**Terminal 2 (Client):**

```bash
uv run streamlit run app.py
```

Open the Streamlit URL, optionally enter your name in the header field (this is your user ID), and chat.
To prove cross-session recall, chat with a name, refresh the page for a fresh session, and greet the
assistant again, you should see that your name, budget, and preferences persist.

### Demo

**1. Multi-turn conversation exploring the inventory.**

**2. Cross-session recall: the agent recalls a returning user's preferences and history in a completely new session:**

![Cross-session recall in a new session](https://i.ibb.co/yBFbFvLT/Screenshot-2026-07-04-141208.png)

### Design choices

**Client (Streamlit):** The assessment grades a reactive chat UI and wants screenshots of a seamless
multi-turn conversation and cross-session recall. Streamlit's `st.session_state` maps directly onto the
short-term memory model. The client is a thin `httpx` transport with no LLM keys or business logic; 
swap it for a notebook without touching `main.py`.

**Agent framework (LiteLLM to `gemini/gemini-2.5-pro`):** One provider-agnostic interface for
tool-calling and Pydantic-structured output. A heavier agent framework would be over-engineering for a
single tool-routing loop over 100 rows.

**Retrieval (Hybrid, structured-first (no vector DB)):** With only 100 clean rows, an in-memory pandas
filter answers instantly; a vector database would be bloat. Reliable structured fields (`year` as exact +
range, `make`, `model`) drive deterministic filtering; a lexical keyword score (NLTK stopwords + domain
terms) over an LLM-normalised English summary handles soft attributes like colour and body type. The LLM
extracts a typed `FilterQuery`, <ins>never free-form SQL</ins>, so numeric constraints can't silently fail.

**Memory (SQLite for long-term) and in-process session state (for short-term).** Short-term memory keeps an
ordered list of the last shown `Listing_ID`s, so "the mileage on the first one" resolves to a concrete
row rather than fuzzy text. Long-term memory uses SQLite (relational, zero-infra) to join users,
preferences, liked listings, and leads by the stable `Listing_ID`.

**Intent & guardrails (Two-stage, routing decoupled from execution):** A cheap Pydantic-constrained
classifier labels each message; the backend then dispatches in Python. Out-of-scope requests (non-
automotive, competitors, other platforms, code, history) return a hardcoded decline immediately, never
reaching the retrieval path - safer, cheaper, and jailbreak-resistant.

### A note on the data (why price isn't a filter)

The dataset has no `Price` or `Mileage` column. Across both provided files, a genuine sale price appears
in at most ~1 in 3 listings (most of the rest state none; many quotes are monthly installments), and 17%
of descriptions are in Arabic. So the assistant **captures the user's budget at booking as a qualified
lead** rather than filtering on price it doesn't have, and the one-time enrichment pass doubles as a
multilingual normaliser so English queries can match Arabic listings. Extracted price/mileage are
nullable and shown for display only; the agent never invents them.

### Evaluation

`eval/eval_retrieval.py` runs a labelled set of natural-language queries whose ground truth is computed 
deterministically from the data (e.g. "mercedes between 2015 and 2018" = listings where make==mercedes-benz
and 2015<=year<=2018), and reports precision, recall, F1, and exact-set-match per query and in aggregate. 
Building this harness surfaced concrete number-handling errors (open-ended year ranges collapsing to a 
single year, km figures misread as budget, extracted numbers leaking into keywords and destroying recall)
that were then fixed; dev-set macro F1 went from 0.57 to 1.00.

`eval/eval_holdout.py` re-runs the same metric on a disjoint set of queries the logic was never tuned
against (different makes, aliases, year phrasings) to guard against overfitting; it also scores 1.00,
confirming the fixes are general. `eval/eval_intent.py` measures intent-classification accuracy (16/16
on the Gemini path). `eval/eval_conversational.py` is a broader behavioural harness: 118 assertions
across every intent class with quirky/slang phrasings plus multi-turn booking, cancellation, reference
resolution, relative dates, conflicts, grounding, and confused/browse requests, asserting structural
outcomes (intent, real listings/bookings, actually-recorded leads) rather than exact prose; it scores
99.2% (the lone miss is a documented slang ambiguity).

Run from the repo root with `.venv` active:

```bash
# deterministic retrieval metrics: precision / recall / F1 / exact-set-match (no API key)
uv run python eval/eval_retrieval.py
# same metric on a disjoint held-out query set, guarding against overfitting (no API key)
uv run python eval/eval_holdout.py
# intent-classification accuracy (Gemini path; needs GEMINI_API_KEY)
uv run python eval/eval_intent.py
# 118-assertion behavioural harness across every intent class (Gemini path; needs GEMINI_API_KEY)
uv run python eval/eval_conversational.py
```

The two retrieval evals use the deterministic heuristic extractor by default; set `EVAL_LLM=1` to
route filter extraction through the LLM instead.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/chat` | Full conversational turn (intent to retrieval/booking to grounded reply) |
| POST | `/chat/stream` | Same, streamed as NDJSON token events plus a final event (listings, bookings) |
| GET | `/inventory` | Structured inventory retrieval (`make`, `model`, `year_min/max`, `mileage_max`, `color`, `body_type`, `q`) |
| GET | `/inventory/{id}` | Single listing |
| POST | `/leads` | Persist a qualified lead (also appended to `data/leads.csv`) |
| GET | `/users/{id}` | Long-term profile rehydration |
| GET | `/health` | Liveness + listing count |

## Out of scope / future work

The prototype favours local files and in-memory state. To productionise: migrate the inventory to a data 
warehouse (Postgres to BigQuery/Snowflake) behind the same retrieval contract; promote lexical search to a 
managed vector store (pgvector/Chroma) with multilingual embeddings and reranking once the catalog is large;
turn the one-off enrichment into a streaming pipeline that writes confidence-scored `price`/`mileage` columns
(the point at which price could finally become a gated filter); move short-term memory to Redis and long-term
memory to managed Postgres; and serve containerised FastAPI replicas behind a load balancer with a LiteLLM 
Router for multi-key failover, cost tracking, and tracing.

## Layout

```
main.py                FastAPI backend
app.py                 Streamlit client
assistant/
  agent.py             two-stage router + dispatch (orchestration)
  llm.py               LiteLLM wrapper (completion + structured output)
  enrich.py            one-time LLM/regex enrichment pass
  retrieval.py         hybrid structured + lexical search
  memory.py            SQLite long-term + in-session short-term memory
  booking.py           slot validation + lead capture to CSV
  guardrails.py        out-of-scope decline messages
  data.py, schemas.py, config.py, text.py
```
