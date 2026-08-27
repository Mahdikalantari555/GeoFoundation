# Gateway — FastAPI facade over geomemory + geoagent
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for rasterio/geopandas optional (kept minimal for core)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential \
  && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests first for layer caching
COPY libs/geomemory/pyproject.toml libs/geomemory/README.md* libs/geomemory/
COPY libs/geoagent/pyproject.toml libs/geoagent/README.md* libs/geoagent/
COPY server/pyproject.toml server/README.md* server/

# Copy sources (install needs package data)
COPY libs/geomemory/src libs/geomemory/src
COPY libs/geomemory/geomemorytest libs/geomemory/geomemorytest
COPY libs/geoagent/src libs/geoagent/src
COPY libs/geoagent/tests libs/geoagent/tests
COPY server/src server/src

RUN pip install --upgrade pip \
 && pip install -e libs/geomemory \
 && pip install -e libs/geoagent \
 && pip install -e server

EXPOSE 8000

ENV GEOFOND_WORKSPACE=/workspace \
    GEOMEMORY_LLM_API_KEY="" \
    PYTHONPATH=/app/server/src:/app/libs/geomemory/src:/app/libs/geoagent/src

# Single worker per SPEC (SQLite single writer)
CMD ["uvicorn", "geofront_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
