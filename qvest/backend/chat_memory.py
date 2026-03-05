from __future__ import annotations

from typing import Dict, List

CHAT_SESSIONS: Dict[str, List[Dict[str, str]]] = {}


def get_history(session_id: str) -> List[Dict[str, str]]:
    return CHAT_SESSIONS.setdefault(session_id, [])


def set_history(session_id: str, history: List[Dict[str, str]]) -> None:
    CHAT_SESSIONS[session_id] = history
