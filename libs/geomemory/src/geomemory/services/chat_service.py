"""Chat service — orchestrates QA."""

from __future__ import annotations

from geomemory.core.models import QAResult, SearchFilters
from geomemory.qa.chat_service import ChatService as QAChatService


class ChatService:
    """Public QA entry point wrapping the QA chat service."""

    def __init__(self, qa: QAChatService) -> None:
        self.qa = qa

    def ask(
        self,
        question: str,
        *,
        mode: str = "grounded_qa",
        filters: SearchFilters | None = None,
    ) -> QAResult:
        """Answer a question with citations, or abstain."""
        return self.qa.ask(question, mode=mode, filters=filters)
