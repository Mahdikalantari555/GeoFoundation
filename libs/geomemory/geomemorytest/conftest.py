"""Root conftest for the geomemorytest suite."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the GeoMemory src package is importable even when tests are run from
# the geomemorytest directory (suite lives at <repo>/geomemory/geomemorytest/).
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from geomemory.storage.database import connect, initialize  # noqa: E402
from geomemory.storage.object_store import ObjectStore  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    """A fresh SQLite database on disk with schema initialized."""
    db = tmp_path / "test.db"
    conn = connect(db)
    initialize(conn)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def object_store(tmp_path):
    return ObjectStore(tmp_path / "objects")


@pytest.fixture
def sample_markdown(tmp_path):
    p = tmp_path / "sample.md"
    p.write_text(
        "# NDVI Analysis\n\n"
        "NDVI is used to monitor crop health.\n\n"
        "## Methods\n\n"
        "Sentinel-2 provides multispectral imagery.\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def sample_python(tmp_path):
    p = tmp_path / "sample.py"
    p.write_text(
        "def compute_ndvi(nir, red):\n"
        "    return (nir - red) / (nir + red)\n\n\n"
        "class VegetationIndex:\n"
        "    def __init__(self, name):\n"
        "        self.name = name\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def sample_notebook(tmp_path):
    nb = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Crop stress"]},
            {"cell_type": "code", "source": ["print('hello')"]},
        ],
        "metadata": {"language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    p = tmp_path / "sample.ipynb"
    p.write_text(str(nb), encoding="utf-8")
    return p
