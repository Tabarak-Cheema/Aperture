# PyInstaller spec for Aperture.exe (and Aperture on macOS / Linux).
#
# Build with:
#     pyinstaller apps/desktop/aperture.spec
#
# Produces a single-file executable under dist/ that bundles:
#   - Python runtime
#   - FastAPI + uvicorn + duckdb + sqlglot + pydantic + pandas + numpy + scipy
#   - The pre-built React web app (apps/web/dist, must exist)
#
# The user double-clicks the exe and their default browser opens to the app.

from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = Path(SPECPATH).resolve().parent.parent  # repo root
WEB_DIST = ROOT / "apps" / "web" / "dist"

if not WEB_DIST.is_dir():
    raise SystemExit(
        "apps/web/dist is missing. Run `npm run build` in apps/web/ first "
        "(the build-desktop script does this for you)."
    )

datas = [
    (str(WEB_DIST), "apps/web/dist"),
]

hiddenimports = (
    collect_submodules("pydantic")
    + collect_submodules("uvicorn")
    + collect_submodules("duckdb")
    + collect_submodules("sqlglot")
    + ["apps.server.aperture_server.main",
       "apps.server.aperture_server.context",
       "apps.server.aperture_server.local_store",
       "apps.server.aperture_server.providers",
       "services.compile.app.cascade",
       "services.compile.app.grammar",
       "services.compile.app.normalizer",
       "services.compile.app.templates",
       "services.compile.app.promoter",
       "services.query.app.executor",
       "services.ingest.app.sniffer",
       "services.ingest.app.profiler",
       "services.ingest.app.relationships",
       "services.insight.app.anomaly",
       "services.insight.app.correlation",
       "services.insight.app.diffing",
       "aqir", "aqir.compiler", "aqir.schema", "aqir.validator", "aqir.jsonschema",
       "catalog", "catalog.models", "catalog.semantic", "catalog.synonyms",
       "llm_gateway", "llm_gateway.client", "llm_gateway.metering", "llm_gateway.prompt",
       ]
)

block_cipher = None

a = Analysis(
    [str(ROOT / "apps" / "server" / "aperture_server" / "desktop.py")],
    pathex=[
        str(ROOT),
        str(ROOT / "packages" / "aqir"),
        str(ROOT / "packages" / "catalog"),
        str(ROOT / "packages" / "llm_gateway"),
        str(ROOT / "services" / "compile"),
        str(ROOT / "services" / "query"),
        str(ROOT / "services" / "ingest"),
        str(ROOT / "services" / "insight"),
        str(ROOT / "apps" / "server"),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Aperture",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,    # True would show a console window on Windows
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
