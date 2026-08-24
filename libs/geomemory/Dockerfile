# syntax=docker/dockerfile:1
# GeoMemory — optimized multi-stage Docker build with split targets.
#
# Key optimization: dependency install layer is cached independently from
# src/ changes. Third-party wheels are downloaded once and stored in the
# BuildKit cache. Only the local package wheel rebuilds when src/ changes
# (fast for pure Python).
#
# Targets:
#   core    — CLI only (pydantic, numpy, click, PyYAML)
#   ai      — + txtai, llama-cpp-python
#   docs    — + pymupdf, python-docx
#   rs      — + rasterio, shapely, geopandas, Pillow
#   st      — + sentence-transformers
#   vector  — + qdrant-client
#   vision  — + torch (CPU), Pillow
#   ui      — + streamlit (full stack)
#
# Usage:
#   docker build --target core -t geomemory:core .
#   docker build --target ui -t geomemory:ui .
#   docker compose --profile dev up

# -------------------------------------------------------------------
# Stage 1: builder — compiles all wheels, then discards toolchain
# -------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    UV_TORCH_BACKEND=cpu

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc g++ make \
    && pip install --no-cache-dir uv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy manifests first — caches independently of src/.
COPY pyproject.toml README.md ./

# Pre-compile all wheels into the BuildKit cache.
# This layer only re-runs when pyproject.toml changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system ".[ai,st,vector,docs,rs,vision,ui]"

# -------------------------------------------------------------------
# Stage 2: runtime base — no compilers, no build-essential
# -------------------------------------------------------------------
FROM python:3.11-slim AS runtime-base

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        libexpat1 libstdc++6 libgomp1 curl \
    && pip install --no-cache-dir uv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy manifests (for metadata layer).
COPY pyproject.toml README.md ./

# -------------------------------------------------------------------
# Stage 3: split targets — each adds only its needed packages
# -------------------------------------------------------------------

# CORE: minimal — no extra installs needed
FROM runtime-base AS core
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
ENTRYPOINT ["geomemory"]

# AI: + txtai, llama-cpp-python
FROM runtime-base AS ai
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system txtai llama-cpp-python
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
ENTRYPOINT ["geomemory"]

# DOCS: + pymupdf, python-docx
FROM runtime-base AS docs
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system txtai llama-cpp-python pymupdf python-docx
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
ENTRYPOINT ["geomemory"]

# RS: + rasterio, shapely, geopandas, Pillow
FROM runtime-base AS rs
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system txtai llama-cpp-python pymupdf python-docx \
        rasterio shapely geopandas Pillow
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
ENTRYPOINT ["geomemory"]

# ST: + sentence-transformers
FROM runtime-base AS st
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system txtai llama-cpp-python pymupdf python-docx \
        rasterio shapely geopandas Pillow sentence-transformers
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
ENTRYPOINT ["geomemory"]

# VECTOR: + qdrant-client
FROM runtime-base AS vector
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system txtai llama-cpp-python pymupdf python-docx \
        rasterio shapely geopandas Pillow sentence-transformers \
        qdrant-client
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
ENTRYPOINT ["geomemory"]

# VISION: + torch (CPU), Pillow
FROM runtime-base AS vision
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_TORCH_BACKEND=cpu uv pip install --system txtai llama-cpp-python \
        pymupdf python-docx rasterio shapely geopandas Pillow \
        sentence-transformers qdrant-client torch
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
ENTRYPOINT ["geomemory"]

# UI: full stack + streamlit
FROM runtime-base AS ui
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_TORCH_BACKEND=cpu uv pip install --system txtai llama-cpp-python \
        pymupdf python-docx rasterio shapely geopandas Pillow \
        sentence-transformers qdrant-client torch streamlit
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
COPY apps/ apps/
ENTRYPOINT ["streamlit", "run", "apps/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
