# Aperture

> Ask anything about your data. Runs on your machine. Pay for the first question, not the thousandth.

**Local-first analytics.** No account. No cloud. No data leaves your machine unless you point
Aperture at a cloud LLM — and even then, only the schema and the question are sent, never your data.

## Install

### Option 1 — Download the app (recommended)

Grab the latest build from the [Releases](https://github.com/Tabarak-Cheema/Aperture/releases) page:

| OS      | File                       | How to run               |
|---------|----------------------------|--------------------------|
| Windows | `Aperture-windows.exe`     | Double-click             |
| macOS   | `Aperture-macos`           | `chmod +x` then open     |
| Linux   | `Aperture-linux`           | `chmod +x ./Aperture-linux && ./Aperture-linux` |

Your default browser opens to the app. No Python, no Node, no setup. Projects, files, settings and
history live under `~/.aperture/` on your disk.

### Option 2 — From source (developers)

Requirements: **Python 3.10 – 3.13**, **Node 20+**.

```bash
git clone https://github.com/Tabarak-Cheema/Aperture.git
cd Aperture
start.bat                   # Windows
./scripts/start.sh          # Linux / macOS
```

To build your own single-file app from source:

```bash
./scripts/build-desktop.sh         # produces dist/Aperture
.\scripts\build-desktop.ps1        # produces dist\Aperture.exe (Windows)
```

## Use

1. **Create a project.** It lives on your disk under `~/.aperture/projects/<slug>/`.
2. **Add files.** Drop CSVs, Excel, Parquet or JSON into the Files page. They are profiled on
   upload — types, PII, candidate keys, relationships — with zero LLM tokens.
3. **Ask.** Try `"revenue by region"`, `"top 10 country by sales"`, `"orders by city last quarter"`.
   The plan, SQL and resolution tier are shown with every answer; click **Lineage** to see them.
4. **Keep going.** Repeated or similar questions resolve at T0 or T1 with zero tokens.

Projects, catalog, plan cache, history and settings all persist across sessions on your machine.
Switch between projects from the dropdown in the top bar.

## LLM providers

Aperture resolves most questions without an LLM. For the ones that do need one, you choose the
provider in **Settings** (no `.env` file to edit):

* **Ollama** (default, local, free) — `ollama serve`, then `ollama pull llama3.2`
* **Groq** (cloud, fast, generous free tier) — paste your API key in Settings
* **OpenAI** — paste your API key
* **Together**, **Fireworks** — also supported

Keys are stored only in `~/.aperture/settings.json` on your machine.

## Why

Most natural-language BI tools call the LLM on every question, every page load and every refresh.
Aperture calls it only when it meets a question it has never seen. It then compiles the answer
into a reusable, verifiable query plan, so the cost per answered question falls toward zero as
usage grows. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Layout

```
aperture/
  apps/server/          Single local FastAPI app (one process, no accounts)
  apps/web/             React + Vite + responsive UI
  apps/desktop/         PyInstaller spec for Aperture.exe / Aperture
  packages/aqir/        AQIR schema + deterministic SQL compiler (Apache-2.0)
  packages/catalog/     Catalog, semantic layer, entity linker
  packages/llm_gateway/ Thin OpenAI-compatible client with Ollama support
  services/compile/app/ Cascade engine (T0–T5)
  services/query/app/   DuckDB executor with result cache
  services/ingest/app/  File sniffer, profiler, relationship discovery
  services/insight/app/ Diffing, correlation, anomaly, drift
  evals/                Benchmark harness
  deploy/               Optional Dockerfile + compose
```

## License

AQIR schema and compiler (`packages/aqir/`): Apache-2.0.
Everything else: source-available (see [LICENSE](LICENSE)).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
