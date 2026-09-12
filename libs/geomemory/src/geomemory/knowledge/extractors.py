"""Entity extraction protocols and rule-based implementation."""

from __future__ import annotations

import contextlib
import logging
import re
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Typed extraction result.
EntityTuple = tuple[str, str, tuple[float, float, float, float] | None]


class EntityExtractor(Protocol):
    """Pluggable protocol for extracting entities from text segments."""

    def extract(self, text: str) -> list[EntityTuple]:
        """Return list of (name, kind, bbox|None) found in text."""
        ...


# ──────────────────────────────────────────────────────────────────────────────
# Rule-based extractor — detects common RS patterns without LLM calls.
# ──────────────────────────────────────────────────────────────────────────────

_MS_RE = re.compile(r"\((\d+\.?\d*)\s*[\u2022\u00B7]\s*(\d+\.?\d*)\s*[\u2022\u00B7]\s*(\d+\.?\d*)\s*[\u2022\u00B7]\s*(\d+\.?\d*)\)")

_KNOWN_METRICS: dict[re.Pattern[str], str] = {
    re.compile(r"\bNDVI\b", re.IGNORECASE): "metric",
    re.compile(r"\bEVI\b", re.IGNORECASE): "metric",
    re.compile(r"\bSAVI\b", re.IGNORECASE): "metric",
    re.compile(r"\bLAI\b", re.IGNORECASE): "metric",
    re.compile(r"\bEVRI\b", re.IGNORECASE): "metric",
    re.compile(r"\bGNDVI\b", re.IGNORECASE): "metric",
    re.compile(r"\bNDBI\b", re.IGNORECASE): "metric",
    re.compile(r"\bcdvi\b", re.IGNORECASE): "metric",
    re.compile(r"\bndwi\b", re.IGNORECASE): "metric",
}

_KNOWN_SENSORS: dict[re.Pattern[str], str] = {
    re.compile(r"\bSentinel[- ]?2\b", re.IGNORECASE): "sensor",
    re.compile(r"\bSentinel[- ]?1\b", re.IGNORECASE): "sensor",
    re.compile(r"\bLandsat[- ]?[89]\b", re.IGNORECASE): "sensor",
    re.compile(r"\bLandsat\b", re.IGNORECASE): "sensor",
    re.compile(r"\bMODIS\b", re.IGNORECASE): "sensor",
    re.compile(r"\bASTER\b", re.IGNORECASE): "sensor",
    re.compile(r"\bWorldView\b", re.IGNORECASE): "sensor",
    re.compile(r"\bQuickBird\b", re.IGNORECASE): "sensor",
}

_KNOWN_STRESS_TYPES: dict[re.Pattern[str], str] = {
    re.compile(r"\bcrop stress\b", re.IGNORECASE): "stress_type",
    re.compile(r"\bdrought\b", re.IGNORECASE): "stress_type",
    re.compile(r"\bsalinity\b", re.IGNORECASE): "stress_type",
    re.compile(r"\bwater stress\b", re.IGNORECASE): "stress_type",
    re.compile(r"\bnutrient stress\b", re.IGNORECASE): "stress_type",
}

_KNOWN_LOCATIONS: dict[re.Pattern[str], str] = {
    re.compile(r"\bKhuzestan\b", re.IGNORECASE): "location",
    re.compile(r"\bIran\b", re.IGNORECASE): "location",
    re.compile(r"\bShadegan\b", re.IGNORECASE): "location",
    re.compile(r"\bKarun\b", re.IGNORECASE): "location",
    re.compile(r"\bAbadan\b", re.IGNORECASE): "location",
}

_KNOWN_PRODUCTS: dict[re.Pattern[str], str] = {
    re.compile(r"\bSentinel[- ]?2\b.*\bLevel\b", re.IGNORECASE): "product",
    re.compile(r"\bLandsat[- ]?[89]\b.*\bLevel\b", re.IGNORECASE): "product",
}


def _match_patterns(text: str, registry: dict[re.Pattern[str], str]) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    for pat, kind in registry.items():
        m = pat.search(text)
        if m:
            results.append((m.group(0).strip(), kind))
    return results


