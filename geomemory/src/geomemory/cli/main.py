"""Click-based CLI entry point for GeoMemory."""

from __future__ import annotations

import click

from geomemory import __version__


@click.group()
@click.version_option(__version__)
def cli() -> None:
    """GeoMemory — multimodal, spatiotemporal knowledge engine."""


def _import_commands() -> None:
    """Register command modules lazily to avoid importing heavy deps at start."""
    from geomemory.cli.commands import (
        app,
        chat,
        doctor,
        eval_cmd,
        feedback,
        index,
        ingest,
        init,
        inspect,
        search,
    )

    cli.add_command(init.init)
    cli.add_command(ingest.ingest)
    cli.add_command(index.index_cmd)
    cli.add_command(search.search)
    cli.add_command(chat.chat)
    cli.add_command(inspect.inspect)
    cli.add_command(eval_cmd.eval_cmd)
    cli.add_command(feedback.feedback)
    cli.add_command(doctor.doctor)
    cli.add_command(app.app)


_import_commands()
