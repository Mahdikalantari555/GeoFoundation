"""Benchmark report rendering: JSON and Markdown."""

from __future__ import annotations

import json


def json_report(name: str, metrics: dict[str, dict[str, float]]) -> str:
    """Serialize metrics to a pretty JSON document."""
    return json.dumps({"name": name, "metrics": metrics}, indent=2, ensure_ascii=False)


def _fmt(value: float) -> str:
    """Format a metric value as a three-decimal string."""
    return f"{value:.3f}"


def markdown_report(name: str, metrics: dict[str, dict[str, float]]) -> str:
    """Render metrics as a Markdown table grouped by metric family."""
    lines = [f"# Benchmark: {name}", ""]
    for group, values in metrics.items():
        if not values:
            continue
        lines.append(f"## {group}")
        lines.append("")
        lines.append("| metric | value |")
        lines.append("| --- | --- |")
        for metric, value in values.items():
            lines.append(f"| {metric} | {_fmt(value)} |")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
