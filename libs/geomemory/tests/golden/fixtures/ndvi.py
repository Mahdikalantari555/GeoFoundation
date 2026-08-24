"""Golden NDVI module for ingestion tests."""

import numpy as np


def compute_ndvi(nir, red):
    """Return the normalized difference vegetation index."""
    return (nir - red) / (nir + red)


def detect_flood(backscatter, threshold=-12.0):
    """Flag pixels whose backscatter drops below the threshold."""
    return backscatter < threshold


class VegetationIndex:
    """Base class for vegetation indices."""

    def __init__(self, name):
        self.name = name