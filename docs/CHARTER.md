# GeoFoundation — Charter

> What GeoFoundation is, what it is not, and the order in which it grows.
> Status: MSc thesis phase. Owner: Mahdi Kalantari.

## Vision

A **data-sovereign AI platform for remote sensing research**: your knowledge
— documents, rasters, feedback — stays on your machine, while compute is
pluggable: a remote OpenAI-compatible LLM API **by default** (e.g. Kilo
gateway), local GGUF models when you need full offline. Citation-grounded
answers over your own data, with a feedback loop that turns researcher
judgment into training data.

GeoFoundation is the umbrella: the memory engine, the agent SDK, the algorithm
libraries, the gateway server, and the apps assembled on top. The name also
nods to foundation models — the platform is designed around small, local
foundation-model embedders (nomic, OlmoEarth) and their future RS kin.

## Layer model

```
┌────────────────────────────────────────────────────────────┐
│ APPS        web SPA · CLI · (future) MCP server · notebooks│
├────────────────────────────────────────────────────────────┤
│ GATEWAY     geofoundation/server — FastAPI · /api/v1       │
│             composes all libs; apps consume ONLY this      │
├────────────────────────────────────────────────────────────┤
│ APPLICATION libs/geoagent (SDK)      · libs/metric_et      │
│             agent framework · tools · playbooks · ET model │
│             (future: geoagent apps, more algorithm libs)   │
├────────────────────────────────────────────────────────────┤
│ LEARNING    (future) GeoLearn — active learning,           │
│             incremental training, replay buffer            │
│             (future) GeoSynth — synthetic EO data          │
├────────────────────────────────────────────────────────────┤
│ MEMORY      libs/geomemory — knowledge store, hybrid       │
│             search, citations, feedback/review queue       │
├────────────────────────────────────────────────────────────┤
│ MODELS      (future) GeoModels — model registry/zoo:       │
│             GGUF LLMs, embedders, RS foundation models     │
├────────────────────────────────────────────────────────────┤
│ STORAGE     SQLite (FTS5 · RTree · WAL) + content-         │
│             addressed object store (SHA-256)               │
└────────────────────────────────────────────────────────────┘
```

**The one architectural rule:** dependencies point strictly downward.
Apps → Gateway → application/learning libs → memory → models → storage.
Apps never import libs directly; libs never import upward.

## Core values

1. **Local data, hybrid compute** — workspaces and knowledge never leave the
   user's machine; the LLM is pluggable, remote API by default, local GGUF as
   offline fallback. `offline: true` flips fully local (blocks API backend).
2. **Frugal by design** — local embedders stay CPU-friendly (no GPU needed);
   compute can scale up to hosted APIs without moving the data.
3. **Citations or abstention** — answers cite segments with locators, or
   say nothing. No silent hallucination. Provenance chain:
   `answer → citation → segment → asset_revision → objects/<sha256>`.
4. **The feedback loop is the product** — search/QA feedback → review queue →
   exported datasets → (future GeoLearn) training → better answers. This loop
   is the platform's differentiator vs. generic RAG tools and the thesis's
   core hypothesis.
5. **Framework + case studies** — libs stay domain-neutral; domain logic
   (sugarcane stress, ET, farms) lives in case studies and agent apps.

## Thesis context (MSc)

- Research question: does RAG-style knowledge memory + active user feedback
  improve stress-classification performance and continual performance under
  data scarcity? (See `../Ideas/geomemory-agri-thesis-plan.md`.)
- Case study: sugarcane (Khuzestan, Iran) · Sentinel-2 + Landsat 8/9.
- Deliverable: GeoFoundation platform + web app demo (incl. Persian/RTL)
  + experiment results.

## Roadmap — now vs. later

| Phase | Scope |
|---|---|
| **Now (MSc)** | Monorepo assembly · gateway server · web app (16 pages) · geoagent SDK polish · metric_et integration when ready · review-loop demo |
| **Post-defense** | GeoLearn extraction · GeoModels registry · MCP server app · GeoSynth · open-source release (docs, install story, plugin story) |

## What GeoFoundation is NOT

- Not a SaaS — no multi-tenant hosting, no auth beyond a local dev token.
- Not a fat meta-package — each lib is independently versioned and pinned.
- Not a data lake — workspaces are filesystem artifacts, not services.

## Naming

`GeoFoundation` = the platform/monorepo. Libs keep their own identities
(`geomemory`, `geoagent`, `metric_et`, future `geolearn`/`geosynth`).
Before any public release: check GitHub/PyPI for name collisions.
