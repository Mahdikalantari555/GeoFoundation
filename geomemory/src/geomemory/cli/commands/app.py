"""AI app command — launch the Streamlit dashboard."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click


@click.command("app")
@click.option(
    "--workspace",
    "-w",
    type=click.Path(),
    default=None,
    help="Workspace path (default: GEOMEMORY_DASHBOARD_ROOT or ./workspace)",
)
def app(workspace: str | None) -> None:
    """Launch the Streamlit reference dashboard."""
    try:
        from streamlit.web import cli as stcli
    except ImportError as err:
        raise click.ClickException(
            "streamlit is not installed. Install it with: pip install 'geomemory[ui]'"
        ) from err

    app_path = Path(__file__).resolve().parents[3] / "apps" / "dashboard" / "app.py"
    if not app_path.is_file():
        raise click.ClickException(f"dashboard not found at {app_path}")
    if workspace:
        os.environ["GEOMEMORY_DASHBOARD_ROOT"] = workspace
    sys.argv = ["streamlit", "run", str(app_path)]
    stcli.main()
