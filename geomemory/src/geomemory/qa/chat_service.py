"""End-to-end QA orchestration: search → context pack → generate → cite."""

from __future__ import annotations

import time
from typing import Any

from geomemory.core.exceptions import AbstentionError
from geomemory.core.models import (
    GenerationRequest,
    QAResult,
    SearchFilters,
)
from geomemory.qa.abstention import abstention_reason, should_abstain
from geomemory.qa.citation import map_citations
from geomemory.qa.prompts import build_prompt
from geomemory.retrieval.context_packer import pack_context
from geomemory.retrieval.search_service import SearchService


class ChatService:
    """Orchestrate grounded QA using a search service and an LLM backend."""

    def __init__(
        self,
        search_service: SearchService,
        llm_backend: Any,
        *,
        token_budget: int = 2000,
        per_hit_budget: int = 500,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> None:
        self.search_service = search_service
        self.llm_backend = llm_backend
        self.token_budget = token_budget
        self.per_hit_budget = per_hit_budget
        self.max_tokens = max_tokens
        self.temperature = temperature

    def ask(
        self,
        question: str,
        *,
        mode: str = "grounded_qa",
        filters: SearchFilters | None = None,
    ) -> QAResult:
        """Answer a question with citations, or abstain."""
        start = time.perf_counter()
        question = (question or "").strip()
        if not question:
            return QAResult(
                text="",
                abstained=True,
                abstention_reason="Empty question",
                model=getattr(self.llm_backend, "model_id", "unknown"),
            )

        # Retrieve.
        result = self.search_service.search(question, filters=filters)
        if not result.hits:
            return QAResult(
                text="not found in selected sources",
                abstained=True,
                abstention_reason="No relevant context found",
                sources=result.hits,
                retrieval_run_id=result.retrieval_run_id,
                latency_ms=result.latency_ms,
                model=getattr(self.llm_backend, "model_id", "unknown"),
            )

        # Pack context within token budget.
        context = pack_context(
            result.hits,
            token_budget=self.token_budget,
            per_hit_budget=self.per_hit_budget,
        )
        if not context:
            return QAResult(
                text="not found in selected sources",
                abstained=True,
                abstention_reason="Context exceeded token budget",
                sources=result.hits,
                retrieval_run_id=result.retrieval_run_id,
                latency_ms=result.latency_ms,
                model=getattr(self.llm_backend, "model_id", "unknown"),
            )

        # Generate.
        prompt = build_prompt(mode, question, context)
        gen_request = GenerationRequest(
            prompt=prompt,
            context=context,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            stop_sequences=["\n\n"],
        )
        try:
            gen = self.llm_backend.generate(gen_request)
        except AbstentionError as exc:
            return QAResult(
                text="",
                abstained=True,
                abstention_reason=str(exc),
                sources=context,
                retrieval_run_id=result.retrieval_run_id,
                latency_ms=result.latency_ms,
                model=getattr(self.llm_backend, "model_id", "unknown"),
            )

        # Map citations and detect abstention.
        citations = map_citations("", gen.text, context)
        abstained = gen.abstained or should_abstain(gen.text)
        latency_ms = int((time.perf_counter() - start) * 1000)

        return QAResult(
            text=gen.text,
            citations=citations,
            abstained=abstained,
            abstention_reason=abstention_reason(gen.text) if abstained else None,
            sources=context,
            retrieval_run_id=result.retrieval_run_id,
            latency_ms=latency_ms,
            model=gen.model_id,
        )
