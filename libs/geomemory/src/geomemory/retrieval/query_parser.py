"""Query normalization and filter extraction."""

from __future__ import annotations

import re

from geomemory.core.models import SearchFilters


class QueryParser:
    """Normalize a query and extract explicit filters.

    Filters can be supplied directly (via ``SearchFilters``) or embedded in
    the query string using a simple ``key:value`` syntax (e.g. ``sensor:Sentinel-2``).
    """

    _FILTER_RE = re.compile(r"\b(sensor|collection|type|language):([\w\-\.]+)")

    def parse(self, query: str, filters: SearchFilters | None = None) -> tuple[str, SearchFilters]:
        """Return (clean_query, filters) with embedded filters merged in."""
        query = (query or "").strip()
        filters = filters or SearchFilters()

        embedded: dict[str, list[str]] = {}
        clean_parts: list[str] = []
        for token in query.split():
            m = self._FILTER_RE.match(token)
            if m:
                key, value = m.group(1), m.group(2)
                embedded.setdefault(key, []).append(value)
            else:
                clean_parts.append(token)
        clean_query = " ".join(clean_parts)

        if "sensor" in embedded:
            filters.sensors = (filters.sensors or []) + embedded["sensor"]
        if "collection" in embedded:
            filters.collections = (filters.collections or []) + embedded["collection"]
        if "type" in embedded:
            filters.asset_types = (filters.asset_types or []) + embedded["type"]
        if "language" in embedded:
            filters.languages = (filters.languages or []) + embedded["language"]

        return clean_query, filters

    def detect_intent(self, query: str) -> str:
        """Heuristically detect query intent."""
        q = query.lower()
        if any(w in q for w in ("how", "what is", "why", "explain", "compare", "define")):
            return "grounded_qa"
        if any(w in q for w in ("function", "class", "code", "implement", "def ")):
            return "code"
        return "search"