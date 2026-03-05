from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple


READ_HISTORY_RE = re.compile(
    r"\b("
    r"reading history|checkout history|borrowed|checked out|"
    r"what have they read|what has .* read|books they read|books they've read"
    r")\b",
    re.IGNORECASE,
)


def reading_history_requested(message: str) -> bool:
    if not message:
        return False
    return bool(READ_HISTORY_RE.search(message))


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def list_read_books(
    *,
    books: Dict[str, Any],
    loans: Iterable[Any],
    student_id: str,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    seen: Dict[str, Tuple[datetime | None, Any]] = {}
    for loan in loans:
        if loan.student_id != student_id:
            continue
        book = books.get(loan.book_id)
        if not book:
            continue
        checkout = _parse_date(getattr(loan, "checkout_date", ""))
        current = seen.get(loan.book_id)
        if current is None or (checkout and (current[0] is None or checkout > current[0])):
            seen[loan.book_id] = (checkout, loan)

    ordered = sorted(
        seen.items(),
        key=lambda item: item[1][0] or datetime.min,
        reverse=True,
    )
    results: List[Dict[str, Any]] = []
    for book_id, (checkout, loan) in ordered[:limit]:
        book = books.get(book_id)
        if not book:
            continue
        results.append(
            {
                "title": book.title,
                "author": book.author,
                "book": asdict(book),
                "last_checkout": checkout.strftime("%Y-%m-%d") if checkout else None,
                "loan": {
                    "transaction_id": getattr(loan, "transaction_id", ""),
                    "checkout_date": getattr(loan, "checkout_date", ""),
                    "return_date": getattr(loan, "return_date", ""),
                    "renewals": getattr(loan, "renewals", ""),
                    "recommended_by": getattr(loan, "recommended_by", ""),
                    "recommendation_reason": getattr(loan, "recommendation_reason", ""),
                    "student_feedback": getattr(loan, "student_feedback", ""),
                },
            }
        )
    return results
