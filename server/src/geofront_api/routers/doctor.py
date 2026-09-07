from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from geomemory.services.doctor import (
    doctor_embedding,
    doctor_environment,
    doctor_llm_provider,
    doctor_workspace,
)

from ..state import get_default_workspace_root, get_state

router = APIRouter(prefix="/doctor", tags=["doctor"])


def _flatten_checks(raw: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    """Split geomemory workspace_report checks into flat primitives vs nested diagnostics."""
    checks: dict[str, object] = {}
    diagnostics: dict[str, object] = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            diagnostics[k] = v
        elif isinstance(v, (bool, str, int, float)) or v is None:
            checks[k] = v
        else:
            # Fallback: treat any other complex type as diagnostics to keep checks flat
            diagnostics[k] = v
    return checks, diagnostics


def _normalize_llm_probe(raw: dict[str, object]) -> dict[str, object]:
    """Return flat LLM probe shape: provider, key_env, key_configured, base_url, model_id, context_window."""
    # geomemory returns keys: provider, model_id, api_base_url, key_env, key_set, context_window
    # gateway fallback returns: provider, key_env, key_configured, base_url, model_id
    return {
        "provider": raw.get("provider"),
        "key_env": raw.get("key_env"),
        "key_configured": bool(raw.get("key_configured") if "key_configured" in raw else raw.get("key_set")),
        "base_url": raw.get("base_url") if "base_url" in raw else raw.get("api_base_url"),
        "model_id": raw.get("model_id"),
        "context_window": raw.get("context_window"),
    }


@router.get("")
async def doctor() -> dict[str, object]:
    """Environment + active-workspace diagnostics (no secret values).

    Runs even with no open workspace — environment checks never require one,
    and the workspace probe reports a graceful "closed" status instead of 409.
    """
    state = get_state()
    environment = doctor_environment()

    resolved_workspace_root = str(get_default_workspace_root().resolve())
    if not state.is_open:
        return {
            "environment": environment,
            "workspace": {"ok": False, "closed": True, "checks": {"status": "no workspace open"}},
            "workspace_open": {"ok": False, "closed": True, "checks": {"open": False}},
            "embedding": {"hub_count": 0, "downloaded": 0, "active_backend": None, "active_model": None},
            "diagnostics": {
                "llm": _normalize_llm_probe(state.llm_health()),
                "qdrant": {"client_installed": False},
                "pdf_parser": {},
                "vision": {},
                "embedding": {"hub_count": 0, "downloaded": 0, "active_backend": None},
                "sqlite_vec": {"installed": False, "loadable": False},
            },
            "resolved_workspace_root": resolved_workspace_root,
        }

    ws = state.require_workspace()
    workspace_report_raw = doctor_workspace(ws.path)
    # Split workspace_report checks into flat primitives and nested diagnostics
    raw_checks = workspace_report_raw.get("checks", {})  # type: ignore[assignment]
    if isinstance(raw_checks, dict):
        flat_checks, nested_diags = _flatten_checks(raw_checks)  # type: ignore[arg-type]
    else:
        flat_checks, nested_diags = {}, {}
    workspace = {
        "ok": workspace_report_raw.get("ok", False),
        "checks": flat_checks,
        "workspace_path": workspace_report_raw.get("workspace_path"),
    }
    # Preserve closed flag if present
    if workspace_report_raw.get("closed") is not None:
        workspace["closed"] = workspace_report_raw["closed"]

    try:
        await run_in_threadpool(ws.list_collections)
        collections_ok = True
        collections_err: str | None = None
    except Exception as exc:  # noqa: BLE001 - report failure
        collections_ok = False
        collections_err = str(exc)

    try:
        await run_in_threadpool(ws.stats)
        stats_ok = True
    except Exception:  # noqa: BLE001 - report failure
        stats_ok = False

    workspace_open = {
        "ok": collections_ok and stats_ok,
        "checks": {
            "open_list_collections": collections_ok,
            "stats": stats_ok,
        },
    }
    if collections_err is not None:
        workspace_open["checks"]["open_error"] = collections_err

    embedding = await run_in_threadpool(doctor_embedding, ws.settings)
    # embedding report may already contain sqlite_vec details; ensure diagnostics shape
    llm_diag = nested_diags.get("llm") or doctor_llm_provider(ws.settings)
    qdrant_diag = nested_diags.get("qdrant") or {}
    pdf_diag = nested_diags.get("pdf_parser") or {}
    vision_diag = nested_diags.get("vision") or {}
    # Merge any embedding nested diag with explicit embedding report
    embedding_diag = nested_diags.get("embedding") or {}
    if isinstance(embedding_diag, dict) and isinstance(embedding, dict):
        # Prefer explicit embedding report for canonical fields
        merged_embedding = {**embedding_diag, **embedding}  # type: ignore[dict-item]
    else:
        merged_embedding = embedding

    # Extract sqlite_vec info from embedding report if present
    sqlite_vec_diag: dict[str, object] = {}
    if isinstance(merged_embedding, dict):
        # doctor_embedding adds sqlite_vec keys inside? Normalize to diagnostics.sqlite_vec
        if "sqlite_vec" in merged_embedding:  # type: ignore[operator]
            sv = merged_embedding["sqlite_vec"]  # type: ignore[index]
            if isinstance(sv, dict):
                sqlite_vec_diag = sv  # type: ignore[assignment]
        else:
            # Build from top-level keys if doctor_embedding emitted flat fields
            sqlite_vec_diag = {
                "installed": bool(merged_embedding.get("sqlite_vec_installed", False) or merged_embedding.get("vec_installed", False)),
                "loadable": bool(merged_embedding.get("sqlite_vec_loadable", False) or merged_embedding.get("vec_loadable", False)),
                "version": merged_embedding.get("sqlite_vec_version") or merged_embedding.get("vec_version"),
            }
            # Fallback try import detection
            if not sqlite_vec_diag["installed"]:
                try:
                    import sqlite_vec  # type: ignore[import-not-found]

                    sqlite_vec_diag = {
                        "installed": True,
                        "loadable": True,
                        "version": getattr(sqlite_vec, "__version__", "unknown"),
                    }
                except ImportError:
                    sqlite_vec_diag = {"installed": False, "loadable": False, "version": None}

    diagnostics = {
        "llm": _normalize_llm_probe(llm_diag if isinstance(llm_diag, dict) else {}),  # type: ignore[arg-type]
        "qdrant": qdrant_diag,
        "pdf_parser": pdf_diag,
        "vision": vision_diag,
        "embedding": merged_embedding,
        "sqlite_vec": sqlite_vec_diag,
    }

    return {
        "environment": environment,
        "workspace": workspace,
        "workspace_open": workspace_open,
        "embedding": merged_embedding,
        "diagnostics": diagnostics,
        "resolved_workspace_root": resolved_workspace_root,
    }


@router.get("/llm")
async def doctor_llm() -> dict[str, object]:
    """Probe the configured LLM provider configuration (no secret values).

    Works without an open workspace by falling back to the gateway's default
    LLM health (env var + provider defaults). Returns flat typed model.
    """
    state = get_state()
    if state.is_open:
        raw = doctor_llm_provider(state.require_workspace().settings)
        return _normalize_llm_probe(raw)  # type: ignore[arg-type]
    return _normalize_llm_probe(state.llm_health())  # type: ignore[arg-type]
