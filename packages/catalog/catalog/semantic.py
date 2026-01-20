"""Semantic layer: user-editable metric and dimension definitions.

Stored as versioned YAML on disk; the compile service reads them into
:class:`SemanticLayer` and hands slices to the AQIR compiler.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml


@dataclass
class MetricYAML:
    name: str
    expr: str
    base_table: str
    type: str = "number"
    description: str = ""
    synonyms: list[str] = field(default_factory=list)


@dataclass
class DimensionYAML:
    name: str
    expr: str
    base_table: str
    type: str = "string"
    description: str = ""
    synonyms: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SemanticLayer:
    version: int = 1
    metrics: dict[str, MetricYAML] = field(default_factory=dict)
    dimensions: dict[str, DimensionYAML] = field(default_factory=dict)

    def all_synonyms(self) -> dict[str, str]:
        """Flatten synonyms into a lookup table: synonym -> canonical name."""
        out: dict[str, str] = {}
        for m in self.metrics.values():
            for s in m.synonyms:
                out[s.lower()] = m.name
            out[m.name.lower()] = m.name
        for d in self.dimensions.values():
            for s in d.synonyms:
                out[s.lower()] = d.name
            out[d.name.lower()] = d.name
        return out


def load_semantic_yaml(path: str | Path) -> SemanticLayer:
    raw = yaml.safe_load(Path(path).read_text())
    layer = SemanticLayer(version=raw.get("version", 1))
    for m in raw.get("metrics", []):
        layer.metrics[m["name"]] = MetricYAML(**m)
    for d in raw.get("dimensions", []):
        layer.dimensions[d["name"]] = DimensionYAML(**d)
    return layer


def dump_semantic_yaml(layer: SemanticLayer, path: str | Path) -> None:
    body = {
        "version": layer.version,
        "metrics": [asdict(m) for m in layer.metrics.values()],
        "dimensions": [asdict(d) for d in layer.dimensions.values()],
    }
    Path(path).write_text(yaml.safe_dump(body, sort_keys=False))
