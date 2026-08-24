"""Abstention policy and detection."""

from __future__ import annotations

_ABSTENTION_PHRASES = (
    "not found in selected sources",
    "not found in the provided context",
    "i don't know",
    "i do not know",
    "cannot answer",
    "insufficient information",
)


def should_abstain(text: str) -> bool:
    """Return True if the model output signals abstention."""
    lowered = text.strip().lower()
    return any(phrase in lowered for phrase in _ABSTENTION_PHRASES)


def abstention_reason(text: str) -> str:
    """Return a human-readable abstention reason."""
    if not text.strip():
        return "Empty answer generated"
    return "Model indicated insufficient evidence in the provided context"