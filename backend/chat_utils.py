from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Dict, Iterable, List

DRIVER_LABELS = {
    "history_similarity": "Borrowing history match",
    "collaborative_similarity": "Borrowing pattern similarity",
    "content_similarity": "Content similarity",
    "profile_fit": "Student profile fit",
    "popularity": "Popularity",
    "availability_penalty": "Availability penalty",
}


STUDENT_ID_RE = re.compile(r"\bS\d{4}\b", re.IGNORECASE)


def extract_student_id(texts: Iterable[str]) -> str | None:
    for text in reversed(list(texts)):
        if not text:
            continue
        match = STUDENT_ID_RE.search(text)
        if match:
            return match.group(0).upper()
    return None


def wants_recommendations(message: str) -> bool:
    text = (message or "").lower()
    triggers = [
        "recommend",
        "suggest",
        "read alike",
        "read-alike",
        "readalike",
        "what should i read",
        "book suggestions",
        "book recommendation",
        "good books",
        "titles for",
    ]
    return any(trigger in text for trigger in triggers)


def build_recommendations(
    *,
    student_id: str,
    k: int,
    books: Dict[str, Any],
    recommender: Any,
    reason_fn: Any,
) -> List[Dict[str, Any]]:
    recs = recommender.recommend(student_id, k=k)
    response: List[Dict[str, Any]] = []

    for rec in recs:
        book = books.get(rec.book_id)
        if not book:
            continue
        similar_book = books.get(rec.similar_to) if rec.similar_to else None
        driver_label = DRIVER_LABELS.get(rec.driver, rec.driver)
        reason = reason_fn(
            asdict(book), asdict(similar_book) if similar_book else None
        )
        if driver_label:
            reason = f"{reason} (Primary signal: {driver_label})"
        response.append(
            {
                "book": asdict(book),
                "score": round(rec.score, 3),
                "similar_to": asdict(similar_book) if similar_book else None,
                "reason": reason,
                "driver": rec.driver,
                "driver_label": driver_label,
                "signals": rec.signals,
            }
        )

    return response
