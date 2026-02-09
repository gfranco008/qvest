from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from .data_loader import DATA_DIR

STATE_PATH = DATA_DIR / "agent_state.json"

DEFAULT_STATE: Dict[str, Any] = {
    "onboarding_profiles": {},
    "holds": [],
    "feedback": [],
    "chat_sessions": {},
}


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return deepcopy(DEFAULT_STATE)
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_STATE)

    if not isinstance(data, dict):
        return deepcopy(DEFAULT_STATE)

    for key, value in DEFAULT_STATE.items():
        if key not in data or not isinstance(data[key], type(value)):
            data[key] = deepcopy(value)

    return data


def save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.write_text(
        json.dumps(state, indent=2, sort_keys=True),
        encoding="utf-8",
    )
