"""Integration tests for the grounded QA chat pipeline."""

from __future__ import annotations

from geomemory.core.models import GenerationRequest, GenerationResult, SearchFilters, SearchHit
from geomemory.qa.backend import NullBackend
from geomemory.qa.chat_service import ChatService
from geomemory.retrieval.search_service import SearchService


class _StaticBackend:
    """Backend that answers from the first source with a citation."""

    model_id = "static"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        text = request.context[0].text + " [1]" if request.context else ""
        return GenerationResult(text=text, prompt_hash="h", model_id=self.model_id)

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)


class _StaticSearchService:
    """Search double returning a fixed ranked list."""

    def __init__(self, hits: list[SearchHit]):
        self._hits = hits

    def search(self, query, *, filters=None):
        from geomemory.core.models import QueryPlan, SearchResult

        return SearchResult(
            query=query,
            query_plan=QueryPlan(intent="search"),
            hits=self._hits,
            total_hits=len(self._hits),
            latency_ms=1,
        )


def _chat(hits, backend):
    return ChatService(
        _StaticSearchService(hits),
        backend,
        token_budget=1000,
        per_hit_budget=250,
    )


class TestChatService:
    def test_empty_question_abstains(self):
        chat = _chat([], NullBackend())
        result = chat.ask("   ")
        assert result.abstained is True
        assert result.abstention_reason == "Empty question"

    def test_no_hits_abstains(self):
        chat = _chat([], NullBackend())
        result = chat.ask("anything")
        assert result.abstained is True
        assert result.abstention_reason == "No relevant context found"

    def test_backend_abstention_flows_through(self):
        chat = _chat([SearchHit(id="s1", text="NDVI text")], NullBackend())
        result = chat.ask("What is NDVI?")
        assert result.abstained is True

    def test_grounded_answer_with_citation(self):
        chat = _chat([SearchHit(id="s1", text="NDVI measures vegetation health")], _StaticBackend())
        result = chat.ask("What does NDVI measure?")
        assert result.abstained is False
        assert "NDVI" in result.text
        assert len(result.citations) == 1
        assert result.citations[0].segment_id == "s1"

    def test_mode_default(self):
        chat = _chat([SearchHit(id="s1", text="text")], _StaticBackend())
        result = chat.ask("question", mode="grounded_qa")
        assert result.model == "static"

    def test_abstention_signals_from_abstention_phrase(self):
        chat = _chat([SearchHit(id="s1", text="irrelevant")], _StaticBackend())
        result = chat.ask("question")
        # Text is grounded, so no abstention is expected.
        assert result.abstained is False