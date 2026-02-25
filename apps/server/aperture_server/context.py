"""Per-project runtime context.

Holds the catalog slice, synonym index, plan cache, template index, and gateway
client for the currently-open project. Swapped atomically when the user picks a
different project in the UI.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from aqir.compiler import CatalogSlice, DimensionDef, MetricDef
from catalog import SynonymIndex
from llm_gateway import GatewayClient, Meter

from services.compile.app.cascade import Cascade, PlanCache
from services.compile.app.grammar import GrammarParser
from services.compile.app.promoter import Promoter
from services.compile.app.templates import TemplateIndex
from services.query.app.executor import Executor, ResultCache

from .local_store import Project, Settings
from .providers import build_client


@dataclass
class ProjectRuntime:
    project: Project
    slice_: CatalogSlice
    synonyms: SynonymIndex
    plans: PlanCache
    templates: TemplateIndex
    grammar: GrammarParser
    promoter: Promoter
    executor: Executor
    meter: Meter
    llm: GatewayClient

    def make_cascade(self) -> Cascade:
        async def _llm_call(question: str, slice_text: str, examples, schema):
            from llm_gateway import PromptBuilder
            pb = PromptBuilder()
            system, user = pb.build(question=question, slice_text=slice_text, examples=examples)
            return await self.llm.complete_json(system=system, user=user, schema=schema)

        return Cascade(
            cache=self.plans, templates=self.templates, grammar=self.grammar,
            synonyms=self.synonyms, slice_=self.slice_,
            tenant_id=self.project.meta.id, catalog_version=1,
            llm_call=_llm_call,
        )


class Runtime:
    """Process-wide runtime state. Thread-safe swap on project change."""

    def __init__(self):
        self._lock = threading.RLock()
        self._settings = Settings.load()
        self._project_runtime: ProjectRuntime | None = None

    # ---- Settings ----
    @property
    def settings(self) -> Settings:
        return self._settings

    def update_settings(self, patch: dict) -> Settings:
        with self._lock:
            for k, v in patch.items():
                if k in Settings.__dataclass_fields__:
                    setattr(self._settings, k, v)
            self._settings.save()
            # Rebuild the LLM client if provider/key/model changed and a project is open
            if self._project_runtime is not None:
                self._project_runtime.llm = build_client(
                    self._settings.provider, self._settings.api_key,
                    self._settings.model, self._settings.ollama_base_url,
                )
        return self._settings

    # ---- Project ----
    @property
    def project_runtime(self) -> ProjectRuntime | None:
        return self._project_runtime

    def open_project(self, project: Project) -> ProjectRuntime:
        with self._lock:
            rt = _build_project_runtime(project, self._settings)
            self._project_runtime = rt
            return rt

    def close_project(self) -> None:
        with self._lock:
            self._project_runtime = None


def _build_project_runtime(project: Project, settings: Settings) -> ProjectRuntime:
    """Compose a fresh runtime state from a project's on-disk files."""
    catalog_json = project.load_catalog()
    slice_ = _catalog_to_slice(catalog_json)
    synonyms = _load_synonyms(project, catalog_json)
    plans = PlanCache()
    # Rehydrate the plan cache from disk
    for fp, plan_body in project.load_plans().items():
        try:
            from aqir import AQIRPlan
            plans.put(fp, AQIRPlan.model_validate(plan_body))
        except Exception:
            continue

    executor = Executor(cache=ResultCache())
    # Register every file sitting in the project's uploads folder as a DuckDB
    # view. The executor sniffs CSV vs Parquet vs JSON by extension.
    for upload in sorted(project.uploads_dir.glob("*")):
        if upload.is_file() and upload.suffix.lower() in {".csv", ".tsv", ".parquet", ".json", ".ndjson"}:
            try:
                executor.register_table(upload.stem, str(upload))
            except Exception:
                continue
    # Also register versioned parquet files when they exist (future pipeline)
    for pq in project.parquet_dir.glob("*.parquet"):
        try:
            executor.register_table(pq.stem, str(pq))
        except Exception:
            continue

    llm = build_client(settings.provider, settings.api_key, settings.model, settings.ollama_base_url)
    return ProjectRuntime(
        project=project,
        slice_=slice_,
        synonyms=synonyms,
        plans=plans,
        templates=TemplateIndex(),
        grammar=GrammarParser(),
        promoter=Promoter(),
        executor=executor,
        meter=Meter(),
        llm=llm,
    )


def _catalog_to_slice(catalog_json: dict) -> CatalogSlice:
    """Build an AQIR CatalogSlice from the project's catalog.json."""
    metrics: dict[str, MetricDef] = {}
    dimensions: dict[str, DimensionDef] = {}
    joins: dict[tuple[str, str], str] = {}
    many_sides: set[str] = set()

    # Auto-derive metrics (SUM of numeric columns with amount-like names,
    # COUNT DISTINCT of id columns) and dimensions (string/categorical).
    for tname, t in catalog_json.get("tables", {}).items():
        for cname, c in t.get("columns", {}).items():
            ctype = c.get("type", "string")
            if ctype in ("number", "integer", "currency", "percent"):
                metric_name = cname
                metrics[metric_name] = MetricDef(
                    metric_name, f"SUM({tname}.{cname})", tname, "number"
                )
            elif ctype == "id":
                m = f"{tname}_count"
                metrics[m] = MetricDef(m, f"COUNT(DISTINCT {tname}.{cname})", tname, "number")
            elif ctype in ("string", "boolean", "date", "datetime"):
                dimensions[cname] = DimensionDef(cname, f"{tname}.{cname}", tname, ctype)

    for r in catalog_json.get("relationships", []):
        key = (r["left_table"], r["right_table"])
        joins[key] = f'ON {r["left_table"]}.{r["left_column"]} = {r["right_table"]}.{r["right_column"]}'
        if r.get("cardinality") == "one_to_many":
            many_sides.add(r["right_table"])
    return CatalogSlice(metrics=metrics, dimensions=dimensions, joins=joins, many_sides=many_sides)


def _load_synonyms(project: Project, catalog_json: dict) -> SynonymIndex:
    idx = SynonymIndex()
    # Register canonical names from the catalog so grammar/templates can resolve
    for _tname, t in catalog_json.get("tables", {}).items():
        for cname in t.get("columns", {}):
            idx.add_name(cname, [])
    # Load user-defined / learned synonyms from disk
    if project.synonyms_path.exists():
        try:
            import json
            data = json.loads(project.synonyms_path.read_text())
            for canonical, syns in data.items():
                idx.add_name(canonical, list(syns))
        except Exception:
            pass
    return idx


RUNTIME = Runtime()
