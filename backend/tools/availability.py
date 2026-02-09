from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Dict, Iterable, List


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


def _score_book(book: Dict[str, Any], tokens: List[str], filters: Dict[str, Any]) -> float:
    score = 0.0
    if filters.get("reading_level") and book.get("reading_level") == filters["reading_level"]:
        score += 2.0
    if filters.get("language") and book.get("language") == filters["language"]:
        score += 1.5
    if filters.get("genres") and book.get("genre") in filters["genres"]:
        score += 2.5

    searchable = " ".join(
        [
            book.get("title", ""),
            book.get("author", ""),
            book.get("keywords", ""),
            book.get("subject_tags", ""),
            book.get("series", ""),
            book.get("audience", ""),
            book.get("format", ""),
            book.get("genre", ""),
        ]
    )
    haystack = _normalize(searchable)
    for token in tokens:
        if token and token in haystack:
            score += 1.0
    return score


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
        if filters.get("language") and book_data.get("language") != filters["language"]:
            continue
        if filters.get("reading_level") and book_data.get("reading_level") != filters["reading_level"]:
            continue
        if filters.get("genres") and book_data.get("genre") not in filters["genres"]:
            continue
        score = _score_book(book_data, tokens, filters)
        available.append((score, book_data))

    available.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in available[:limit]]
