"""Shared pytest fixtures for GeoMemory tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure src is importable when running tests without installation.
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from geomemory import GeoMemory  # noqa: E402


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a fresh workspace in a temp directory."""
    ws = GeoMemory.create(tmp_path / "ws")
    yield ws
    ws.close()


@pytest.fixture
def sample_markdown(tmp_path):
    """Write a small Markdown document with headers."""
    path = tmp_path / "sample.md"
    path.write_text(
        "# Introduction\n\n"
        "Remote sensing is the acquisition of information about an object "
        "without physical contact.\n\n"
        "## Methods\n\n"
        "We use NDVI computed from Sentinel-2 imagery for crop stress detection.\n\n"
        "## Results\n\n"
        "The classification accuracy reached 92 percent.\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def sample_python(tmp_path):
    """Write a small Python file with functions and a class."""
    path = tmp_path / "sample.py"
    path.write_text(
        '"""Sample module."""\n\n'
        "import numpy as np\n\n\n"
        "def compute_ndvi(nir, red):\n"
        '    """Compute the NDVI index."""\n'
        "    return (nir - red) / (nir + red)\n\n\n"
        "class VegetationIndex:\n"
        '    """Base class for vegetation indices."""\n'
        "    def __init__(self, name):\n"
        "        self.name = name\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def sample_notebook(tmp_path):
    """Write a minimal Jupyter notebook."""
    import json

    path = tmp_path / "sample.ipynb"
    nb = {
        "cells": [
            {"cell_type": "markdown", "source": ["# Analysis"]},
            {"cell_type": "code", "source": ["print('hello')"]},
        ],
        "metadata": {"language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(nb), encoding="utf-8")
    return path
