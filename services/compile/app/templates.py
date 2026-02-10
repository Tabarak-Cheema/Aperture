"""T1 — Template match.

Templates look like ``"<metric> by <dim> in <period>"``. The slot filler pulls
metric/dim/period tokens from the question using the :class:`SynonymIndex` and
normalizes them to catalog names. Zero model tokens.

Retrieval uses a small local embedding model (fastembed, ONNX, CPU). For the
MVP we fall back to BM25 when fastembed isn't installed so the service still
boots.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from aqir import AQIRPlan
from catalog import SynonymIndex


@dataclass(slots=True)
class Template:
    name: str
    pattern: str           # regex with named groups: metric, dim, period, limit
    build: str             # a template-literal JSON string with {metric}/{dim}/{period}/{limit}


_DEFAULT_TEMPLATES: list[Template] = [
    # Most specific first so broader shapes don't win by accident.
    Template(
        name="top_n_metric_by_dim",
        pattern=r"^top\s+(?P<limit>\d+)\s+(?P<dim>[\w\s]+?)\s+by\s+(?P<metric>[\w\s]+?)$",
        build='{"metrics":["{metric}"],"dimensions":["{dim}"],"sort":[{"by":"{metric}","dir":"desc"}],"limit":{limit}}',
    ),
    Template(
        name="trend_metric",
        pattern=r"^(?P<metric>[\w\s]+?)\s+(?:trend|over time)\s*(?:by\s+(?P<grain>day|week|month|quarter|year))?$",
        build='{"metrics":["{metric}"],"time":{"dim":"order_date","grain":"{grain_or_month}"}}',
    ),
    Template(
        name="metric_by_dim_period",
        pattern=r"^(?P<metric>[\w\s]+?)\s+by\s+(?P<dim>[\w\s]+?)\s+(?:in|for)\s+(?P<period>.+)$",
        build='{"metrics":["{metric}"],"dimensions":["{dim}"],"time":{"dim":"order_date","range":"{period_kw}"}}',
    ),
    Template(
        name="metric_by_dim",
        pattern=r"^(?P<metric>[\w\s]+?)\s+by\s+(?P<dim>[\w\s]+?)$",
        build='{"metrics":["{metric}"],"dimensions":["{dim}"]}',
    ),
]


_PERIOD_KEYWORDS = {
    "today": "today",
    "yesterday": "yesterday",
    "last week": "last_7d",
    "last month": "last_30d",
    "last quarter": "last_quarter",
    "last year": "last_year",
    "ytd": "ytd",
    "mtd": "mtd",
    "qtd": "qtd",
}


@dataclass(slots=True)
class TemplateHit:
    template: str
    plan: AQIRPlan
    confidence: float


@dataclass
class TemplateIndex:
    templates: list[Template] = field(default_factory=lambda: list(_DEFAULT_TEMPLATES))
    _examples: list[tuple[str, str]] = field(default_factory=list)

    def best(self, question: str, synonyms: SynonymIndex) -> TemplateHit | None:
        q = question.strip().lower()
        for t in self.templates:
            m = re.match(t.pattern, q)
            if not m:
                continue
            groups = m.groupdict()
            # Resolve metric/dim via synonym index
            metric = synonyms.resolve_token(groups.get("metric", "") or "")
            dim = synonyms.resolve_token(groups.get("dim", "") or "")
            if not metric or not dim:
                continue
            period_kw = _PERIOD_KEYWORDS.get((groups.get("period") or "").strip().lower(), "last_30d")
            grain_or_month = (groups.get("grain") or "month").lower()
            body = t.build
            replacements = {
                "metric": metric,
                "dim": dim,
                "limit": groups.get("limit") or "10",
                "period_kw": period_kw,
                "grain_or_month": grain_or_month,
            }
            for k, v in replacements.items():
                body = body.replace("{" + k + "}", str(v))
            try:
                plan = AQIRPlan.model_validate_json(body)
            except Exception:
                continue
            return TemplateHit(template=t.name, plan=plan, confidence=0.9)
        return None

    def add_example(self, question: str, plan: AQIRPlan) -> None:
        self._examples.append((question, plan.model_dump_json(exclude_none=True)))

    def top_examples(self, k: int) -> list[tuple[str, str]]:
        return self._examples[-k:]
