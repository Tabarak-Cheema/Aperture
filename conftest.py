"""Root conftest.

Pytest rootdir anchor so that tests collected from each service/package
directory resolve their imports against the monorepo layout declared in
pyproject.toml.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent

for sub in (
    "packages/aqir", "packages/catalog", "packages/llm_gateway",
    "services/compile", "services/query", "services/ingest", "services/insight",
    "apps/server",
    ".",
):
    sys.path.insert(0, str(ROOT / sub))
