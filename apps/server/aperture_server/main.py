"""Aperture local server — a single FastAPI app.

Everything runs in one process on the user's machine:
  - projects + settings (file-backed under ~/.aperture)
  - compile cascade (T0-T5)
  - query executor (DuckDB)
  - ingest (sniff + profile + relationship discovery)
  - insight (diff + correlation + anomaly + drift)

No auth, no accounts, no remote services. The user owns everything.
"""
from __future__ import annotations

import shutil
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from aqir import compile_plan
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.ingest.app.profiler import profile_file
from services.ingest.app.sniffer import sniff
from services.insight.app.anomaly import detect_anomalies, ks_drift, psi
from services.insight.app.correlation import correlate_pairs
from services.insight.app.diffing import decompose_drivers, diff_metric, narrate_delta

from .context import RUNTIME
from .local_store import ProjectStore
from .providers import all_providers

app = FastAPI(title="Aperture (local)", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = ProjectStore()
# Auto-open last-current project so the UI doesn't need an explicit open on boot
_init_cur = store.current()
if _init_cur is not None:
    RUNTIME.open_project(_init_cur)


# -----------------------------------------------------------------------------
# Health + settings
# -----------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "app": "aperture",
        "version": "0.1.0",
        "provider": RUNTIME.settings.provider,
        "current_project_id": store.index.current_id,
    }


@app.get("/settings")
async def get_settings() -> dict:
    return {
        "settings": RUNTIME.settings.public_dict(),
        "providers": [p.__dict__ for p in all_providers()],
    }


class SettingsPatch(BaseModel):
    provider: str | None = None
    api_key: str | None = None
    model: str | None = None
    ollama_base_url: str | None = None
    theme: str | None = None
    density: str | None = None


@app.put("/settings")
async def put_settings(patch: SettingsPatch) -> dict:
    changes = {k: v for k, v in patch.model_dump().items() if v is not None}
    s = RUNTIME.update_settings(changes)
    return {"settings": s.public_dict()}


# -----------------------------------------------------------------------------
# Projects
# -----------------------------------------------------------------------------
@app.get("/projects")
async def list_projects() -> dict:
    return {
        "current_id": store.index.current_id,
        "projects": [p.__dict__ for p in store.list()],
    }


class CreateProject(BaseModel):
    name: str
    path: str | None = None


@app.post("/projects")
async def create_project(req: CreateProject) -> dict:
    if not req.name.strip():
        raise HTTPException(400, "name is required")
    project = store.create(req.name, req.path)
    RUNTIME.open_project(project)
    return {"project": project.meta.__dict__}


class SwitchProject(BaseModel):
    id: str


@app.post("/projects/switch")
async def switch_project(req: SwitchProject) -> dict:
    try:
        project = store.switch(req.id)
    except KeyError:
        raise HTTPException(404, f"project {req.id} not found") from None
    RUNTIME.open_project(project)
    return {"project": project.meta.__dict__}


class RenameProject(BaseModel):
    name: str


@app.patch("/projects/{pid}")
async def rename_project(pid: str, req: RenameProject) -> dict:
    try:
        meta = store.rename(pid, req.name)
    except KeyError:
        raise HTTPException(404) from None
    return {"project": meta.__dict__}


@app.delete("/projects/{pid}")
async def delete_project(pid: str, remove_files: bool = False) -> dict:
    store.delete(pid, remove_files=remove_files)
    cur = store.current()
    if cur is not None:
        RUNTIME.open_project(cur)
    else:
        RUNTIME.close_project()
    return {"ok": True}


# -----------------------------------------------------------------------------
# Files
# -----------------------------------------------------------------------------
def _project_required():
    pr = RUNTIME.project_runtime
    if pr is None:
        raise HTTPException(409, "no project is currently open; create or switch one first")
    return pr


@app.get("/files")
async def list_files() -> dict:
    pr = _project_required()
    uploads = pr.project.uploads_dir
    files: list[dict] = []
    for f in sorted(uploads.glob("*")):
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
    return {"files": files, "project": pr.project.meta.name}


@app.post("/files")
async def upload_file(file: UploadFile) -> dict:
    pr = _project_required()
    if file.filename is None:
        raise HTTPException(400, "missing filename")
    dst = pr.project.uploads_dir / file.filename
    with dst.open("wb") as fp:
        shutil.copyfileobj(file.file, fp)

    # Profile + update catalog in-process
    sniffed = sniff(dst)
    table = profile_file(dst, table_name=dst.stem)
    catalog = pr.project.load_catalog()
    tables = catalog.setdefault("tables", {})
    tables[table.name] = {
        "name": table.name,
        "primary_key": table.primary_key,
        "profile": {
            "rows": table.profile.rows,
            "source_path": table.profile.source_path,
        },
        "columns": {
            c.name: {
                "name": c.name,
                "type": c.type.value,
                "description": c.description,
                "profile": {
                    "distinct": c.profile.distinct,
                    "null_share": c.profile.null_share,
                    "sample_values": c.profile.sample_values,
                    "is_pii": c.profile.is_pii,
                    "pii_kind": c.profile.pii_kind,
                },
            } for c in table.columns.values()
        },
    }
    catalog["version"] = catalog.get("version", 0) + 1
    pr.project.save_catalog(catalog)

    # Re-register in the executor
    pr.executor.register_table(table.name, str(dst))

    # Refresh the project runtime so compile sees the new tables
    RUNTIME.open_project(pr.project)
    return {
        "file": {"name": dst.name, "size": dst.stat().st_size},
        "table": table.name,
        "columns": list(table.columns),
        "rows": table.profile.rows,
        "sniffed": asdict(sniffed) if is_dataclass(sniffed) else {},
    }


