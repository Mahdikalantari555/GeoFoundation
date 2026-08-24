"""geomemory doctor command — environment and workspace diagnostics."""

from __future__ import annotations

import click

from geomemory.services.doctor import doctor_environment, doctor_workspace, doctor_workspace_open


@click.command("doctor")
@click.option("--workspace", "-w", type=click.Path(), default=".", help="Workspace path to check")
def doctor(workspace: str) -> None:
    """Diagnose the environment and an optional workspace."""
    env = doctor_environment()
    click.echo("=== GeoMemory environment ===")
    click.echo(f"Python: {env['python_version'].split()[0]} (ok={env['python_ok']})")
    for name, ok in env["core_deps"].items():
        click.echo(f"  core {name}: {'✅' if ok else '❌'}")
    for name, ok in env["optional_deps"].items():
        click.echo(f"  opt  {name}: {'✅' if ok else '❌'}")

    click.echo(f"\n=== Workspace: {workspace} ===")
    ws = doctor_workspace(workspace)
    for name, value in ws["checks"].items():
        if isinstance(value, bool):
            click.echo(f"  {name}: {'✅' if value else '❌'}")
        else:
            click.echo(f"  {name}: {value}")
    if ws["ok"]:
        click.echo("  workspace structural checks passed")
    else:
        click.echo("  workspace structural checks FAILED")

    opened = doctor_workspace_open(workspace)
    for name, value in opened["checks"].items():
        if isinstance(value, bool):
            click.echo(f"  {name}: {'✅' if value else '❌'}")
        else:
            click.echo(f"  {name}: {value}")
    click.echo("  workspace API round-trip: " + ("✅ passed" if opened["ok"] else "❌ failed"))
