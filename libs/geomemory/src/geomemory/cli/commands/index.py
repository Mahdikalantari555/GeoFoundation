"""geomemory index command."""

from __future__ import annotations

import click

from geomemory.core.workspace import GeoMemory


@click.group("index")
def index_cmd() -> None:
    """Manage retrieval indexes."""


@index_cmd.command("build")
@click.option("--workspace", "-w", type=click.Path(), default=".", help="Workspace path")
@click.option("--space", default="text.nomic.v1", help="Embedding space id")
def build(workspace: str, space: str) -> None:
    """Build the index for a space."""
    ws = GeoMemory.open(workspace)
    try:
        ws.build_index(space)
        click.echo(f"Built index for space: {space}")
    finally:
        ws.close()


@index_cmd.command("rebuild")
@click.option("--workspace", "-w", type=click.Path(), default=".", help="Workspace path")
@click.option("--space", default="text.nomic.v1", help="Embedding space id")
def rebuild(workspace: str, space: str) -> None:
    """Rebuild the index for a space from SQLite source."""
    ws = GeoMemory.open(workspace)
    try:
        ws.rebuild_index(space)
        click.echo(f"Rebuilt index for space: {space}")
    finally:
        ws.close()


# Alias under `index reindex` for migration convenience: delegates to top-level reindex
@index_cmd.command("reindex")
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False), default=".", help="Workspace path")
@click.option("--collection", "-c", default=None, help="Collection id (optional)")
@click.option("--provider", default="onnx", type=click.Choice(["onnx", "hashing", "llamacpp"]), help="Embedding provider")
@click.option("--model", "model_name", default="Xenova/all-MiniLM-L6-v2", help="ONNX model id")
@click.option("--space", default=None, help="Target space_id (defaults to provider's space_id)")
@click.option("--force/--no-force", default=True, help="Force rebuild")
def reindex_alias(
    workspace: str,
    collection: str | None,
    provider: str,
    model_name: str,
    space: str | None,
    force: bool,
) -> None:
    """Alias for `geomemory reindex` (migration to sqlite-vec)."""
    from geomemory.cli.commands.reindex import reindex as _reindex

    # Click's standalone callback is the function object; invoke directly
    ctx = click.get_current_context()
    ctx.invoke(_reindex, workspace=workspace, collection=collection, provider=provider, model_name=model_name, space=space, force=force)
