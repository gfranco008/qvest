from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Literal

from .availability import availability_requested, list_available_books
from .holds import hold_requested, reserve_hold
from .onboarding import (
    onboarding_requested,
    onboarding_save_requested,
    build_onboarding_from_history,
)
from .reading_history import reading_history_requested, list_read_books
from .series_author import series_author_requested, find_series_author_matches
from .student_snapshot import student_snapshot_requested, build_student_snapshot

ToolDetectFn = Callable[[str], bool]
ToolCallFn = Callable[..., Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    kind: Literal["action", "signal"]
    description: str
    input_schema: Dict[str, Any]
    system_context: List[str]


_ACTION_REGISTRY: Dict[str, Dict[str, ToolCallFn | ToolDetectFn | ToolSpec]] = {
    "availability": {
        "detect": availability_requested,
        "call": list_available_books,
        "spec": ToolSpec(
            name="availability",
            kind="action",
            description="List available books that match a request.",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "User request to filter results.",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 8,
                        "minimum": 1,
                        "maximum": 200,
                    },
                },
                "required": ["message"],
            },
            system_context=["books", "genres"],
        ),
    },
    "reading_history": {
        "detect": reading_history_requested,
        "call": list_read_books,
        "spec": ToolSpec(
            name="reading_history",
            kind="action",
            description="Return a student's recent reading history.",
            input_schema={
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "default": 25,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": ["student_id"],
            },
            system_context=["books", "loans"],
        ),
    },
    "reserve_hold": {
        "detect": hold_requested,
        "call": reserve_hold,
        "spec": ToolSpec(
            name="reserve_hold",
            kind="action",
            description="Place a hold on a book for a student.",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "student_id": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["message"],
            },
            system_context=["books", "students"],
        ),
    },
    "onboard_from_history": {
        "detect": onboarding_requested,
        "call": build_onboarding_from_history,
        "spec": ToolSpec(
            name="onboard_from_history",
            kind="action",
            description="Generate an onboarding profile from a student's reading history.",
            input_schema={
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                    "genre_limit": {
                        "type": "integer",
                        "default": 2,
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "interest_limit": {
                        "type": "integer",
                        "default": 4,
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": ["student_id"],
            },
            system_context=["books", "loans"],
        ),
    },
    "series_author": {
        "detect": series_author_requested,
        "call": find_series_author_matches,
        "spec": ToolSpec(
            name="series_author",
            kind="action",
            description="Find series continuations or more books by the same author.",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "User request mentioning a series, author, or title.",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 6,
                        "minimum": 1,
                        "maximum": 12,
                    },
                },
                "required": ["message"],
            },
            system_context=["books"],
        ),
    },
    "student_snapshot": {
        "detect": student_snapshot_requested,
        "call": build_student_snapshot,
        "spec": ToolSpec(
            name="student_snapshot",
            kind="action",
            description="Summarize a student's reading stats, feedback, and holds.",
            input_schema={
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                    "recent_limit": {
                        "type": "integer",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10,
                    },
                    "top_limit": {
                        "type": "integer",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 6,
                    },
                },
                "required": ["student_id"],
            },
            system_context=["books", "loans", "students", "agent_state"],
        ),
    },
}

_SIGNAL_REGISTRY: Dict[str, Dict[str, ToolDetectFn | ToolSpec]] = {
    "onboard_save_intent": {
        "detect": onboarding_save_requested,
        "spec": ToolSpec(
            name="onboard_save_intent",
            kind="signal",
            description="Detect whether the user wants to save onboarding preferences.",
            input_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            system_context=[],
        ),
    },
}


def tool_names(*, include_signals: bool = False) -> list[str]:
    names = list(_ACTION_REGISTRY.keys())
    if include_signals:
        names.extend(_SIGNAL_REGISTRY.keys())
    return sorted(names)


def tool_metadata(*, include_signals: bool = True) -> List[Dict[str, Any]]:
    specs: List[ToolSpec] = [
        entry["spec"] for entry in _ACTION_REGISTRY.values() if isinstance(entry.get("spec"), ToolSpec)
    ]
    if include_signals:
        specs.extend(
            entry["spec"] for entry in _SIGNAL_REGISTRY.values() if isinstance(entry.get("spec"), ToolSpec)
        )
    return [asdict(spec) for spec in sorted(specs, key=lambda item: item.name)]


def action_detect(name: str, message: str) -> bool:
    tool = _ACTION_REGISTRY.get(name)
    if not tool:
        return False
    detect = tool.get("detect")
    if not callable(detect):
        return False
    return bool(detect(message))


def signal_detect(name: str, message: str) -> bool:
    tool = _SIGNAL_REGISTRY.get(name)
    if not tool:
        return False
    detect = tool.get("detect")
    if not callable(detect):
        return False
    return bool(detect(message))


def tool_detect(name: str, message: str) -> bool:
    return action_detect(name, message)


def call_tool(name: str, **kwargs: Any) -> Any:
    tool = _ACTION_REGISTRY.get(name)
    if not tool or "call" not in tool:
        raise ValueError(f"Unknown tool: {name}")
    call = tool["call"]
    if not callable(call):
        raise ValueError(f"Tool is not callable: {name}")
    safe_keys = ", ".join(sorted(kwargs.keys()))
    print(f"[tool] call={name} keys=[{safe_keys}]")
    return call(**kwargs)
