"""geomemory chat command."""

from __future__ import annotations

import click

from geomemory.core.workspace import GeoMemory


@click.command("chat")
@click.option("--workspace", "-w", type=click.Path(), default=".", help="Workspace path")
@click.option("--mode", type=click.Choice(["grounded_qa", "research", "code"]), default="grounded_qa")
def chat(workspace: str, mode: str) -> None:
    """Launch an interactive chat session."""
    ws = GeoMemory.open(workspace)
    try:
        click.echo("GeoMemory chat — type 'exit' to quit.")
        while True:
            question = click.prompt("You", default="")
            if question.strip().lower() in ("exit", "quit"):
                break
            answer = ws.ask(question, mode=mode)
            click.echo(f"\nGeoMemory: {answer.text}")
            if answer.abstained:
                click.echo(f"  (abstained: {answer.abstention_reason})")
            for citation in answer.citations:
                click.echo(f"  [cite] {citation.locator}")
            click.echo("")
    finally:
        ws.close()