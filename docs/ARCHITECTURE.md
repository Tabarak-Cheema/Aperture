# Architecture

> Aperture's novelty is the combination: a typed IR as the model's only output,
> a zero-token cascade in front of the model, plans promoted into templates, a
> render path the LLM provably can't reach, and fan-out-safe compilation.

Aperture is **local-first**. On your machine, one Python process runs a
FastAPI server backing a Vite-served React UI. Everything the user cares about
— projects, files, catalog, plans, history — lives under `~/.aperture/`.

## Shape

```
┌────────────┐ http /api  ┌─────────────────────────────────────┐
│ React app  │ ─────────► │  FastAPI server (apps/server)       │
│ (localhost │            │  ├─ /projects   /files   /settings  │
│  :5173)    │            │  ├─ /ask        /history            │
└────────────┘            │  ├─ /catalog    /metrics            │
                          │  └─ /insight/*                      │
                          └──┬──────────────────────────────────┘
                             │ in-process calls
                             ▼
                          ┌──────────────────────────────────┐
                          │ packages/  (AQIR, catalog, llm)  │
                          │ services/  (compile, query,      │
                          │             ingest, insight)     │
                          └──────────────────────────────────┘
                             │
                             ▼
                          DuckDB (:memory: or project parquet)
```

No tenants. No auth. No microservices to deploy. One process to boot.

## Projects on disk

```
~/.aperture/
  settings.json                   # provider, api key, theme, density
  projects.json                   # { current_id, projects: [...] }
  projects/
    <slug>/
      project.json
      data/uploads/               # original CSV/XLSX/Parquet/JSON files
      data/parquet/               # (future) versioned parquet
      catalog.json                # tables, columns, profiles, relationships
      plans.json                  # T0 plan cache
      history.jsonl               # Q&A log
      synonyms.json               # learned synonyms
```

Switching projects is an atomic in-process state swap — the catalog and plan
cache rebuild from the chosen project's files in milliseconds.

## The compile-once engine

### AQIR — the LLM's only output

`packages/aqir/aqir/schema.py` — a small typed JSON plan (Pydantic). Example:

```json
{"metrics":["revenue"],"dimensions":["region"],
 "filters":[{"dim":"country","op":"=","value":"PK"}],
 "time":{"dim":"order_date","range":"last_quarter","grain":"month"},
 "sort":[{"by":"revenue","dir":"desc"}],"limit":10}
```

* 60–120 tokens, not 300+ of SQL.
* Constrained decoding against the JSON Schema makes malformed output impossible.
* The compiler (`packages/aqir/aqir/compiler.py`) can only emit `SELECT`.

### Resolution cascade

Every question walks `services/compile/app/cascade.py`:

| Tier | Description                           | Tokens  | Latency |
|------|---------------------------------------|---------|---------|
| T0   | Plan cache (per-project, on disk)     | 0       | <5 ms   |
| T1   | Template match + entity linker        | 0       | ~20 ms  |
| T2   | Deterministic analytic grammar        | 0       | ~5 ms   |
| T3   | Local small model (optional)          | 0 cloud | ~1 s    |
| T4   | Cloud LLM, ≤ 800/120 tokens           | ≤ 920   | ~1–3 s  |
| T5   | Targeted repair (error + fragment)    | ≤ 250   | ~1 s    |

Accepted plans are **promoted**: added to the plan cache, registered as a
template, and persisted to `~/.aperture/projects/<slug>/plans.json`.

### Verification without the model

Before a plan runs, deterministic checks (`packages/aqir/aqir/validator.py`):

* Static: every column exists, types compatible, join path exists.
* **Fan-out detection**: summing a measure across a one-to-many join silently
  inflates totals. The compiler detects this from cardinalities and rewrites
  with pre-aggregation (symmetric aggregates).
* Plausibility: row count, null share, grand-total drift.
* Deterministic English rendering: *"Sum of revenue, by region, for Jul–Sep
  2026, top 10"* — the user confirms intent without narration tokens.

### Isolation

The LLM gateway is reachable only from the compile path. A test
(`apps/server/tests/test_isolation.py`) walks the render-path source
(`services/query`, `services/insight`, `apps/web`) and fails the build if any
import of `llm_gateway` appears there. The LLM provably cannot touch the
render path.

## Providers

User picks provider in **Settings**. Keys never go into env files.

* **Ollama** (default, no key, runs offline) — uses its OpenAI-compatible
  `/v1/chat/completions` endpoint on `http://localhost:11434`.
* **Groq**, **OpenAI**, **Together**, **Fireworks** — same thin OpenAI-shape
  client, different base URL. Switching is a settings change, never a code
  change.

## Security

* **No accounts, no network sync.** If you never add a cloud key, nothing
  leaves your machine.
* **Data never goes to the LLM.** Only schema slices, column *descriptions*
  and question text are sent. PII-flagged columns are redacted even in sample
  values.
* **Read-only execution** (SELECT-only via AST allow-list; cost guard; row
  cap).
* **Prompt-injection resistance.** The model's output is a schema-validated
  plan, not code. Text inside the data or question can't make it run anything
  outside the IR.
