"""Domain event types for lightweight event sourcing."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import Field

from geomemory.core.models import GeoMemoryModel, new_id, utc_now

# Event type constants
ASSET_CREATED = "asset_created"
ASSET_REVISION_CREATED = "asset_revision_created"
SEGMENT_INDEXED = "segment_indexed"
SEARCH_COMPLETED = "search_completed"
ANSWER_GENERATED = "answer_generated"
FEEDBACK_RECORDED = "feedback_recorded"
JOB_STATE_CHANGED = "job_state_changed"
COLLECTION_CREATED = "collection_created"


class DomainEvent(GeoMemoryModel):
    """A recorded domain event."""

    id: str = Field(default_factory=lambda: new_id("evt"))
    event_type: str
    entity_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=utc_now)


class EventBus:
    """Synchronous in-process event bus with subscriber callbacks."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[DomainEvent], None]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        """Register a handler for an event type."""
        self._subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[DomainEvent], None]) -> None:
        """Remove a handler from an event type."""
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, event: DomainEvent) -> None:
        """Dispatch an event to all subscribers of its type."""
        for handler in self._subscribers.get(event.event_type, []):
            handler(event)
