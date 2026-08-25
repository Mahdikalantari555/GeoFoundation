"""geomemory eval command."""

from __future__ import annotations

import click

from geomemory.core.workspace import GeoMemory


@click.group("eval")
def eval_cmd() -> None:
    """Run benchmarks and evaluations."""


@eval_cmd.command("run")
@click.argument("benchmark_path", type=click.Path(exists=True))
@click.option("--workspace", "-w", type=click.Path(), default=".", help="Workspace path")
@click.option("--config", type=click.Path(), default=None, help="Benchmark config JSON")
def run(benchmark_path: str, workspace: str, config: str | None) -> None:
    """Run a benchmark from a JSONL file."""
    ws = GeoMemory.open(workspace)
    try:
        result = ws.run_benchmark(benchmark_path, config)
        click.echo(f"Benchmark: {result.name}")
        click.echo(f"  metrics: {result.metrics}")
    finally:
        ws.close()
