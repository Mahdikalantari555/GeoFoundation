"""geomemory inspect command."""

from __future__ import annotations

import click

from geomemory.core.workspace import GeoMemory


@click.command("inspect")
@click.argument("asset_id")
@click.option("--workspace", "-w", type=click.Path(), default=".", help="Workspace path")
def inspect(asset_id: str, workspace: str) -> None:
    """Inspect an asset's full detail."""
    ws = GeoMemory.open(workspace)
    try:
        detail = ws.inspect(asset_id)
        click.echo(f"Asset: {detail.asset.id}")
        click.echo(f"  kind: {detail.asset.kind}")
        click.echo(f"  title: {detail.asset.title}")
        if detail.revision:
            click.echo(f"  revision: {detail.revision.id}")
            click.echo(f"  hash: {detail.revision.hash}")
            click.echo(f"  mime: {detail.revision.mime_type}")
        click.echo(f"  segments: {len(detail.segments)}")
        for seg in detail.segments[:5]:
            click.echo(f"    - [{seg.segment_type}] {seg.text[:80]}")
    finally:
        ws.close()