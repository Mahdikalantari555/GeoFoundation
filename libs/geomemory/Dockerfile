# syntax=docker/dockerfile:1
# GeoMemory — lightweight multi-stage Docker build (ONNX + sqlite-vec, no torch by default).
#
# Base is torch-free: onnxruntime + tokenizers + sqlite-vec + huggingface_hub.
# Vision (OLMoEarth) stays opt-in [vision] (torch).
#
# Targets:
#   core    — CLI only (base: pydantic, numpy, onnxruntime, tokenizers, sqlite-vec)
#   docs    — + pymupdf, python-docx
#   rs      — + rasterio, shapely, geopandas, Pillow
#   vector  — + qdrant-client / lancedb optional
#   vision  — + torch (CPU), Pillow, olmoearth-pretrain
#   llamacpp — + llama-cpp-python (GGUF offline)
#   ui      — + streamlit (full stack)
#
# Usage:
#   docker build --target core -t geomemory:core .
#   docker build --target ui -t geomemory:ui .
#   docker compose --profile dev up

# -------------------------------------------------------------------
# Stage 1: builder — compiles all wheels, then discards toolchain
# -------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc g++ make \
    && pip install --no-cache-dir uv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system ".[vector,docs,rs,vision,ui,llamacpp]"

# -------------------------------------------------------------------
# Stage 2: runtime base — no compilers
# -------------------------------------------------------------------
FROM python:3.12-slim AS runtime-base

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        libexpat1 libstdc++6 libgomp1 curl \
    && pip install --no-cache-dir uv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./

# -------------------------------------------------------------------
# Stage 3: split targets
# -------------------------------------------------------------------

FROM runtime-base AS core
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
ENTRYPOINT ["geomemory"]

FROM runtime-base AS docs
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system pymupdf python-docx
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
ENTRYPOINT ["geomemory"]

FROM runtime-base AS rs
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system pymupdf python-docx rasterio shapely geopandas Pillow
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
ENTRYPOINT ["geomemory"]

FROM runtime-base AS vector
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system pymupdf python-docx rasterio shapely geopandas Pillow qdrant-client
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
ENTRYPOINT ["geomemory"]

FROM runtime-base AS vision
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system pymupdf python-docx rasterio shapely geopandas Pillow qdrant-client torch Pillow olmoearth-pretrain
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
ENTRYPOINT ["geomemory"]

FROM runtime-base AS llamacpp
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system llama-cpp-python
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
ENTRYPOINT ["geomemory"]

FROM runtime-base AS ui
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system pymupdf python-docx rasterio shapely geopandas Pillow qdrant-client torch streamlit
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .
COPY apps/ apps/
ENTRYPOINT ["streamlit", "run", "apps/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
