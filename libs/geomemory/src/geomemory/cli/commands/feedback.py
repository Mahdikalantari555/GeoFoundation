"""geomemory feedback command."""

from __future__ import annotations

import click

from geomemory.core.workspace import GeoMemory


@click.group("feedback")
def feedback() -> None:
    """Manage feedback and dataset exports."""


@feedback.command("export")
@click.option("--workspace", "-w", type=click.Path(), default=".", help="Workspace path")
@click.option("--type", "task_type", type=click.Choice(["rag_eval", "qa_eval", "sft", "preference"]), required=True)
@click.option("--output", type=click.Path(), default=".", help="Output directory")
def export(workspace: str, task_type: str, output: str) -> None:
    """Export reviewed feedback as a dataset."""
    ws = GeoMemory.open(workspace)
    try:
        path = ws.export_dataset(task_type, output)
        click.echo(f"Exported dataset to {path}")
    finally:
        ws.close()


@feedback.command("review")
@click.option("--workspace", "-w", type=click.Path(), default=".", help="Workspace path")
@click.option("--pending", is_flag=True, help="List pending review items")
def review(workspace: str, pending: bool) -> None:
    """List the review queue."""
    ws = GeoMemory.open(workspace)
    try:
        queue = ws.get_review_queue()
        if not queue:
            click.echo("Review queue is empty.")
            return
        for item in queue:
            click.echo(f"{item.id} [{item.task_type}] state={item.review_state}")
    finally:
        ws.close()
