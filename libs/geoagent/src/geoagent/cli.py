"""GeoAgent CLI: init, chat, ingest, search, tools."""

from __future__ import annotations

import json
from pathlib import Path

import click

from geoagent import __version__, plugins
from geoagent import playbooks as pb_mod
from geoagent.agent import AgentCore, build_backend
from geoagent.config import (
    AgentSettings,
    load_settings,
    write_default_config,
)
from geoagent.registry import Registry, RunContext
from geoagent.store import Store
from geoagent.tools import advisor_tools, cli_runner, gis_tools, memory_tools


def _bootstrap(config: str) -> tuple[AgentSettings, Store]:
    global _SETTINGS
    settings = load_settings(config)
    _SETTINGS = settings
    settings.workspace.mkdir(parents=True, exist_ok=True)
    store = Store(settings.workspace / "agent.db")
    return settings, store


def _registry_with_memory(settings: AgentSettings | None = None) -> Registry:
    global _SETTINGS
    _SETTINGS = settings or _SETTINGS
    registry = Registry()
    memory_tools.register(registry)
    gis_tools.register(registry)
    advisor_tools.register(registry)
    if _SETTINGS is not None:
        cli_runner.register_from_config(registry, _SETTINGS)
        plugins.load_plugins(registry, _SETTINGS.workspace)
        pb_mod.register_playbook_tools(registry, _SETTINGS)
    return registry


_SETTINGS: AgentSettings | None = None


@click.group()
@click.version_option(__version__)
def main() -> None:
    """GeoAgent — agent harness over GeoMemory."""


@main.command()
@click.argument("directory", type=click.Path(), default=".")
def init(directory: str) -> None:
    """Create an agent workspace with a default agent.yaml."""
    root = Path(directory).resolve() / "geoagent-workspace"
    (root / "runs").mkdir(parents=True, exist_ok=True)
    (root / "playbooks").mkdir(parents=True, exist_ok=True)
    (root / "plugins").mkdir(parents=True, exist_ok=True)
    config_path = root.parent / "agent.yaml"
    if not config_path.exists():
        write_default_config(config_path)
    Store(root / "agent.db").close()
    click.echo(f"workspace: {root}")
    click.echo(f"config:    {config_path}")
    click.echo("next: set memory_workspace + provider in agent.yaml, then `geoagent chat`")


@main.command()
@click.option("--config", "config", default="agent.yaml", show_default=True)
def tools(config: str) -> None:
    """List registered tools."""
    settings = None
    if Path(config).exists():
        settings = load_settings(config)
    for line in _registry_with_memory(settings).manifest_lines():
        click.echo(line)


@main.command()
@click.argument("query")
@click.option("--config", "config", default="agent.yaml", show_default=True)
@click.option("--top-k", default=5, show_default=True)
@click.option("--bbox", default=None, help="w,s,e,n lon/lat")
@click.option("--date-range", default=None, help="ISO start,end")
def search(query: str, config: str, top_k: int, bbox: str | None, date_range: str | None) -> None:
    """Run geo_search directly against the knowledge base."""
    settings, store = _bootstrap(config)
    registry = _registry_with_memory()
    args: dict = {"query": query, "top_k": top_k}
    if bbox:
        args["bbox"] = [float(x) for x in bbox.split(",")]
    if date_range:
        parts = [p.strip() for p in date_range.split(",")]
        args["date_range"] = parts
    ctx = RunContext(
        store=store,
        workspace_dir=settings.workspace,
        sandbox_roots=settings.resolve_sandbox_roots(),
        settings=settings,
    )
    result = registry.call("geo_search", args, ctx)
    click.echo(json.dumps(result.value or {"error": result.error}, ensure_ascii=False, indent=2))
    store.close()


