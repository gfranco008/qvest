from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Dict, Iterable, List

from ..scoring import score_book

AVAILABILITY_RE = re.compile(r"\b(available|in stock|on shelf|available now)\b", re.IGNORECASE)


def availability_requested(message: str) -> bool:
    if not message:
        return False
    return bool(AVAILABILITY_RE.search(message))


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s-]", " ", text.lower()).strip()


def _extract_filters(message: str | None, genres: Iterable[str]) -> Dict[str, Any]:
    if not message:
        return {}
    text = _normalize(message)
    filters: Dict[str, Any] = {}

    level_match = re.search(r"(\d)\s*-\s*(\d)", text)
    if level_match:
        filters["reading_level"] = f"{level_match.group(1)}-{level_match.group(2)}"

    if "spanish" in text:
        filters["language"] = "Spanish"
    if "english" in text:
        filters["language"] = "English"

    genre_matches = [genre for genre in genres if genre.lower() in text]
    if genre_matches:
        filters["genres"] = genre_matches

    return filters


def list_available_books(
    books: Dict[str, Any],
    *,
    message: str | None = None,
    genres: Iterable[str] | None = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    available = []
    genre_list = list(genres or {book.genre for book in books.values() if book.genre})
    filters = _extract_filters(message, genre_list)
    tokens = [token for token in _normalize(message or "").split() if token]

    for book in books.values():
        book_data = asdict(book)
        if book_data.get("availability") != "Available":
            continue
        score = score_book(
            book_data,
            tokens,
            filters,
            weight_reading_level=2.0,
            weight_language=1.5,
            weight_genre=2.5,
            weight_token=1.0,
        )
        if score is None:
            continue
        available.append((score, book_data))

    available.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in available[:limit]]
