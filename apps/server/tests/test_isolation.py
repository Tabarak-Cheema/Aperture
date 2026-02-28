"""Architectural isolation tests.

The render / query / insight services must NEVER import llm_gateway. Enforced
here so CI catches drift the moment a developer merges it.
"""
from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_MODULE_PREFIX = "llm_gateway"
RENDER_PATH_DIRS = [
    Path("services/query"),
    Path("services/insight"),
    Path("apps/web"),
]


def _imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_no_render_path_imports_llm_gateway() -> None:
    root = Path(__file__).resolve().parents[3]
    offenders: list[str] = []
    for d in RENDER_PATH_DIRS:
        base = root / d
        if not base.exists():
            continue
        for py in base.rglob("*.py"):
            if py.name == "test_isolation.py":
                continue
            for imp in _imports(py):
                if imp == FORBIDDEN_MODULE_PREFIX or imp.startswith(FORBIDDEN_MODULE_PREFIX + "."):
                    offenders.append(f"{py.relative_to(root)}: imports {imp}")
                    break
    assert not offenders, "render-path files import llm_gateway:\n" + "\n".join(offenders)
