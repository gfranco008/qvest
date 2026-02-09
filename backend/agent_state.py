from __future__ import annotations

import json
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterator, List
from uuid import uuid4

from pydantic import BaseModel, Field

from .data_loader import DATA_DIR

STATE_PATH = DATA_DIR / "agent_state.json"
SCHEMA_VERSION = 1

try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


class ObservabilityEvent(BaseModel):
    event_id: str
    created_at: str
    mode: str
    message: str | None = None
    student_id: str | None = None
    intents: Dict[str, bool] = Field(default_factory=dict)
    signals: Dict[str, bool] = Field(default_factory=dict)
    tools_called: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    counts: Dict[str, int] = Field(default_factory=dict)

    class Config:
        extra = "ignore"


class AgentState(BaseModel):
    schema_version: int = Field(default=SCHEMA_VERSION)
    onboarding_profiles: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    holds: List[Dict[str, Any]] = Field(default_factory=list)
    feedback: List[Dict[str, Any]] = Field(default_factory=list)
    chat_sessions: Dict[str, List[Dict[str, str]]] = Field(default_factory=dict)
    observability: List[ObservabilityEvent] = Field(default_factory=list)

    class Config:
        extra = "ignore"


def _validate_state(data: Dict[str, Any]) -> AgentState:
    if hasattr(AgentState, "model_validate"):
        return AgentState.model_validate(data)
    return AgentState.parse_obj(data)


def _validate_event(data: Dict[str, Any]) -> ObservabilityEvent:
    if hasattr(ObservabilityEvent, "model_validate"):
        return ObservabilityEvent.model_validate(data)
    return ObservabilityEvent.parse_obj(data)


def _dump_model(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _default_state() -> Dict[str, Any]:
    return _dump_model(AgentState())


DEFAULT_STATE: Dict[str, Any] = _default_state()


def _parse_state_payload(payload: str) -> Dict[str, Any]:
    if not payload.strip():
        return deepcopy(DEFAULT_STATE)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_STATE)

    if not isinstance(data, dict):
        return deepcopy(DEFAULT_STATE)

    try:
        state = _validate_state(data)
    except Exception:
        return deepcopy(DEFAULT_STATE)
    state.schema_version = SCHEMA_VERSION
    return _dump_model(state)


@contextmanager
def _locked_state_file() -> Iterator[Any]:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = STATE_PATH.open("a+", encoding="utf-8")
    try:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        yield handle
    finally:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return deepcopy(DEFAULT_STATE)
    try:
        with STATE_PATH.open("r", encoding="utf-8") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            payload = handle.read()
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        return deepcopy(DEFAULT_STATE)

    return _parse_state_payload(payload)


def save_state(state: Dict[str, Any] | AgentState) -> None:
    if isinstance(state, AgentState):
        state_model = state
    else:
        state_model = _validate_state(state)
    state_model.schema_version = SCHEMA_VERSION
    payload = json.dumps(_dump_model(state_model), indent=2, sort_keys=True)

    with _locked_state_file() as handle:
        handle.seek(0)
        handle.truncate()
        handle.write(payload)


def new_event_id() -> str:
    return f"EVT-{uuid4().hex[:10]}"


def record_observability(event: Dict[str, Any], *, max_entries: int = 200) -> None:
    with _locked_state_file() as handle:
        payload = handle.read()
        state = _parse_state_payload(payload)
        events = state.get("observability", [])
        events.append(_dump_model(_validate_event(event)))
        if len(events) > max_entries:
            events = events[-max_entries:]
        state["observability"] = events
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps(state, indent=2, sort_keys=True))
