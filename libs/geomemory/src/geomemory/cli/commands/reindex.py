"""geomemory reindex — migration from legacy txtai/ST indexes to ONNX sqlite-vec."""

from __future__ import annotations

import json
from pathlib import Path

import click

from geomemory.core.workspace import GeoMemory


@click.command("reindex")
@click.option("--workspace", "-w", type=click.Path(exists=True, file_okay=False), default=".", help="Workspace path")
@click.option("--collection", "-c", default=None, help="Collection id (optional, rebuilds all if omitted)")
@click.option("--provider", default="onnx", type=click.Choice(["onnx", "hashing", "llamacpp"]), help="Embedding provider")
@click.option("--model", "model_name", default="Xenova/all-MiniLM-L6-v2", help="ONNX model id (Xenova/all-MiniLM-L6-v2)")
@click.option("--space", default=None, help="Target space_id (defaults to provider's space_id)")
@click.option("--force/--no-force", default=True, help="Force rebuild even if no legacy markers")
def reindex(
    workspace: str,
    collection: str | None,
    provider: str,
    model_name: str,
    space: str | None,
    force: bool,
) -> None:
    """Re-embed all segments via the ONNX provider into sqlite-vec.

    Migrates legacy txtai / sentence-transformers ``text.st.*`` indexes to
    ``text.onnx.<model>.v1`` (default Xenova/all-MiniLM-L6-v2 quantized,
    384-d, mean-pool L2). Data stays local; no network unless ``offline=false``
    and the model is not cached (then hub auto-downloads).
    """
    ws_path = Path(workspace)
    # WorkspaceSettings override: we temporarily patch settings for the rebuild
    ws = GeoMemory.open(ws_path)
    try:
        # Resolve target space_id
        if space is None:
            from geomemory.embeddings.provider import ONNXEmbeddingProvider

            prov = ONNXEmbeddingProvider(model_name)
            space = prov.space_id

        # If collection filter given, rebuild only that collection's segments
        # IndexService currently rebuilds all; we filter by deleting other embeddings?
        # Simplest: rebuild all, but warn if collection specified and not filtered.
        if collection:
            click.echo(f"Note: collection filter '{collection}' — rebuilding all segments (collection-scoped rebuild not yet isolated).", err=True)

        # Detect legacy manifest
        manifest_path = ws_path / "indexes" / space / "manifest.json"
        legacy_detected = False
        if ws_path.joinpath("indexes").exists():
            for child in (ws_path / "indexes").iterdir():
                if child.name.startswith("text.st.") or child.name.startswith("text.txtai"):
                    legacy_detected = True
                    click.echo(f"Legacy space detected: {child.name} → will migrate to {space}", err=True)
                # Also inspect manifest model_id
                man = child / "manifest.json"
                if man.is_file():
                    try:
                        data = json.loads(man.read_text())
                        mid = data.get("model_id", "")
                        if "sentence-transformers" in mid and "Xenova" not in mid:
                            click.echo(f"Legacy model {mid} in {child.name}", err=True)
                    except Exception:
                        pass

        if not legacy_detected and not force:
            click.echo("No legacy txtai/ST markers found — nothing to do (use --force to rebuild).")
            return

        # Patch settings for this rebuild (provider/model)
        # Persist so future searches use the new provider without extra flags
        from geomemory.core.config import load_settings, save_settings

        settings_path = ws_path / "workspace.yaml"
        if settings_path.is_file():
            settings = load_settings(settings_path)
            settings.embedding_provider = provider  # type: ignore[assignment]
            settings.onnx_model_name = model_name  # type: ignore[assignment]
            # Normalize vector backend to sqlite-vec
            settings.vector_backend = "sqlite-vec"  # type: ignore[assignment]
            save_settings(settings_path, settings)
            # Reopen to pick up new provider
            ws.close()
            ws = GeoMemory.open(ws_path)

        result = ws.rebuild_index(space)
        click.echo(json.dumps(result, indent=2))
        click.echo(f"Reindexed {result.get('indexed', 0)} segments into {space} (provider={provider} model={model_name})")
        click.echo("Migration complete — pipdeptree should now show no torch/txtai (unless [vision]).")
    finally:
        try:
            ws.close()
        except Exception:
            pass
