"""geomemory search command."""

from __future__ import annotations

import json

import click

from geomemory.core.workspace import GeoMemory


@click.command("search")
@click.argument("query")
@click.option("--workspace", "-w", type=click.Path(), default=".", help="Workspace path")
@click.option("--mode", type=click.Choice(["sparse", "dense", "hybrid"]), default="hybrid")
@click.option("--top-k", type=int, default=20)
@click.option("--top-n", type=int, default=5)
@click.option("--collection", multiple=True, help="Collection id filter (repeatable)")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["table", "json", "markdown"]),
    default="table",
    help="Output format",
)
def search(
    query: str,
    workspace: str,
    mode: str,
    top_k: int,
    top_n: int,
    collection: tuple[str, ...],
    fmt: str,
) -> None:
    """Search the workspace."""
    ws = GeoMemory.open(workspace)
    try:
        result = ws.search(
            query,
            mode=mode,
            top_k=top_k,
            top_n=top_n,
            collections=list(collection) or None,
        )
        if fmt == "json":
            payload = {
                "query": result.query,
                "mode": mode,
                "total_hits": result.total_hits,
                "latency_ms": result.latency_ms,
                "retrieval_run_id": result.retrieval_run_id,
                "hits": [
                    {
                        "id": h.id,
                        "score": h.score,
                        "sparse_score": h.sparse_score,
                        "dense_score": h.dense_score,
                        "text": h.text,
                        "locator": h.locator,
                        "segment_type": h.metadata.get("segment_type"),
                    }
                    for h in result.hits
                ],
            }
            click.echo(json.dumps(payload, indent=2, default=str))
            return

        click.echo(f"Query: {result.query}")
        click.echo(f"Mode: {mode} | Hits: {result.total_hits} | Latency: {result.latency_ms}ms")
        click.echo(f"Run: {result.retrieval_run_id}")
        if fmt == "markdown":
            click.echo("\n| # | score | type | snippet |")
            click.echo("|---|-------|------|---------|")
            for i, hit in enumerate(result.hits, start=1):
                seg = (hit.text or "")[:80].replace("|", "\\|").replace("\n", " ")
                stype = hit.metadata.get("segment_type", "?")
                click.echo(f"| {i} | {hit.score:.4f} | {stype} | {seg} |")
            return
        for i, hit in enumerate(result.hits, start=1):
            click.echo(f"\n[{i}] score={hit.score:.4f}")
            click.echo(f"    {hit.text[:200]}")
            click.echo(f"    locator: {hit.locator}")
    finally:
        ws.close()
