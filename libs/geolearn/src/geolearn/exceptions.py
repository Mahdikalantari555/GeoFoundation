class GeoLearnError(Exception):
    """Base exception for GeoLearn library."""


class ClassifierNotTrainedError(GeoLearnError):
    """Raised when an operation requires a trained classifier."""


class ModelNotFoundError(GeoLearnError):
    """Raised when a requested model is not found."""
