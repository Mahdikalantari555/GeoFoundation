from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PredictionResult:
    labels: list[int]
    confidence: list[float]
    abstain: bool
    key: tuple[str, ...] | str
    n_samples: int
    model_version: str
    source: str = "classifier"
