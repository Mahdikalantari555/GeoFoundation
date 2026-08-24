"""geomemory ingest command."""

from __future__ import annotations

import click

from geomemory.core.workspace import GeoMemory


@click.command("ingest")
@click.argument("source", type=click.Path(exists=True))
@click.option("--workspace", "-w", type=click.Path(), default=".", help="Workspace path")
@click.option("--collection", "-c", required=True, help="Collection name or id")
@click.option("--no-index", is_flag=True, help="Skip indexing after ingestion")
def ingest(source: str, workspace: str, collection: str, no_index: bool) -> None:
    """Ingest a file into a collection."""
    ws = GeoMemory.open(workspace)
    try:
        col = _resolve_collection(ws, collection)
        job = ws.ingest(source, collection_id=col.id, index_after=not no_index)
        click.echo(f"Job: {job.id} state={job.state}")
        click.echo(f"  result: {job.result}")
    finally:
        ws.close()


def _resolve_collection(ws, name_or_id: str):
    """Resolve a collection by id or name."""
    col = ws.get_collection(name_or_id)
    if col is not None:
        return col
    for c in ws.list_collections():
        if c.name == name_or_id:
            return c
    raise click.ClickException(f"Collection not found: {name_or_id}")