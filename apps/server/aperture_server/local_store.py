"""Local-first state store.

Everything lives under ``~/.aperture`` on the user's machine:

    ~/.aperture/
      settings.json              # provider, api key, theme
      projects.json              # { current, projects: [{id, name, path, createdAt}] }
      projects/
        <slug>/
          project.json
          data/uploads/          # original uploaded files
          data/parquet/          # versioned parquet (future)
          catalog.json           # table + column definitions
          plans.json             # plan cache (T0)
          history.jsonl          # Q&A log
          synonyms.json          # learned synonyms

No database. No accounts. Switching projects is a fast JSON load.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

APERTURE_HOME = Path(os.environ.get("APERTURE_HOME", str(Path.home() / ".aperture")))
APERTURE_HOME.mkdir(parents=True, exist_ok=True)

SETTINGS_PATH = APERTURE_HOME / "settings.json"
PROJECTS_INDEX = APERTURE_HOME / "projects.json"
PROJECTS_ROOT = APERTURE_HOME / "projects"
PROJECTS_ROOT.mkdir(exist_ok=True)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip().lower()).strip("-")
    return s or "project"


def _atomic_write(path: Path, data: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(path)


# -----------------------------------------------------------------------------
# Settings
# -----------------------------------------------------------------------------
@dataclass
class Settings:
    """Global user settings."""

    provider: str = "ollama"           # ollama | groq | openai | together | fireworks | mock
    api_key: str = ""                  # not needed for ollama
    model: str = ""                    # provider default if empty
    ollama_base_url: str = "http://localhost:11434/v1"
    theme: str = "system"              # light | dark | system
    density: str = "comfortable"       # comfortable | compact

    @classmethod
    def load(cls) -> Settings:
        if SETTINGS_PATH.exists():
            try:
                data = json.loads(SETTINGS_PATH.read_text())
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception:
                pass
        return cls()

    def save(self) -> None:
        _atomic_write(SETTINGS_PATH, json.dumps(asdict(self), indent=2))

    def public_dict(self) -> dict[str, Any]:
        """Settings safe to send to the browser — strips the api key."""
        d = asdict(self)
        d["api_key_set"] = bool(self.api_key)
        d["api_key"] = ""
        return d


# -----------------------------------------------------------------------------
# Projects
# -----------------------------------------------------------------------------
@dataclass
class ProjectMeta:
    id: str
    name: str
    slug: str
    path: str
    created_at: str
    last_opened_at: str = ""


@dataclass
class ProjectsIndex:
    current_id: str | None = None
    projects: list[ProjectMeta] = field(default_factory=list)

    @classmethod
    def load(cls) -> ProjectsIndex:
        if PROJECTS_INDEX.exists():
            try:
                raw = json.loads(PROJECTS_INDEX.read_text())
                return cls(
                    current_id=raw.get("current_id"),
                    projects=[ProjectMeta(**p) for p in raw.get("projects", [])],
                )
            except Exception:
                pass
        return cls()

    def save(self) -> None:
        _atomic_write(
            PROJECTS_INDEX,
            json.dumps(
                {"current_id": self.current_id, "projects": [asdict(p) for p in self.projects]},
                indent=2,
            ),
        )

    def by_id(self, pid: str) -> ProjectMeta | None:
        return next((p for p in self.projects if p.id == pid), None)


class Project:
    """A local project folder with a tiny file-backed state model."""

    def __init__(self, meta: ProjectMeta):
        self.meta = meta
        self.root = Path(meta.path)
        self.data_dir = self.root / "data"
        self.uploads_dir = self.data_dir / "uploads"
        self.parquet_dir = self.data_dir / "parquet"
        self.catalog_path = self.root / "catalog.json"
        self.plans_path = self.root / "plans.json"
        self.history_path = self.root / "history.jsonl"
        self.synonyms_path = self.root / "synonyms.json"
        self._lock = threading.Lock()
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        for d in (self.root, self.data_dir, self.uploads_dir, self.parquet_dir):
            d.mkdir(parents=True, exist_ok=True)
        if not (self.root / "project.json").exists():
            _atomic_write(self.root / "project.json", json.dumps(asdict(self.meta), indent=2))

    # ---- Catalog ----
    def load_catalog(self) -> dict[str, Any]:
        if self.catalog_path.exists():
            try:
                return json.loads(self.catalog_path.read_text())
            except Exception:
                return {"version": 1, "tables": {}, "relationships": []}
        return {"version": 1, "tables": {}, "relationships": []}

    def save_catalog(self, catalog: dict[str, Any]) -> None:
        with self._lock:
            _atomic_write(self.catalog_path, json.dumps(catalog, indent=2))

    # ---- Plan cache ----
    def load_plans(self) -> dict[str, Any]:
        if self.plans_path.exists():
            try:
                return json.loads(self.plans_path.read_text())
            except Exception:
                return {}
        return {}

    def save_plans(self, plans: dict[str, Any]) -> None:
        with self._lock:
            _atomic_write(self.plans_path, json.dumps(plans, indent=2))

    # ---- History ----
    def append_history(self, record: dict[str, Any]) -> None:
        with self._lock, self.history_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record) + "\n")

    def read_history(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        lines = self.history_path.read_text().splitlines()
        out: list[dict[str, Any]] = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out


class ProjectStore:
    """Façade over the on-disk projects index + current project."""

    def __init__(self):
        self.index = ProjectsIndex.load()

    # ---- Index ops ----
    def list(self) -> list[ProjectMeta]:
        return list(self.index.projects)

    def get(self, pid: str) -> Project | None:
        meta = self.index.by_id(pid)
        return Project(meta) if meta else None

    def current(self) -> Project | None:
        if not self.index.current_id:
            return None
        return self.get(self.index.current_id)

    def switch(self, pid: str) -> Project:
        meta = self.index.by_id(pid)
        if not meta:
            raise KeyError(f"no project with id {pid}")
        self.index.current_id = pid
        meta.last_opened_at = datetime.utcnow().isoformat() + "Z"
        self.index.save()
        return Project(meta)

    def create(self, name: str, path: str | None = None) -> Project:
        pid = uuid.uuid4().hex[:12]
        slug = _slug(name)
        # Ensure slug uniqueness
        taken = {p.slug for p in self.index.projects}
        base = slug
        i = 2
        while slug in taken:
            slug = f"{base}-{i}"
            i += 1
        root = Path(path).expanduser().resolve() if path else PROJECTS_ROOT / slug
        meta = ProjectMeta(
            id=pid, name=name, slug=slug, path=str(root),
            created_at=datetime.utcnow().isoformat() + "Z",
            last_opened_at=datetime.utcnow().isoformat() + "Z",
        )
        self.index.projects.append(meta)
        self.index.current_id = pid
        self.index.save()
        return Project(meta)

    def rename(self, pid: str, new_name: str) -> ProjectMeta:
        meta = self.index.by_id(pid)
        if not meta:
            raise KeyError(pid)
        meta.name = new_name
        self.index.save()
        return meta

    def delete(self, pid: str, remove_files: bool = False) -> None:
        meta = self.index.by_id(pid)
        if not meta:
            return
        if remove_files:
            shutil.rmtree(meta.path, ignore_errors=True)
        self.index.projects = [p for p in self.index.projects if p.id != pid]
        if self.index.current_id == pid:
            self.index.current_id = self.index.projects[0].id if self.index.projects else None
        self.index.save()
