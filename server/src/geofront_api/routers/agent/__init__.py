"""Agent routes: chat SSE, conversations, tools, playbooks, files.

Thin HTTP bridge over the geoagent public API — zero new logic.
"""

from __future__ import annotations

from .chat import router as chat_router
from .conversations import router as conversations_router
from .files import router as files_router
from .playbooks import router as playbooks_router
from .tools import router as tools_router

__all__ = [
    "chat_router",
    "conversations_router",
    "files_router",
    "playbooks_router",
    "tools_router",
]
