from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, Iterable, List


ONBOARD_RE = re.compile(
    r"\b(onboard|onboarding|initialize profile|profile from history|use reading history)\b",
    re.IGNORECASE,
)

ONBOARD_SAVE_RE = re.compile(
    r"\b(save|apply|update profile|use this profile|store profile)\b",
    re.IGNORECASE,
)


def onboarding_requested(message: str) -> bool:
    if not message:
        return False
    return bool(ONBOARD_RE.search(message))


def onboarding_save_requested(message: str) -> bool:
    if not message:
        return False
    return bool(ONBOARD_SAVE_RE.search(message))


def _split_tags(value: str) -> List[str]:
    if not value:
        return []
    normalized = value.replace(",", ";")
    return [item.strip() for item in normalized.split(";") if item.strip()]


def build_onboarding_from_history(
    *,
    books: Dict[str, Any],
    loans: Iterable[Any],
    student_id: str,
    genre_limit: int = 2,
    interest_limit: int = 4,
) -> Dict[str, Any]:
    read_books = [
        books[loan.book_id]
        for loan in loans
        if loan.student_id == student_id and loan.book_id in books
    ]

    if not read_books:
        return {
            "student_id": student_id,
            "profile": {},
            "summary": "No reading history available to initialize onboarding.",
            "counts": {"total_loans": 0, "unique_books": 0},
        }

    genre_counts = Counter(book.genre for book in read_books if book.genre)
    level_counts = Counter(book.reading_level for book in read_books if book.reading_level)
    keyword_counts: Counter[str] = Counter()

    for book in read_books:
        keyword_counts.update(_split_tags(book.keywords))
        keyword_counts.update(_split_tags(book.subject_tags))

    preferred_genres = [genre for genre, _ in genre_counts.most_common(genre_limit)]
    reading_level = level_counts.most_common(1)[0][0] if level_counts else ""
    interests = [kw for kw, _ in keyword_counts.most_common(interest_limit)]

    profile = {
        "preferred_genres": ";".join(preferred_genres),
        "reading_level": reading_level,
        "interests": ";".join(interests),
        "notes": "Generated from reading history.",
        "source": "reading_history",
    }

    summary_parts = []
    if preferred_genres:
        summary_parts.append(f"Top genres: {', '.join(preferred_genres)}")
    if reading_level:
        summary_parts.append(f"Typical level: {reading_level}")
    if interests:
        summary_parts.append(f"Interest tags: {', '.join(interests)}")

    return {
        "student_id": student_id,
        "profile": profile,
        "summary": " · ".join(summary_parts) or "Profile generated from history.",
        "counts": {
            "total_loans": len(read_books),
            "unique_books": len({book.book_id for book in read_books}),
        },
    }
