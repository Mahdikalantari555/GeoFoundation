"""Prompt templates for different QA modes."""

from __future__ import annotations

from typing import Any

from geomemory.retrieval.context_packer import format_context


def grounded_qa_prompt(question: str, context: list[Any]) -> str:
    """Build a grounded QA prompt with numbered context and citation keys."""
    context_block = format_context(context)
    return (
        "You are a research assistant. Answer the question using ONLY the "
        "provided context. Cite sources as [1], [2], etc. If the context does "
        "not contain the answer, respond exactly: 'not found in selected sources'.\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )


def research_prompt(question: str, context: list[Any]) -> str:
    """Build a research-style prompt that synthesizes across sources."""
    context_block = format_context(context)
    return (
        "You are a research assistant. Synthesize an answer from the provided "
        "context, citing sources as [1], [2], etc. If the context is insufficient, "
        "respond exactly: 'not found in selected sources'.\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )


def code_prompt(question: str, context: list[Any]) -> str:
    """Build a code-focused prompt."""
    context_block = format_context(context)
    return (
        "You are a code assistant. Answer the question using ONLY the provided "
        "code context, citing sources as [1], [2], etc. If the context does not "
        "contain the answer, respond exactly: 'not found in selected sources'.\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )


def build_prompt(mode: str, question: str, context: list[Any]) -> str:
    """Dispatch to the appropriate prompt template."""
    if mode == "research":
        return research_prompt(question, context)
    if mode == "code":
        return code_prompt(question, context)
    return grounded_qa_prompt(question, context)