@app.delete("/files/{name}")
async def delete_file(name: str) -> dict:
    pr = _project_required()
    p = pr.project.uploads_dir / name
    if not p.exists():
        raise HTTPException(404)
    p.unlink()
    catalog = pr.project.load_catalog()
    catalog.get("tables", {}).pop(Path(name).stem, None)
    catalog["version"] = catalog.get("version", 0) + 1
    pr.project.save_catalog(catalog)
    RUNTIME.open_project(pr.project)
    return {"ok": True}


# -----------------------------------------------------------------------------
# Catalog / schema
# -----------------------------------------------------------------------------
@app.get("/catalog")
async def get_catalog() -> dict:
    pr = _project_required()
    return pr.project.load_catalog()


# -----------------------------------------------------------------------------
# Ask
# -----------------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str


@app.post("/ask")
async def ask(req: AskRequest) -> dict:
    pr = _project_required()
    cascade = pr.make_cascade()
    cr = await cascade.resolve(req.question)
    plan_dict: dict[str, Any] | None = None
    sql: str | None = None
    rows: list[dict] = []
    columns: list[str] = []
    row_count = 0
    latency_ms = 0
    cached = False
    if cr.plan is not None:
        plan_dict = cr.plan.model_dump(exclude_none=True)
        try:
            sql = compile_plan(cr.plan, pr.slice_, dialect="duckdb")
            exec_result = pr.executor.execute(sql, plan_hash=cr.plan.fingerprint())
            rows = exec_result.rows
            columns = exec_result.columns
            row_count = exec_result.row_count
            latency_ms = exec_result.latency_ms
            cached = exec_result.cached
        except Exception as exc:
            return {
                "question": req.question,
                "tier": cr.tier,
                "english": cr.english,
                "plan": plan_dict,
                "sql": sql,
                "error": str(exc),
                "tokens_in": cr.tokens_in,
                "tokens_out": cr.tokens_out,
            }

    # Persist to project history + plan cache
    record = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "question": req.question,
        "tier": cr.tier,
        "tokens_in": cr.tokens_in,
        "tokens_out": cr.tokens_out,
        "english": cr.english,
        "plan": plan_dict,
        "sql": sql,
        "row_count": row_count,
        "latency_ms": latency_ms,
        "cached": cached,
        "note": cr.note,
    }
    pr.project.append_history(record)
    if cr.plan is not None:
        plans_disk = pr.project.load_plans()
        plans_disk[cr.plan.fingerprint()] = plan_dict
        pr.project.save_plans(plans_disk)

    return {
        **record,
        "columns": columns,
        "rows": rows,
    }


# -----------------------------------------------------------------------------
# History
# -----------------------------------------------------------------------------
@app.get("/history")
async def history(limit: int = 50) -> dict:
    pr = _project_required()
    return {"history": pr.project.read_history(limit=limit)}


# -----------------------------------------------------------------------------
# Insight
# -----------------------------------------------------------------------------
class InsightDiff(BaseModel):
    metric: str
    history: list[float]
    current: float
    previous_by_dim: dict[str, float] = {}
    current_by_dim: dict[str, float] = {}


@app.post("/insight/diff")
async def insight_diff(req: InsightDiff) -> dict:
    d = diff_metric(metric=req.metric, history=req.history, current=req.current)
    drivers = decompose_drivers(previous_by_dim=req.previous_by_dim, current_by_dim=req.current_by_dim)
    if d is None:
        return {"significant": False}
    return {"delta": d.__dict__, "drivers": [dr.__dict__ for dr in drivers], "narration": narrate_delta(d, drivers)}


class InsightDrift(BaseModel):
    expected: list[float]
    actual: list[float]


@app.post("/insight/drift")
async def insight_drift(req: InsightDrift) -> dict:
    stat, p = ks_drift(req.expected, req.actual)
    return {"psi": psi(req.expected, req.actual), "ks_stat": stat, "ks_p": p}


class InsightAnomaly(BaseModel):
    series: list[float]
    period: int = 7
    z_cutoff: float = 3.0


@app.post("/insight/anomaly")
async def insight_anomaly(req: InsightAnomaly) -> dict:
    out = detect_anomalies(req.series, period=req.period, z_cutoff=req.z_cutoff)
    return {"anomalies": [a.__dict__ for a in out]}


class InsightCorrelation(BaseModel):
    columns: dict[str, list[float]]
    kinds: dict[str, str]
    fdr: float = 0.05


@app.post("/insight/correlation")
async def insight_correlation(req: InsightCorrelation) -> dict:
    import numpy as np
    cols = {k: np.asarray(v) for k, v in req.columns.items()}
    results = correlate_pairs(columns=cols, kinds=req.kinds, fdr=req.fdr)  # type: ignore[arg-type]
    return {"results": [r.__dict__ for r in results]}


# -----------------------------------------------------------------------------
# Metrics (admin)
# -----------------------------------------------------------------------------
@app.get("/metrics")
async def metrics() -> dict:
    pr = RUNTIME.project_runtime
    if pr is None:
        return {"by_tier": {}, "total_tokens": 0}
    tenant = pr.project.meta.id
    return {
        "by_tier": pr.meter.by_tier(tenant),
        "total_tokens": sum(pr.meter.total_for(tenant)),
    }
