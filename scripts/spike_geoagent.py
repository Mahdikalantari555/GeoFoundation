"""GeoAgent end-to-end spike: chat turn + one tool call.

Acceptance: go/no-go + scope note recorded in tasks/todo.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from geoagent.agent import AgentCore, build_backend
from geoagent.config import AgentSettings, load_settings
from geoagent.registry import Registry, RunContext
from geoagent.store import Store
from geoagent.tools import gis_tools, memory_tools


def main() -> int:
    config_path = sys.argv[1] if len(sys.argv) > 1 else "agent.yaml"
    if not Path(config_path).exists():
        print(f"config not found: {config_path}")
        return 1

    settings = load_settings(config_path)
    settings.workspace.mkdir(parents=True, exist_ok=True)
    store = Store(settings.workspace / "agent.db")

    registry = Registry()
    memory_tools.register(registry)
    gis_tools.register(registry)

    try:
        backend = build_backend(settings)
    except Exception as exc:
        print(f"LLM setup problem: {exc}")
        store.close()
        return 1

    core = AgentCore(settings, backend, registry, store)
    conv_id = core.new_conversation("spike")

    events: list[str] = []
    query = "What tools do you have for raster analysis?"
    print(f"you> {query}")
    answer = core.chat(conv_id, query, on_event=lambda e: events.append(e))

    print(f"\nagent> {answer}")
    print(f"\n--- events ({len(events)}) ---")
    for e in events:
        print(e)

    turns = store.turns(conv_id)
    tool_runs = [
        dict(r)
        for r in store.conn.execute(
            "SELECT tool, status FROM tool_run WHERE conversation_id=? ORDER BY created_at",
            (conv_id,),
        ).fetchall()
    ]
    print(f"\n--- turns: {len(turns)}, tool runs: {len(tool_runs)} ---")
    for tr in tool_runs:
        print(f"  {tr['tool']} -> {tr['status']}")

    store.close()
    print("\nSPIKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
