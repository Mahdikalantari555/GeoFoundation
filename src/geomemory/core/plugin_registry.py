"""Registry for loaders, chunkers, and embedders keyed by mime type or space id."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """Generic string-keyed registry for pluggable components."""

    def __init__(self) -> None:
        self._items: dict[str, T] = {}

    def register(self, key: str, item: T) -> None:
        """Register an item under a key (e.g. a mime type)."""
        self._items[key] = item

    def unregister(self, key: str) -> None:
        """Remove an item by key."""
        self._items.pop(key, None)

    def get(self, key: str) -> T | None:
        """Return the item for a key, or None."""
        return self._items.get(key)

    def keys(self) -> list[str]:
        """Return all registered keys."""
        return list(self._items.keys())

    def all(self) -> dict[str, T]:
        """Return a copy of all registered items."""
        return dict(self._items)


class LoaderRegistry(Registry[Any]):
    """Registry of loaders keyed by mime type (or extension)."""


class ChunkerRegistry(Registry[Any]):
    """Registry of chunkers keyed by name."""


class EmbedderRegistry(Registry[Any]):
    """Registry of embedders keyed by space_id."""


class BackendRegistry(Registry[Any]):
    """Registry of retrieval backends keyed by name."""