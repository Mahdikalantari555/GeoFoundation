"""geomemory init command."""

from __future__ import annotations

import click

from geomemory.core.models import WorkspaceConfig
from geomemory.core.workspace import GeoMemory


@click.command("init")
@click.argument("path", type=click.Path())
@click.option("--name", default="GeoMemory Workspace", help="Workspace name")
@click.option("--offline/--no-offline", default=True, help="Enable offline mode")
@click.option("--language", type=click.Choice(["en", "fa"]), default=None, help="Default language")
def init(path: str, name: str, offline: bool, language: str | None) -> None:
    """Create a new GeoMemory workspace at PATH."""
    config = WorkspaceConfig(name=name, offline=offline, language=language)
    ws = GeoMemory.create(path, config=config)
    click.echo(f"Created workspace at {path}")
    click.echo(f"  name: {ws.settings.name}")
    click.echo(f"  offline: {ws.settings.offline}")
    ws.close()
