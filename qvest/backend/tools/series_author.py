from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple


SERIES_AUTHOR_RE = re.compile(
    r"\b("
    r"next in (the )?series|next book|next title|continue (the )?series|"
    r"series continuation|more(?: (?:books|titles))? by|other books by|"
    r"more by (this )?author|same author|more from (this )?author"
    r")\b",
    re.IGNORECASE,
)


def series_author_requested(message: str) -> bool:
    if not message:
        return False
    return bool(SERIES_AUTHOR_RE.search(message))


def _normalize(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"[^a-z0-9\s-]", " ", text.lower()).strip()


def _book_year(book: Any) -> int:
    value = getattr(book, "publication_year", None)
    if value is None and isinstance(book, dict):
        value = book.get("publication_year")
    if not value:
        return 0
    try:
        return int(str(value))
    except ValueError:
        return 0


def _match_title(message: str, books: Dict[str, Any]) -> Optional[Any]:
    text = _normalize(message)
    best: Tuple[int, Any] | None = None
    for book in books.values():
        title = getattr(book, "title", "")
        title_norm = _normalize(title)
        if title_norm and title_norm in text:
            score = len(title_norm)
            if best is None or score > best[0]:
                best = (score, book)
    return best[1] if best else None


def _match_series(message: str, series_list: Iterable[str]) -> Optional[str]:
    text = _normalize(message)
    best: Tuple[int, str] | None = None
    for series in series_list:
        series_norm = _normalize(series)
        if series_norm and series_norm in text:
            score = len(series_norm)
            if best is None or score > best[0]:
                best = (score, series)
    return best[1] if best else None


def _match_author(message: str, authors: Iterable[str]) -> Optional[str]:
    text = _normalize(message)
    best: Tuple[int, str] | None = None
    for author in authors:
        author_norm = _normalize(author)
        if author_norm and author_norm in text:
            score = len(author_norm)
            if best is None or score > best[0]:
                best = (score, author)
    if best:
        return best[1]

    by_match = re.search(r"\bby\s+([a-zA-Z .'-]{3,})", message or "")
    if not by_match:
        return None
    fragment = _normalize(by_match.group(1))
    if not fragment:
        return None
    for author in authors:
        author_norm = _normalize(author)
        if fragment in author_norm:
            score = len(author_norm)
            if best is None or score > best[0]:
                best = (score, author)
    return best[1] if best else None


def _series_books(
    books: Dict[str, Any],
    series: str,
    target_id: str | None,
) -> List[Dict[str, Any]]:
    series_norm = _normalize(series)
    candidates = [
        book
        for book in books.values()
        if _normalize(getattr(book, "series", "")) == series_norm
    ]
    candidates.sort(key=lambda book: (_book_year(book), getattr(book, "title", "")))
    if target_id:
        for idx, book in enumerate(candidates):
            if getattr(book, "book_id", "") == target_id:
                after = candidates[idx + 1 :]
                before = candidates[:idx]
                candidates = after + before
                break
    results = [
        asdict(book)
        for book in candidates
        if not target_id or getattr(book, "book_id", "") != target_id
    ]
    return results


def _author_books(
    books: Dict[str, Any],
    author: str,
    target_id: str | None,
) -> List[Dict[str, Any]]:
    author_norm = _normalize(author)
    candidates = [
        book
        for book in books.values()
        if _normalize(getattr(book, "author", "")) == author_norm
    ]
    candidates.sort(key=lambda book: (-_book_year(book), getattr(book, "title", "")))
    results = [
        asdict(book)
        for book in candidates
        if not target_id or getattr(book, "book_id", "") != target_id
    ]
    return results


def find_series_author_matches(
    *,
    books: Dict[str, Any],
    message: str,
    limit: int = 6,
) -> Dict[str, Any]:
    if not message:
        return {
            "mode": None,
            "match_source": None,
            "query": None,
            "series": None,
            "author": None,
            "target_book": None,
            "results": [],
            "total_results": 0,
        }

    target_book = _match_title(message, books)
    target_id = getattr(target_book, "book_id", None) if target_book else None
    series_list = {
        getattr(book, "series", "")
        for book in books.values()
        if getattr(book, "series", "")
    }
    author_list = {
        getattr(book, "author", "")
        for book in books.values()
        if getattr(book, "author", "")
    }

    mode = None
    match_source = None
    series = None
    author = None
    results: List[Dict[str, Any]] = []

    if target_book:
        match_source = "title"
        series = getattr(target_book, "series", "") or None
        author = getattr(target_book, "author", "") or None
        if series:
            mode = "series"
            results = _series_books(books, series, target_id)
        if not results and author:
            mode = "author"
            results = _author_books(books, author, target_id)
    if not results:
        series_match = _match_series(message, series_list)
        if series_match:
            mode = "series"
            match_source = "series"
            series = series_match
            results = _series_books(books, series, target_id)
    if not results:
        author_match = _match_author(message, author_list)
        if author_match:
            mode = "author"
            match_source = "author"
            author = author_match
            results = _author_books(books, author, target_id)

    return {
        "mode": mode,
        "match_source": match_source,
        "query": series or author or (getattr(target_book, "title", None) if target_book else None),
        "series": series,
        "author": author,
        "target_book": asdict(target_book) if target_book else None,
        "results": results[:limit],
        "total_results": len(results),
    }