@main.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--collection", required=True)
@click.option("--config", "config", default="agent.yaml", show_default=True)
def ingest(source: str, collection: str, config: str) -> None:
    """Ingest a file via geo_ingest directly."""
    settings, store = _bootstrap(config)
    registry = _registry_with_memory()
    ctx = RunContext(
        store=store,
        workspace_dir=settings.workspace,
        sandbox_roots=settings.resolve_sandbox_roots(),
        settings=settings,
    )
    result = registry.call("geo_ingest", {"source_path": source, "collection": collection}, ctx)
    click.echo(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    store.close()


@main.command()
@click.option("--config", "config", default="agent.yaml", show_default=True)
@click.option("--conversation", default=None, help="existing conversation id")
def chat(config: str, conversation: str | None) -> None:
    """Interactive chat REPL."""
    settings, store = _bootstrap(config)
    try:
        backend = build_backend(settings)
    except Exception as exc:  # noqa: BLE001 - CLI boundary: show setup hints
        click.echo(f"LLM setup problem: {exc}")
        store.close()
        return
    core = AgentCore(settings, backend, _registry_with_memory(), store)
    conv_id = conversation or core.new_conversation("chat")

    click.echo(f"GeoAgent chat — conversation {conv_id} (/new, /tools, /exit)")
    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user:
            continue
        if user == "/exit":
            break
        if user == "/new":
            conv_id = core.new_conversation("chat")
            click.echo(f"new conversation {conv_id}")
            continue
        if user == "/tools":
            for line in core.registry.manifest_lines():
                click.echo(line)
            continue
        answer = core.chat(conv_id, user, on_event=lambda e: click.echo(e))
        click.echo(f"\nagent> {answer}\n")
    store.close()


@main.group()
def playbook() -> None:
    """Manage saved tool sequences (fast-path playbooks)."""


@playbook.command("list")
@click.option("--config", "config", default="agent.yaml", show_default=True)
def playbook_list(config: str) -> None:
    """List playbooks and validity against the live registry."""
    settings = load_settings(config)
    registry = _registry_with_memory(settings)
    found = pb_mod.load_playbooks(settings.workspace)
    if not found:
        click.echo("no playbooks (create <workspace>/playbooks/<name>.md)")
        return
    for pb in found:
        problems = pb_mod.validate_playbook(pb, registry)
        flag = "" if not problems else f"  INVALID: {'; '.join(problems[:2])}"
        click.echo(f"- {pb.name} v{pb.version} ({len(pb.steps)} steps){flag}")


@playbook.command("show")
@click.argument("name")
@click.option("--config", "config", default="agent.yaml", show_default=True)
def playbook_show(name: str, config: str) -> None:
    """Print a playbook file."""
    settings = load_settings(config)
    path = settings.workspace / "playbooks" / f"{name.replace('-', '_')}.md"
    if not path.exists():
        click.echo(f"not found: {path}")
        return
    click.echo(path.read_text(encoding="utf-8"))


@playbook.command("run")
@click.argument("name")
@click.option("--config", "config", default="agent.yaml", show_default=True)
@click.option("--param", "params", multiple=True, help="key=value, repeatable")
def playbook_run(name: str, config: str, params: tuple[str, ...]) -> None:
    """Execute a playbook directly (no LLM involved)."""
    import json as _json

    settings = load_settings(config)
    store = Store(settings.workspace / "agent.db")
    registry = _registry_with_memory(settings)
    ctx = RunContext(
        store=store,
        workspace_dir=settings.workspace,
        sandbox_roots=settings.resolve_sandbox_roots(),
        settings=settings,
        max_tool_calls=settings.budgets.max_tool_calls,
    )
    args: dict = {}
    for p in params:
        k, _, v = p.partition("=")
        try:
            v = _json.loads(v)
        except _json.JSONDecodeError:
            pass
        args[k] = v
    result = registry.call(f"pb_{name.replace('-', '_')}", args, ctx)
    click.echo(_json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    store.close()


@playbook.command("save")
@click.argument("name")
@click.option("--config", "config", default="agent.yaml", show_default=True)
@click.option("--conversation", required=True, help="conversation id to convert")
def playbook_save(name: str, config: str, conversation: str) -> None:
    """Draft a playbook from a past conversation via the LLM."""
    settings = load_settings(config)
    store = Store(settings.workspace / "agent.db")
    backend = build_backend(settings)

    sequence = [
        row
        for row in store.conn.execute(
            "SELECT tool, args_json FROM tool_run WHERE conversation_id=? ORDER BY created_at",
            (conversation,),
        ).fetchall()
    ]
    if not sequence:
        click.echo("no tool runs in that conversation")
        store.close()
        return
    text = pb_mod.draft_playbook_text(
        backend,
        name,
        [{"tool": r["tool"], "args": _json_loads_safe(r["args_json"])} for r in sequence],
    )
    path = pb_mod.save_playbook(settings.workspace, name, text)
    click.echo(f"saved {path}")
    click.echo(text)
    store.close()


def _json_loads_safe(raw: str) -> dict:
    import json

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


if __name__ == "__main__":
    main()
