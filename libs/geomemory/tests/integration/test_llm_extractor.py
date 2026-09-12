"""Integration tests for the LLM-driven entity extractor (gated on LLM availability)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from geomemory.core.models import GenerationRequest, GenerationResult
from geomemory.knowledge.extractors import LLMEntityExtractor, RuleBasedExtractor


class _FakeLLMBackend:
    """Deterministic fake LLM backend returning structured JSON."""

    model_id = "fake"

    def __init__(self, entities: list[dict[str, Any]]) -> None:
        self.entities = entities

    def generate(self, request: GenerationRequest) -> GenerationResult:
        payload = json.dumps(self.entities)
        return GenerationResult(text=payload, prompt_hash="", model_id=self.model_id)

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)


class _FailFastLLM:
    """LLM that always raises — used to exercise the fallback path."""

    model_id = "fail"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        raise RuntimeError("simulated LLM failure")

    def count_tokens(self, text: str) -> int:
        return 1


class TestLLMEntityExtractor:
    def test_llm_returns_entities(self) -> None:
        backend = _FakeLLMBackend([
            {"name": "NDVI", "kind": "metric", "bbox": None},
            {"name": "salinity", "kind": "stress_type", "bbox": None},
        ])
        extractor = LLMEntityExtractor(llm_backend=backend)
        hits = extractor.extract("This text mentions NDVI and salinity.")
        names = [h[0] for h in hits]
        assert "NDVI" in names
        assert "salinity" in names
        kinds = {n: k for n, k, b in hits}
        assert kinds["NDVI"] == "metric"
        assert kinds["salinity"] == "stress_type"

    def test_llm_failure_falls_back_to_rule_based(self) -> None:
        backend = _FailFastLLM()
        extractor = LLMEntityExtractor(llm_backend=backend)
        hits = extractor.extract("NDVI vegetation index is useful.")
        names = [h[0] for h in hits]
        assert "NDVI" in names

    def test_llm_abstain_falls_back(self) -> None:
        class _AbstainingLLM:
            model_id = "abstain"
            def generate(self, request: GenerationRequest) -> GenerationResult:
                return GenerationResult(text="not found", prompt_hash="", model_id="abstain", abstained=True)
            def count_tokens(self, text: str) -> int:
                return 1
        extractor = LLMEntityExtractor(llm_backend=_AbstainingLLM())
        hits = extractor.extract("The NDVI index was computed.")
        names = [h[0] for h in hits]
        assert "NDVI" in names

    def test_no_llm_uses_rule_based_only(self) -> None:
        extractor = LLMEntityExtractor(llm_backend=None)
        hits = extractor.extract("Sentinel-2 data over Khuzestan.")
        names = {h[0] for h in hits}
        assert "Sentinel-2" in names
        assert "Khuzestan" in names

    def test_empty_json_returns_rule_based(self) -> None:
        backend = _FakeLLMBackend([])
        extractor = LLMEntityExtractor(llm_backend=backend)
        hits = extractor.extract("Only NDVI matters here.")
        names = [h[0] for h in hits]
        # Falls back to rule-based because empty list from LLM
        assert "NDVI" in names

    def test_location_with_bbox_from_llm(self) -> None:
        backend = _FakeLLMBackend([
            {"name": "Khuzestan", "kind": "location", "bbox": [51.0, 32.0, 52.0, 33.0]},
        ])
        extractor = LLMEntityExtractor(llm_backend=backend)
        hits = extractor.extract("Study area Khuzestan.")
        assert len(hits) == 1
        name, kind, bbox = hits[0]
        assert name == "Khuzestan"
        assert kind == "location"
        assert bbox == (51.0, 32.0, 52.0, 33.0)
