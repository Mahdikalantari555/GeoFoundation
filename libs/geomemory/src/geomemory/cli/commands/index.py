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