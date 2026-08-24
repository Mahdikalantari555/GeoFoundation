"""Tool registry: definitions, validation, sandbox, cache, audit, budgets."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from geoagent.store import Store

ToolFn = Callable[[dict[str, Any], "RunContext"], Any]

PATH_SUFFIXES = ("path", "file", "dir")


class ToolDefinition(BaseModel):
    name: str
    description: str
    params: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}, "additionalProperties": False}
    )
    returns: str = ""
    timeout_s: float = 60.0
    cacheable: bool = False


class ArtifactRef(BaseModel):
    path: str
    sha256: str | None = None


class ToolResult(BaseModel):
    status: str = "ok"  # ok | validation_error | failed | timeout | budget_refused
    value: Any = None
    error: str | None = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    from_cache: bool = False


@dataclass
class RunContext:
    store: Store
    workspace_dir: Path
    sandbox_roots: list[Path]
    settings: Any = None
    conversation_id: str | None = None
    turn_id: str | None = None
    max_tool_calls: int = 8
    deadline: float = field(default_factory=lambda: time.monotonic() + 120.0)
    calls_used: int = 0

    def budget_left(self) -> bool:
        return self.calls_used < self.max_tool_calls and time.monotonic() < self.deadline

    def budget_reason(self) -> str:
        if self.calls_used >= self.max_tool_calls:
            return f"max tool calls reached ({self.max_tool_calls})"
        return "wall-clock budget exhausted"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate(value: Any, schema: dict[str, Any], where: str) -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    if "enum" in schema and value not in schema["enum"]:
        return [f"{where}: must be one of {schema['enum']}"]
    if expected == "object":
        if not isinstance(value, dict):
            return [f"{where}: expected object"]
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{where}.{req}: required")
        props = schema.get("properties", {})
        for key, sub in value.items():
            if key in props:
                errors.extend(_validate(sub, props[key], f"{where}.{key}"))
    elif expected == "array":
        if not isinstance(value, list):
            return [f"{where}: expected array"]
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(value):
                errors.extend(_validate(item, item_schema, f"{where}[{i}]"))
    elif expected == "string":
        if not isinstance(value, str):
            errors.append(f"{where}: expected string")
    elif expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{where}: expected integer")
    elif expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{where}: expected number")
    elif expected == "boolean":
        if not isinstance(value, bool):
            errors.append(f"{where}: expected boolean")
    return errors


def _path_args(args: dict[str, Any]) -> list[str]:
    return [k for k, v in args.items() if isinstance(v, str) and k.endswith(PATH_SUFFIXES)]


def _check_sandbox(path_keys: list[str], args: dict[str, Any], roots: list[Path], workspace: Path) -> str | None:
    for key in path_keys:
        raw = args[key]
        p = Path(raw)
        resolved = (p if p.is_absolute() else workspace / p).resolve()
        if not any(resolved.is_relative_to(root) for root in roots):
            return (
                f"path '{raw}' is outside sandbox roots "
                f"({', '.join(str(r) for r in roots)})"
            )
    return None


def _cache_key(name: str, args: dict[str, Any], workspace: Path) -> tuple[str, bool]:
    payload: dict[str, Any] = {"n": name, "a": args}
    files_ok = True
    for key, val in args.items():
        if isinstance(val, str) and key.endswith(PATH_SUFFIXES):
            p = Path(val)
            p = p if p.is_absolute() else workspace / p
            if p.is_file():
                payload[key + "_sha"] = sha256_file(p)
            else:
                files_ok = False
    blob = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return digest, files_ok


class Registry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._fns: dict[str, ToolFn] = {}

    def register(self, definition: ToolDefinition) -> Callable[[ToolFn], ToolFn]:
        def deco(fn: ToolFn) -> ToolFn:
            if definition.name in self._tools:
                raise ValueError(
                    f"duplicate tool name '{definition.name}' "
                    f"(already registered with {self._fns[definition.name]})"
                )
            self._tools[definition.name] = definition
            self._fns[definition.name] = fn
            return fn

        return deco

    def names(self) -> list[str]:
        return sorted(self._tools)

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def openai_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.params,
                },
            }
            for t in sorted(self._tools.values(), key=lambda x: x.name)
        ]

    def manifest_lines(self) -> list[str]:
        return [f"- {t.name}: {t.description}" for t in sorted(self._tools.values(), key=lambda x: x.name)]

    def call(self, name: str, args: dict[str, Any], ctx: RunContext) -> ToolResult:
        started = time.perf_counter()
        tool = self._tools.get(name)
        if tool is None:
            result = ToolResult(status="validation_error", error=f"unknown tool: {name}")
            self._audit(ctx, name, args, "", result, started)
            return result
        if not ctx.budget_left():
            result = ToolResult(status="budget_refused", error=ctx.budget_reason())
            self._audit(ctx, name, args, "", result, started)
            return result

        errors = _validate(args, tool.params, "$")
        bad_paths = _path_args(args)
        sandbox_err = (
            _check_sandbox(bad_paths, args, ctx.sandbox_roots, ctx.workspace_dir)
            if bad_paths
            else None
        )
        if errors or sandbox_err:
            msg = "; ".join(errors + ([sandbox_err] if sandbox_err else []))
            result = ToolResult(status="validation_error", error=msg)
            self._audit(ctx, name, args, "", result, started)
            return result

        ctx.calls_used += 1

        cache_dir = ctx.workspace_dir / "runs" / "cache"
        key: str | None = None
        if tool.cacheable:
            key, _ = _cache_key(name, args, ctx.workspace_dir)
            cached = cache_dir / key / "result.json"
            if cached.is_file():
                try:
                    result = ToolResult.model_validate(json.loads(cached.read_text(encoding="utf-8")))
                    result.from_cache = True
                    self._audit(ctx, name, args, key, result, started)
                    return result
                except (json.JSONDecodeError, ValueError):
                    pass

        box: dict[str, Any] = {}

        def target() -> None:
            try:
                box["result"] = self._fns[name](args, ctx)
            except Exception as exc:  # noqa: BLE001 - tool boundary
                box["error"] = f"{type(exc).__name__}: {exc}"

        worker = threading.Thread(target=target, daemon=True)
        worker.start()
        worker.join(tool.timeout_s)
        if worker.is_alive():
            result = ToolResult(status="timeout", error=f"{name} exceeded {tool.timeout_s:.0f}s")
            self._audit(ctx, name, args, key or "", result, started)
            return result
        if "error" in box:
            result = ToolResult(status="failed", error=str(box["error"])[:2000])
            self._audit(ctx, name, args, key or "", result, started)
            return result

        raw = box.get("result")
        result = raw if isinstance(raw, ToolResult) else ToolResult(status="ok", value=raw)

        for art in result.artifacts:
            p = Path(art.path)
            if art.sha256 is None and p.is_file():
                art.sha256 = sha256_file(p)

        if key is not None and result.status == "ok":
            out_dir = cache_dir / key
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "result.json").write_text(result.model_dump_json(), encoding="utf-8")

        self._audit(ctx, name, args, key or "", result, started)
        return result

    def _audit(
        self,
        ctx: RunContext,
        name: str,
        args: dict[str, Any],
        cache_key: str,
        result: ToolResult,
        started: float,
    ) -> None:
        latency_ms = int((time.perf_counter() - started) * 1000)
        args_blob = json.dumps(args, sort_keys=True, default=str).encode("utf-8")
        args_hash = hashlib.sha256(cache_key.encode() + b"\x00" + args_blob).hexdigest()
        ctx.store.record_tool_run(
            conversation_id=ctx.conversation_id,
            turn_id=ctx.turn_id,
            tool=name,
            args=args,
            args_hash=args_hash,
            status=result.status,
            latency_ms=latency_ms,
            error=result.error,
            artifacts=[a.model_dump() for a in result.artifacts],
            from_cache=result.from_cache,
        )
