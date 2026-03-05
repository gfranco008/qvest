from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from ..agent_state import load_state


SNAPSHOT_RE = re.compile(
    r"\b("
    r"snapshot|student snapshot|student summary|student stats|student overview|"
    r"reading stats|reading summary|profile snapshot"
    r")\b",
    re.IGNORECASE,
)


def student_snapshot_requested(message: str) -> bool:
    if not message:
        return False
    return bool(SNAPSHOT_RE.search(message))


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_student_snapshot(
    *,
    books: Dict[str, Any],
    loans: Iterable[Any],
    students: Dict[str, Any],
    student_id: str,
    state: Dict[str, Any] | None = None,
    recent_limit: int = 5,
    top_limit: int = 3,
) -> Dict[str, Any]:
    if student_id not in students:
        return {
            "student": None,
            "onboarding_profile": None,
            "stats": {},
            "generated_at": _now_iso(),
            "error": "Student not found",
        }

    snapshot_state = state or load_state()
    student = asdict(students[student_id])
    profile = snapshot_state.get("onboarding_profiles", {}).get(student_id)

    loan_rows: List[Tuple[Any, datetime | None]] = []
    for loan in loans:
        if getattr(loan, "student_id", "") != student_id:
            continue
        book = books.get(getattr(loan, "book_id", ""))
        if not book:
            continue
        checkout = _parse_date(getattr(loan, "checkout_date", ""))
        loan_rows.append((book, checkout))

    genre_counts = Counter(book.genre for book, _ in loan_rows if book.genre)
    author_counts = Counter(book.author for book, _ in loan_rows if book.author)
    series_counts = Counter(book.series for book, _ in loan_rows if book.series)
    level_counts = Counter(book.reading_level for book, _ in loan_rows if book.reading_level)

    total_loans = len(loan_rows)
    unique_books = len({book.book_id for book, _ in loan_rows})

    last_checkout = None
    if loan_rows:
        last_checkout = max((date for _, date in loan_rows if date), default=None)

    recent_sorted = sorted(
        loan_rows,
        key=lambda item: item[1] or datetime.min,
        reverse=True,
    )
    recent_books = [
        {
            "book_id": book.book_id,
            "title": book.title,
            "author": book.author,
            "checkout_date": checkout.strftime("%Y-%m-%d") if checkout else None,
        }
        for book, checkout in recent_sorted[:recent_limit]
    ]

    feedback_entries = [
        entry
        for entry in snapshot_state.get("feedback", [])
        if entry.get("student_id") == student_id
    ]
    feedback_ratings = [entry.get("rating") for entry in feedback_entries if entry.get("rating")]
    feedback_avg = (
        sum(feedback_ratings) / len(feedback_ratings) if feedback_ratings else None
    )

    holds_entries = [
        hold
        for hold in snapshot_state.get("holds", [])
        if hold.get("student_id") == student_id and hold.get("status") != "Canceled"
    ]

    stats = {
        "total_loans": total_loans,
        "unique_books": unique_books,
        "last_checkout": last_checkout.strftime("%Y-%m-%d") if last_checkout else None,
        "top_genres": [
            {"genre": genre, "count": count}
            for genre, count in genre_counts.most_common(top_limit)
        ],
        "top_authors": [
            {"author": author, "count": count}
            for author, count in author_counts.most_common(top_limit)
        ],
        "top_series": [
            {"series": series, "count": count}
            for series, count in series_counts.most_common(top_limit)
        ],
        "reading_level_mode": level_counts.most_common(1)[0][0] if level_counts else None,
        "recent_books": recent_books,
        "feedback": {
            "count": len(feedback_entries),
            "avg_rating": round(feedback_avg, 2) if feedback_avg is not None else None,
        },
        "holds": {
            "active": len(holds_entries),
        },
    }

    return {
        "student": student,
        "onboarding_profile": profile,
        "stats": stats,
        "generated_at": _now_iso(),
    }