def _resolve_bbox(text: str) -> tuple[float, float, float, float] | None:
    """Extract a WGS84 bbox from parenthesised coordinates in text."""
    m = _MS_RE.search(text)
    if m is None:
        return None
    vals = [float(v) for v in (m.group(1), m.group(2), m.group(3), m.group(4))]
    # Normalize so min < max
    min_lon, max_lon = sorted(vals[:2])
    min_lat, max_lat = sorted(vals[2:])
    return (min_lon, min_lat, max_lon, max_lat)


class LLMEntityExtractor:
    """LLM-driven entity extractor with rule-based fallback.

    Uses the configured ``LLMBackend`` to prompt for structured JSON output.
    Falls back to :class:`RuleBasedExtractor` when no LLM backend is available.
    """

    PROMPT_TEMPLATE = (
        "Extract all geospatial entities from the following text. "
        "Return a JSON array of objects with keys: name, kind, bbox. "
        "kind must be one of: concept, location, sensor, product, stress_type, metric. "
        "bbox is [min_lon, min_lat, max_lon, max_lat] only for location entities, null otherwise. "
        "Text:\n---\n{text}\n---\nJSON:"
    )

    def __init__(self, llm_backend: Any = None) -> None:
        self._llm = llm_backend
        self._rule_based = RuleBasedExtractor()

    def extract(self, text: str) -> list[EntityTuple]:
        if self._llm is not None:
            try:
                return self._extract_via_llm(text)
            except Exception as exc:
                logger.warning("LLM extraction failed (%s), falling back to rule-based", exc)
        return self._rule_based.extract(text)

    def _extract_via_llm(self, text: str) -> list[EntityTuple]:
        from geomemory.core.models import GenerationRequest
        prompt = self.PROMPT_TEMPLATE.format(text=text)
        req = GenerationRequest(prompt=prompt, max_tokens=512, temperature=0.1)
        result = self._llm.generate(req)
        if result.abstained:
            return self._rule_based.extract(text)
        return self._parse_json_result(result.text, text)

    @staticmethod
    def _parse_json_result(raw: str, original_text: str) -> list[EntityTuple]:
        import json
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0] if "\n" in raw else raw[3:]
        try:
            items = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return []
        results: list[EntityTuple] = []
        seen: set[str] = set()
        valid_kinds = {"concept", "location", "sensor", "product", "stress_type", "metric"}
        bbox = _resolve_bbox(original_text)
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            kind = str(item.get("kind", "concept")).strip().lower()
            if not name or kind not in valid_kinds:
                continue
            key = f"{kind}:{name}"
            if key in seen:
                continue
            seen.add(key)
            ent_bbox = None
            bb = item.get("bbox")
            if isinstance(bb, list) and len(bb) == 4:
                with contextlib.suppress(TypeError, ValueError):
                    ent_bbox = (float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3]))
            elif kind == "location" and bbox is not None:
                ent_bbox = bbox
            results.append((name, kind, ent_bbox))
        if not results:
            return RuleBasedExtractor().extract(original_text)
        return results


class RuleBasedExtractor:
    """Rule-based entity extractor for common remote-sensing terms."""

    def extract(self, text: str) -> list[EntityTuple]:
        """Parse text and return detected (name, kind, bbox|None) tuples."""
        seen: set[str] = set()
        results: list[EntityTuple] = []
        bbox = _resolve_bbox(text)

        for name, kind in _match_patterns(text, _KNOWN_METRICS):
            key = f"{kind}:{name}"
            if key not in seen:
                seen.add(key)
                results.append((name, kind, bbox))

        for name, kind in _match_patterns(text, _KNOWN_SENSORS):
            key = f"{kind}:{name}"
            if key not in seen:
                seen.add(key)
                results.append((name, kind, bbox))

        for name, kind in _match_patterns(text, _KNOWN_STRESS_TYPES):
            key = f"{kind}:{name}"
            if key not in seen:
                seen.add(key)
                results.append((name, kind, bbox))

        for name, kind in _match_patterns(text, _KNOWN_LOCATIONS):
            key = f"{kind}:{name}"
            if key not in seen:
                seen.add(key)
                results.append((name, kind, bbox))

        for name, kind in _match_patterns(text, _KNOWN_PRODUCTS):
            key = f"{kind}:{name}"
            if key not in seen:
                seen.add(key)
                results.append((name, kind, bbox))

        return results
