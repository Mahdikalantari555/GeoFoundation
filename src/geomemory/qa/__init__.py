"""QA layer: LLM backends, prompts, citations, abstention, chat service."""

from __future__ import annotations

from geomemory.qa.abstention import abstention_reason, should_abstain
from geomemory.qa.backend import LLMBackend, NullBackend
from geomemory.qa.chat_service import ChatService
from geomemory.qa.citation import extract_citation_keys, map_citations, validate_citations
from geomemory.qa.llama_cpp_backend import LlamaCppBackend
from geomemory.qa.prompts import build_prompt, code_prompt, grounded_qa_prompt, research_prompt

__all__ = [
    "ChatService",
    "LLMBackend",
    "LlamaCppBackend",
    "NullBackend",
    "abstention_reason",
    "build_prompt",
    "code_prompt",
    "extract_citation_keys",
    "grounded_qa_prompt",
    "map_citations",
    "research_prompt",
    "should_abstain",
    "validate_citations",
]