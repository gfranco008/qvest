from __future__ import annotations

from typing import Any, Callable, Dict

from .availability import availability_requested, list_available_books
from .onboarding import (
    onboarding_requested,
    onboarding_save_requested,
    build_onboarding_from_history,
)
from .reading_history import reading_history_requested, list_read_books
from .holds import hold_requested, reserve_hold
from .series_author import series_author_requested, find_series_author_matches
from .student_snapshot import student_snapshot_requested, build_student_snapshot

ToolDetectFn = Callable[[str], bool]
ToolCallFn = Callable[..., Any]


_TOOL_REGISTRY: Dict[str, Dict[str, ToolCallFn | ToolDetectFn]] = {
    "availability": {
        "detect": availability_requested,
        "call": list_available_books,
    },
    "reading_history": {
        "detect": reading_history_requested,
        "call": list_read_books,
    },
    "reserve_hold": {
        "detect": hold_requested,
        "call": reserve_hold,
    },
    "onboard_from_history": {
        "detect": onboarding_requested,
        "call": build_onboarding_from_history,
    },
    "onboard_save_intent": {
        "detect": onboarding_save_requested,
        "call": onboarding_save_requested,
    },
    "series_author": {
        "detect": series_author_requested,
        "call": find_series_author_matches,
    },
    "student_snapshot": {
        "detect": student_snapshot_requested,
        "call": build_student_snapshot,
    },
}


def tool_names() -> list[str]:
    return sorted(_TOOL_REGISTRY.keys())


def tool_detect(name: str, message: str) -> bool:
    tool = _TOOL_REGISTRY.get(name)
    if not tool:
        return False
    detect = tool.get("detect")
    if not callable(detect):
        return False
    return bool(detect(message))


def call_tool(name: str, **kwargs: Any) -> Any:
    tool = _TOOL_REGISTRY.get(name)
    if not tool or "call" not in tool:
        raise ValueError(f"Unknown tool: {name}")
    call = tool["call"]
    if not callable(call):
        raise ValueError(f"Tool is not callable: {name}")
    safe_keys = ", ".join(sorted(kwargs.keys()))
    print(f"[tool] call={name} keys=[{safe_keys}]")
    return call(**kwargs)
