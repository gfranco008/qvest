from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Tuple

from ..agent_state import load_state, save_state
from ..agents.utils import next_id


HOLD_RE = re.compile(
    r"\b("
    r"reserve|reservation|place (a )?hold|put (a )?hold|request (a )?hold|"
    r"hold(?!\s+on\b)"
    r")\b",
    re.IGNORECASE,
)
BOOK_ID_RE = re.compile(r"\bB\d{4}\b", re.IGNORECASE)
STUDENT_ID_RE = re.compile(r"\bS\d{4}\b", re.IGNORECASE)


def hold_requested(message: str) -> bool:
    if not message:
        return False
    return bool(HOLD_RE.search(message))


def _normalize(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"[^a-z0-9\s-]", " ", text.lower()).strip()


def _tokenize(text: str) -> List[str]:
    return [token for token in _normalize(text).split() if token]


def _token_match(title_token: str, message_token: str) -> bool:
    if title_token == message_token:
        return True
    if len(title_token) >= 4 and title_token.startswith(message_token):
        return True
    if len(message_token) >= 4 and message_token.startswith(title_token):
        return True
    return False


def _match_student_id(message: str | None, student_id: str | None) -> str | None:
    if student_id:
        return student_id
    if not message:
        return None
    match = STUDENT_ID_RE.search(message)
    return match.group(0).upper() if match else None


def _match_book_by_id(message: str | None, books: Dict[str, Any]) -> Any | None:
    if not message:
        return None
    match = BOOK_ID_RE.search(message)
    if not match:
        return None
    return books.get(match.group(0).upper())


def _exact_title_matches(message: str, books: Dict[str, Any]) -> List[Any]:
    text = _normalize(message)
    results = []
    for book in books.values():
        title = getattr(book, "title", "")
        title_norm = _normalize(title)
        if title_norm and title_norm in text:
            results.append(book)
    return results


def _fuzzy_title_matches(message: str, books: Dict[str, Any]) -> List[Any]:
    message_tokens = _tokenize(message)
    if not message_tokens:
        return []
    scored: List[Tuple[float, int, int, Any]] = []
    for book in books.values():
        title_tokens = _tokenize(getattr(book, "title", ""))
        if not title_tokens:
            continue
        matched = sum(
            1
            for token in title_tokens
            if any(_token_match(token, msg_token) for msg_token in message_tokens)
        )
        if matched == 0:
            continue
        ratio = matched / len(title_tokens)
        if ratio < 0.6 and matched < 2:
            continue
        scored.append((ratio, matched, len(title_tokens), book))
    if not scored:
        return []
    scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    best_ratio, best_matched, _, _ = scored[0]
    top = [
        book
        for ratio, matched, _, book in scored
        if ratio == best_ratio and matched == best_matched
    ]
    return top


def _match_book(message: str | None, books: Dict[str, Any]) -> List[Any]:
    if not message:
        return []
    by_id = _match_book_by_id(message, books)
    if by_id:
        return [by_id]
    exact = _exact_title_matches(message, books)
    if exact:
        return exact
    return _fuzzy_title_matches(message, books)


def reserve_hold(
    *,
    books: Dict[str, Any],
    students: Dict[str, Any],
    message: str,
    student_id: str | None = None,
    notes: str | None = None,
) -> Dict[str, Any]:
    resolved_student_id = _match_student_id(message, student_id)
    if not resolved_student_id:
        return {
            "status": "needs_student_id",
            "message": "Student_id is missing. Ask for it before placing a hold.",
            "student_id": None,
            "book_id": None,
            "book": None,
            "hold": None,
            "matches": [],
        }
    if resolved_student_id not in students:
        return {
            "status": "invalid_student",
            "message": "Student not found.",
            "student_id": resolved_student_id,
            "book_id": None,
            "book": None,
            "hold": None,
            "matches": [],
        }

    matches = _match_book(message, books)
    if not matches:
        return {
            "status": "needs_book",
            "message": "Book title or ID is missing. Ask which title to reserve.",
            "student_id": resolved_student_id,
            "book_id": None,
            "book": None,
            "hold": None,
            "matches": [],
        }
    if len(matches) > 1:
        return {
            "status": "ambiguous",
            "message": "Multiple matching titles found. Ask which one to reserve.",
            "student_id": resolved_student_id,
            "book_id": None,
            "book": None,
            "hold": None,
            "matches": [asdict(book) for book in matches],
        }

    book = matches[0]
    state = load_state()
    holds = state.get("holds", [])
    for hold in holds:
        if (
            hold.get("student_id") == resolved_student_id
            and hold.get("book_id") == book.book_id
            and hold.get("status") in {"Requested", "Ready"}
        ):
            hold_copy = dict(hold)
            hold_copy["book"] = asdict(book)
            return {
                "status": "exists",
                "message": "Hold already exists for this student.",
                "student_id": resolved_student_id,
                "book_id": book.book_id,
                "book": asdict(book),
                "hold": hold_copy,
                "matches": [],
            }

    hold_id = next_id("H", [hold.get("hold_id", "") for hold in holds])
    status = "Ready" if book.availability == "Available" else "Requested"
    now = datetime.now(timezone.utc)
    hold = {
        "hold_id": hold_id,
        "student_id": resolved_student_id,
        "book_id": book.book_id,
        "status": status,
        "notes": notes or "",
        "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    holds.append(hold)
    state["holds"] = holds
    save_state(state)
    hold_copy = dict(hold)
    hold_copy["book"] = asdict(book)
    message_text = (
        "This title is available now. Hold is marked Ready for pickup."
        if status == "Ready"
        else "Hold placed and queued."
    )
    return {
        "status": "created",
        "message": message_text,
        "student_id": resolved_student_id,
        "book_id": book.book_id,
        "book": asdict(book),
        "hold": hold_copy,
        "matches": [],
    }
