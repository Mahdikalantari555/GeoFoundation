"""Environment diagnostics for GeoMemory.

Implements the P0 ``geomemory doctor`` command: verifies the Python
environment, optional dependency availability, and workspace integrity.
"""

from __future__ import annotations

import importlib
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from geomemory.core.models import WorkspaceSettings

OPTIONAL_DEPS: list[tuple[str, str, str]] = [
    ("txtai", "txtai", "dense/sparse retrieval backend"),
    ("llama_cpp_python", "llama_cpp", "local GGUF LLM + embedding inference"),
    ("sentence_transformers", "sentence_transformers",
     "sentence-transformers dense text embeddings"),
    ("qdrant_client", "qdrant_client", "Qdrant server-mode vector backend"),
    ("rasterio", "rasterio", "GeoTIFF reading"),
    ("shapely", "shapely", "geometry operations"),
    ("geopandas", "geopandas", "vector data reading"),
    ("PIL", "Pillow", "image previews/thumbnails"),
    ("fitz", "PyMuPDF", "PDF parsing (fallback)"),
    ("opendataloader_pdf", "opendataloader-pdf", "high-quality PDF parsing (optional)"),
    ("docx", "python-docx", "DOCX parsing"),
    ("streamlit", "streamlit", "reference dashboard"),
    ("torch", "torch", "OLMoEarth vision embeddings"),
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

            loaded = load_settings(settings_path)
            settings_ok = True
            report["checks"]["llm_provider"] = doctor_llm_provider(loaded)
            report["checks"]["qdrant"] = doctor_qdrant(loaded)
            report["checks"]["pdf_parser"] = doctor_pdf_parser(loaded)
            report["checks"]["vision"] = doctor_vision(loaded)
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
    report["checks"]["java_available"] = shutil.which("java") is not None

    return report


def doctor_llm_provider(settings: WorkspaceSettings) -> dict[str, Any]:
    """Report the resolved LLM provider configuration (no secret values)."""
    key_env = settings.llm_api_key_env
    return {
        "provider": settings.llm_provider,
        "model_id": settings.llm_model_id,
        "api_base_url": settings.llm_api_base_url,
        "key_env": key_env,
        "key_set": bool(os.environ.get(key_env)),
        "context_window": settings.llm_context_window,
    }


def doctor_qdrant(settings: WorkspaceSettings) -> dict[str, Any]:
    """Report Qdrant client availability and, when configured, server reachability."""
    client_installed = True
    try:
        importlib.import_module("qdrant_client")
    except ImportError:
        client_installed = False

    info: dict[str, Any] = {"client_installed": client_installed, "url": settings.qdrant_url}

    if settings.qdrant_url and client_installed:
        try:
            from qdrant_client import QdrantClient  # type: ignore[import-not-found]

            client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
            client.get_collections()
            info["reachable"] = True
        except Exception as exc:  # noqa: BLE001
            info["reachable"] = False
            info["error"] = str(exc)
    return info


def doctor_pdf_parser(settings: WorkspaceSettings) -> dict[str, Any]:
    """Report the resolved PDF parser preference."""
    try:
        importlib.import_module("opendataloader_pdf")
        odl_installed = True
    except ImportError:
        odl_installed = False
    java = shutil.which("java") is not None
    if settings.pdf_parser == "opendataloader":
        resolved = "opendataloader"
    elif settings.pdf_parser == "pymupdf":
        resolved = "pymupdf"
    else:
        resolved = "opendataloader" if (odl_installed and java) else "pymupdf"
    return {
        "pdf_parser_setting": settings.pdf_parser,
        "resolved": resolved,
        "opendataloader_installed": odl_installed,
        "java_available": java,
    }


def doctor_vision(settings: WorkspaceSettings) -> dict[str, Any]:
    """Report vision model (torch + checkpoint) availability."""
    try:
        importlib.import_module("torch")
        torch_installed = True
    except ImportError:
        torch_installed = False

    vision_path = settings.vision_path
    # vision_path may be a directory (config.json + weights.pth) or a direct
    # .pth file (per the vision-embedding spec).
    if vision_path:
        vp = Path(vision_path)
        checkpoint_exists = (
            vp.is_file()
            or (vp.is_dir() and (vp / "weights.pth").is_file())
        )
    else:
        checkpoint_exists = False
    return {
        "torch_installed": torch_installed,
        "vision_path": vision_path,
        "vision_path_configured": vision_path is not None,
        "checkpoint_exists": checkpoint_exists,
    }


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
