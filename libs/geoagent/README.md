# GeoAgent

Lightweight agent framework for remote-sensing workflows, built on the
[GeoMemory](../GeoMemory/) public API. Local-first, offline-by-default,
CPU-friendly (frugal AI).

- Specs: [`openspec/project.md`](openspec/project.md) + `openspec/specs/*/spec.md`
- Status: spec phase (no code yet)
- Thesis context: `../Ideas/`

```
User ──chat──▶ Agent Core (GGUF LLM, planner)
                 │ tool calling
                 ▼
              Tool Registry ──▶ memory tools ──▶ geomemory public API
                            ├─▶ gis tools (rasterio/geopandas, lazy)
                            ├─▶ CLI runner (external libs)
                            └─▶ advisor tools (report/recommend)
                 │
                 ▼
            Playbooks (SKILL.md) — replay common workflows fast
```
