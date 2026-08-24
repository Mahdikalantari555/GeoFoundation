# GeoAgent — openspec project context

## Why

GeoMemory is a local-first **memory library** (ingest / search / grounded QA /
feedback) with no agent surface. GeoAgent fills the gap: a lightweight,
tool-calling **agent framework for remote-sensing workflows**, built *on top of*
GeoMemory — not a fork of it.

Thesis framing (see `../Ideas/`): case study = sugarcane stress monitoring in
Khuzestan; study axes = stress detection, stress discrimination, plant health
from imagery; method = frugal ML + continual learning. GeoAgent is the
engineering product that makes those axes operable through an agent.

## What it is

- A Python package `geoagent` + CLI `geoagent`.
- An agent harness (cloud LLM via OpenAI-compatible API, function calling).
- A tool registry: every capability is a typed tool with JSON-Schema params.
- Tool families:
  1. **memory tools** — wrap the GeoMemory public facade (`geomemory` root exports only);
  2. **GIS tools** — reclassify, polygonize, symbology, zonal stats, spectral indices;
  3. **CLI runner** — wrap any external Python CLI (e.g. the researcher's own
     stress-analysis lib: date + bbox args) as a tool;
  4. **advisor tools** — farm report + irrigation/fertilizer/spraying recommendations;
- Playbooks (SKILL.md-style): saved tool sequences so repeated tasks run fast
  without the LLM re-reading code every turn.
- MCP server (later phase): expose the same registry to external agents.

## Constraints (frugal)

- **LLM: cloud-first.** Default backend = any **OpenAI-compatible** provider
  (`base_url` + `api_key` + `model` in `agent.yaml` or env). Easily swappable.
  **Local LLM support is out of scope for the first versions** — the
  `LLMBackend` protocol keeps the seam open, but no local runtime ships in v0.x.
- Frugal ML constraint still holds for the *models under study* (small tabular
  classifiers on laptop hardware); frugality does NOT apply to the agent LLM.
- Heavy deps (rasterio/geopandas/matplotlib) stay behind lazy imports and
  optional extras (`[rs]`, `[all]`).
- GeoMemory workspace itself stays local/offline; the only network traffic is
  LLM API calls explicitly configured by the user. Query/context content leaves
  the machine by design — this trade-off is documented, not hidden.

## Invariants

1. **GeoMemory access = public API only.** `geoagent` imports nothing deeper
   than `import geomemory` root exports (`GeoMemory`, models, exceptions).
   Mirrors the dashboard invariant in GeoMemory AGENTS.md.
2. **Never write GeoMemory's DB directly.** All state flows through facade calls
   (`ingest`, `search`, `ask`, `record_feedback`, `export_dataset`, ...).
   Agent-own state lives in a separate `agent.db` inside its workspace dir.
3. **Provenance chain preserved.** Any answer/report produced by the agent must
   carry citations or artifact paths traceable back to inputs (asset hashes).
4. **Every tool call is audited.** Persisted ToolRun record: tool name, args
   hash, status, latency, artifacts, error.
5. **Abstention over hallucination.** If evidence or data is missing, the agent
   abstains explicitly (inherits GeoMemory QA semantics).
6. **Deterministic where possible.** Same input hash + same args → same cached
   result; randomness confined to the LLM step.

## Personas

| Persona | Need |
|---|---|
| Supervisor (advisor) | Open dashboard, see farm state, chat for irrigation/fertilization/spraying guidance |
| GIS/RS researcher | One-shot natural-language → CLI/pipeline execution ("stress map for farm 12 from 1403/07/01 to 1403/09/30") |
| Developer | Add a tool or playbook without touching the harness |

## Roadmap (maps to thesis weeks)

| Phase | Weeks | Scope | Specs exercised |
|---|---|---|---|
| P1 core | 1–2 | Harness + registry + memory tools | agent-core, tool-registry, memory-tools |
| P2 EO/GIS | 3–5 | gis-tools + cli-runner | gis-tools, cli-runner |
| P3 advisor | 9–10 | report/recommend tools + dashboard chat + playbooks | advisor, playbooks |
| P4 plumbing | 9–12 | feedback/review/export/run-logs only (ML deferred) | learning-loop |
| P5 expose | 13–14 | MCP server expose | mcp-interface |

## Decisions (interview, 2026-08)

1. **Own thin harness** — GeoAgent is self-written (~loop + registry + sessions,
   direct OpenAI-compatible calls). nanobot/Hermes/fx are design references,
   never dependencies.
2. **Cloud-first LLM** — OpenAI-compatible provider default via config/env;
   local LLM runtimes out of scope for first versions.
3. **Agent-driven RAG** — grounded generation happens in agent-core
   (`geo_search` → pack → cite `[S#]`); no `geo_ask` tool; GeoMemory needs no
   LLM configuration.
4. **Native GIS tools first** — rasterio/geopandas wrappers in-repo; MCP client
   deferred (MCP *expose* stays P5).
5. **Agent project first** — Active Learning / incremental-model placement
   deferred; specs cover data plumbing contract only.
6. **GeoMemory = public API consumer** — facade imports only; `agent.db`
   separate from `geomemory.db`.

## Glossary

- **Tool**: callable + JSON-Schema params registered in the registry.
- **Playbook**: versioned SKILL.md describing trigger phrases and a templated
  sequence of tool calls.
- **ToolRun**: audit row of one tool execution.
- **Artifact**: file output of a tool (tif/geojson/png/csv/md), stored under the
  agent workspace and referenced by path + sha256.
