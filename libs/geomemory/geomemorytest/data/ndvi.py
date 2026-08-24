def compute_ndvi(nir, red):
    """Compute NDVI from NIR and Red reflectance bands.

    Args:
        nir: Near-infrared band values
        red: Red band values

    Returns:
        NDVI values in range [-1, 1]
    """
    return (nir - red) / (nir + red)


class VegetationIndex:
    """Base class for vegetation indices."""

    def __init__(self, name):
        self.name = name

    def compute(self, bands):
        raise NotImplementedError


class EVI(VegetationIndex):
    """Enhanced Vegetation Index."""

    def compute(self, nir, red, blue):
        return 2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1)
