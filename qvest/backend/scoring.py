from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

DEFAULT_SEARCH_FIELDS = (
    "title",
    "author",
    "keywords",
    "subject_tags",
    "series",
    "audience",
    "format",
    "genre",
)


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"[^a-z0-9\s-]", " ", text.lower()).strip()


def score_book(
    book: Dict[str, Any],
    tokens: Iterable[str],
    filters: Dict[str, Any],
    *,
    weight_reading_level: float = 0.0,
    weight_language: float = 0.0,
    weight_genre: float = 0.0,
    weight_availability: float = 0.0,
    weight_token: float = 1.0,
    availability_value: str = "Available",
    require_filters: bool = True,
    search_fields: Iterable[str] = DEFAULT_SEARCH_FIELDS,
) -> float | None:
    if require_filters:
        if filters.get("availability") and book.get("availability") != filters["availability"]:
            return None
        if filters.get("language") and book.get("language") != filters["language"]:
            return None
        if filters.get("genres") and book.get("genre") not in filters["genres"]:
            return None

    score = 0.0
    if (
        weight_reading_level
        and filters.get("reading_level")
        and book.get("reading_level") == filters["reading_level"]
    ):
        score += weight_reading_level
    if weight_language and filters.get("language") and book.get("language") == filters["language"]:
        score += weight_language
    if weight_genre and filters.get("genres") and book.get("genre") in filters["genres"]:
        score += weight_genre
    if weight_availability and book.get("availability") == availability_value:
        score += weight_availability

    searchable = " ".join(book.get(field, "") for field in search_fields)
    haystack = normalize_text(searchable)
    for token in tokens:
        if token and token in haystack:
            score += weight_token
    return score
