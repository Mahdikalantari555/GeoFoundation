"""GeoLearn tools for feedback training, adaptation, edge export, and model versioning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geoagent.registry import Registry, RunContext, ToolDefinition, ToolResult


def _get_pipeline(ctx: RunContext) -> Any:
    from geolearn.training_pipeline import TrainingPipeline

    geolearn_dir = ctx.workspace_dir / "geolearn"
    geomemory_workspace = ctx.workspace_dir
    return TrainingPipeline(geolearn_dir, geomemory_workspace)


def _get_store(ctx: RunContext) -> Any:
    from geolearn.persistence import ClassifierStore

    geolearn_dir = ctx.workspace_dir / "geolearn"
    return ClassifierStore(geolearn_dir)


def register(registry: Registry) -> None:
    @registry.register(
        ToolDefinition(
            name="geo_train_on_feedback",
            description="Train online classifier on accepted feedback candidate memory items.",
            params={
                "type": "object",
                "properties": {
                    "feedback_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of feedback IDs to train on",
                    },
                    "batch_size": {
                        "type": "integer",
                        "description": "Batch size for partial_fit",
                    },
                },
                "additionalProperties": False,
            },
        )
    )
    def geo_train_on_feedback(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        pipeline = _get_pipeline(ctx)
        feedback_ids = args.get("feedback_ids")
        batch_size = args.get("batch_size", 10)
        res = pipeline.train_on_feedback(feedback_ids=feedback_ids, batch_size=batch_size)
        return ToolResult(status="ok", value=res)

    @registry.register(
        ToolDefinition(
            name="geo_pending_training_count",
            description="Check how many accepted candidates are waiting for training.",
            params={"type": "object", "properties": {}, "additionalProperties": False},
        )
    )
    def geo_pending_training_count(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        pipeline = _get_pipeline(ctx)
        res = pipeline.pending_count()
        return ToolResult(status="ok", value=res)

    @registry.register(
        ToolDefinition(
            name="geo_select_region",
            description="Select or resolve region-specific classifier key.",
            params={
                "type": "object",
                "properties": {
                    "crop_type": {"type": "string"},
                    "region": {"type": "string"},
                    "sub_region": {"type": "string"},
                },
                "required": ["crop_type", "region"],
                "additionalProperties": False,
            },
        )
    )
    def geo_select_region(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        store = _get_store(ctx)
        crop = args["crop_type"]
        region = args["region"]
        sub_region = args.get("sub_region")
        key = store.get_or_create_key(crop, region, sub_region)
        return ToolResult(status="ok", value={"key": key})

    @registry.register(
        ToolDefinition(
            name="geo_get_user_settings",
            description="Get user preferences and confidence thresholds.",
            params={
                "type": "object",
                "properties": {"user_id": {"type": "string"}},
                "additionalProperties": False,
            },
        )
    )
    def geo_get_user_settings(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        from geolearn.user_settings import UserSettingsStore

        store = UserSettingsStore(ctx.workspace_dir / "geolearn")
        user_id = args.get("user_id", "default")
        settings = store.get_or_default(user_id)
        return ToolResult(
            status="ok",
            value={
                "user_id": settings.user_id,
                "confidence_threshold": settings.confidence_threshold,
                "preferred_classifier": settings.preferred_classifier,
                "auto_train_on_feedback": settings.auto_train_on_feedback,
                "updated_at": settings.updated_at,
            },
        )

    @registry.register(
        ToolDefinition(
            name="geo_update_user_settings",
            description="Update user preferences and confidence thresholds.",
            params={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "partial_settings": {"type": "object"},
                },
                "required": ["user_id", "partial_settings"],
                "additionalProperties": False,
            },
        )
    )
    def geo_update_user_settings(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        from geolearn.user_settings import UserSettingsStore

        store = UserSettingsStore(ctx.workspace_dir / "geolearn")
        user_id = args["user_id"]
        partial = args["partial_settings"]
        settings = store.update(user_id, **partial)
        return ToolResult(
            status="ok",
            value={
                "user_id": settings.user_id,
                "confidence_threshold": settings.confidence_threshold,
                "preferred_classifier": settings.preferred_classifier,
                "auto_train_on_feedback": settings.auto_train_on_feedback,
                "updated_at": settings.updated_at,
            },
        )

    @registry.register(
        ToolDefinition(
            name="geo_export_for_edge",
            description="Export classifier for standalone edge/CPU inference.",
            params={
                "type": "object",
                "properties": {
                    "output_dir": {"type": "string"},
                    "key": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["output_dir"],
                "additionalProperties": False,
            },
        )
    )
    def geo_export_for_edge(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        store = _get_store(ctx)
        key_list = args.get("key")
        key = (key_list[0], key_list[1]) if key_list and len(key_list) == 2 else ("unknown", "global")
        clf = store.get_classifier(key)
        out_dir = Path(args["output_dir"])
        out_dir = out_dir if out_dir.is_absolute() else ctx.workspace_dir / out_dir
        res = clf.export_for_edge(out_dir)
        return ToolResult(status="ok", value=res)

    @registry.register(
        ToolDefinition(
            name="geo_list_model_versions",
            description="List saved model versions for rollback recovery.",
            params={
                "type": "object",
                "properties": {
                    "key": {"type": "array", "items": {"type": "string"}},
                },
                "additionalProperties": False,
            },
        )
    )
    def geo_list_model_versions(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        from geolearn.versioning import ModelVersionManager

        mgr = ModelVersionManager(ctx.workspace_dir / "geolearn")
        key_list = args.get("key")
        key = (key_list[0], key_list[1]) if key_list and len(key_list) == 2 else None
        versions = mgr.list_versions(key)
        return ToolResult(
            status="ok",
            value=[
                {
                    "key": list(v.key),
                    "version": v.version,
                    "timestamp": v.timestamp,
                    "n_samples": v.n_samples,
                    "sha256": v.sha256,
                }
                for v in versions
            ],
        )

    @registry.register(
        ToolDefinition(
            name="geo_rollback_model",
            description="Rollback model to a previous version.",
            params={
                "type": "object",
                "properties": {
                    "key": {"type": "array", "items": {"type": "string"}},
                    "version": {"type": "integer"},
                },
                "required": ["key", "version"],
                "additionalProperties": False,
            },
        )
    )
    def geo_rollback_model(args: dict[str, Any], ctx: RunContext) -> ToolResult:
        from geolearn.versioning import ModelVersionManager

        mgr = ModelVersionManager(ctx.workspace_dir / "geolearn")
        key_list = args["key"]
        key = (key_list[0], key_list[1])
        version = args["version"]
        ok = mgr.rollback_to(key, version)
        return ToolResult(status="ok" if ok else "failed", value={"rolled_back": ok})
