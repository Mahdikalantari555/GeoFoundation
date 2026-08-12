"""Environment diagnostics for GeoMemory.

Implements the P0 ``geomemory doctor`` command: verifies the Python
environment, optional dependency availability, and workspace integrity.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

OPTIONAL_DEPS: list[tuple[str, str, str]] = [
    ("txtai", "txtai", "dense/sparse retrieval backend"),
    ("llama_cpp_python", "llama_cpp", "local GGUF LLM + embedding inference"),
    ("rasterio", "rasterio", "GeoTIFF reading"),
    ("shapely", "shapely", "geometry operations"),
    ("geopandas", "geopandas", "vector data reading"),
    ("PIL", "Pillow", "image previews/thumbnails"),
    ("fitz", "PyMuPDF", "PDF parsing"),
    ("docx", "python-docx", "DOCX parsing"),
    ("streamlit", "streamlit", "reference dashboard"),
]

CORE_DEPS: list[tuple[str, str]] = [
    ("pydantic", "pydantic"),
    ("numpy", "numpy"),
    ("click", "click"),
    ("yaml", "yaml"),
]


def check_optional_deps() -> dict[str, bool]:
    """Return {module_name: installed} for all optional dependencies."""
    result: dict[str, bool] = {}
    for _, module, _ in OPTIONAL_DEPS:
        try:
            importlib.import_module(module)
            result[module] = True
        except ImportError:
            result[module] = False
    return result


def doctor_environment() -> dict[str, Any]:
    """Run environment checks and return a diagnostics report."""
    core: dict[str, bool] = {}
    for label, module in CORE_DEPS:
        try:
            importlib.import_module(module)
            core[label] = True
        except ImportError:
            core[label] = False

    optional = check_optional_deps()

    return {
        "python_version": sys.version,
        "python_ok": sys.version_info >= (3, 10),
        "core_deps": core,
        "core_ok": all(core.values()),
        "optional_deps": optional,
    }


def doctor_workspace(path: str | Path) -> dict[str, Any]:
    """Run integrity checks against a workspace directory."""
    target = Path(path)
    report: dict[str, Any] = {"workspace_path": str(target), "ok": True, "checks": {}}

    marker = target / ".geomemory"
    report["checks"]["marker_exists"] = marker.is_file()
    if not marker.is_file():
        report["ok"] = False
        report["checks"]["error"] = f"missing {marker.name} marker — not a GeoMemory workspace"
        return report

    settings_path = target / "workspace.yaml"
    settings_ok = False
    if settings_path.is_file():
        try:
            from geomemory.core.config import load_settings

            load_settings(settings_path)
            settings_ok = True
        except Exception:  # noqa: BLE001 - config parsing error
            settings_ok = False
    report["checks"]["settings_valid"] = settings_ok
    report["ok"] = report["ok"] and settings_ok

    db_path = target / "geomemory.db"
    report["checks"]["db_exists"] = db_path.is_file()
    if db_path.is_file():
        try:
            import sqlite3

            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA schema_version").fetchone()
            conn.close()
            report["checks"]["db_readable"] = True
        except Exception:  # noqa: BLE001
            report["checks"]["db_readable"] = False
            report["ok"] = False
    else:
        report["ok"] = False
        report["checks"]["db_error"] = "geomemory.db not created — run with an ingestion pipeline"

    report["checks"]["objects_dir"] = (target / "objects").is_dir()
    report["checks"]["indexes_dir"] = (target / "indexes").is_dir()

    return report


def doctor_workspace_open(path: str | Path) -> dict[str, Any]:
    """Open the workspace and verify the public API round-trips."""
    from geomemory import GeoMemory

    report: dict[str, Any] = {"ok": True, "checks": {}}
    try:
        ws = GeoMemory.open(path)
        try:
            ws.list_collections()
            report["checks"]["open_list_collections"] = True
            try:
                ws.stats()
                report["checks"]["stats"] = True
            except Exception:  # noqa: BLE001
                report["checks"]["stats"] = False
                report["ok"] = False
        finally:
            ws.close()
    except Exception as exc:  # noqa: BLE001 - report failure
        report["ok"] = False
        report["checks"]["open_error"] = str(exc)
    return report
