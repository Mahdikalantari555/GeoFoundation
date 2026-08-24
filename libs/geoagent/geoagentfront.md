# GeoAgent — Frontend-Usable Features

What the GeoAgent backend exposes today. Every item below works via Python
API today; an HTTP bridge (`/chat`, `/tools/:name/call`, `/files/*`) would map
1:1 onto these with zero new logic.

## 1. Chat / Agent
| Feature | What it gives the UI |
|---|---|
| Multi-turn agent chat | LLM tool-calling loop over any OpenAI-compatible endpoint; user sends text, agent answers using tools |
| Conversation history | Persisted sessions (list + full turn timeline) → sidebar + transcript views |
| Citations `[S#]` | Answers cite knowledge-base sources; render as clickable source chips |
| Tool-run audit | Every tool call logged w/ status, duration, args, cache-hit → "what did the agent do" inspector |
| Budget guardrails | Call/wall-clock limits per turn → deterministic failure messages |

## 2. Knowledge Base (GeoMemory)
| Feature | Inputs | Outputs |
|---|---|---|
| Ingest documents/rasters | file path, collection | asset_id, segment_count |
| Hybrid semantic search | query, collections, bbox, date range, sensor | ranked hits w/ text + source locator → citation chips |
| Collection management | name | list / create collections |

## 3. Geospatial Analysis Tools
| Tool | Input | Output (renderable) |
|---|---|---|
| Spectral indices | multiband GeoTIFF, band map | NDVI/EVI/NDWI/SAVI GeoTIFFs (+ custom formulas) |
| Reclassify | index TIF + rules | classified TIF + histogram |
| Polygonize | classified TIF | **GeoJSON FeatureCollection** (direct map-layer) + area % per class |
| Symbology | GeoJSON + field + palette/breaks | **map.png** choropleth |
| Zonal stats | raster + polygons | **stats.csv** per-polygon means/min/max |

All outputs are workspace files under `<ws>/runs/…` with sha256 artifact hashes — servable as static assets.

## 4. Advisor (Agriculture)
| Feature | Input | Output |
|---|---|---|
| Farm registry | farms GeoJSON (farm_id, crop) | farm lookup by id or bbox |
| Farm stress report | farm_id + dated rasters | **report.md** (trend table, worst date, [S#] sources), **stats.csv**, **map.png**; auto-filed into `reports` collection |
| Recommendation evidence | topic (irrigation/fertilization/spraying) + stress state | structured evidence pack: stress label + expert-rule hits ([S#]-citable) + explicit data gaps (→ abstain UI state) |

## 5. Extensibility (backend-driven UI)
| Feature | Frontend relevance |
|---|---|
| Playbooks (YAML+MD workflows) | Register as callable tools; run multi-step pipelines in one click, zero intermediate LLM latency; params = simple form schema |
| Playbook drafting from a past conversation | "Save this workflow" button → generated playbook file |
| Workspace plugins / entry-point tools | New tools appear automatically in tool manifest → dynamic tool catalog UI |
| Declarative CLI tools | External tools surfaced as typed JSON-schema tools |
| Deterministic cache | Repeated identical calls return instantly (cache-hit badge) |

## 6. Natural UI screens this supports
1. **Chat** — transcript, citations, tool-run timeline
2. **Knowledge** — collections browser, ingest form, search console
3. **Maps** — PNG viewer + GeoJSON overlay layers from any tool/report
4. **Farms** — farm list → report cards (trend sparkline from stats.csv, map thumb)
5. **Workflows** — playbook list/run with param forms; save-from-conversation
6. **Tools** — live manifest of all registered tools (built-in + plugins)

## Gap
No HTTP server yet. Proposed thin FastAPI bridge:
`POST /chat` (SSE) · `GET /conversations[/:id]` · `GET /tools` ·
`POST /tools/:name/call` · `POST /playbooks/save` · `GET /files/*` (sandboxed artifacts).
