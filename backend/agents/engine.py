from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal

from ..agent_state import load_state, new_event_id, record_observability, save_state
from ..chat_utils import build_recommendations, extract_student_id, wants_recommendations
from ..data_loader import DATA_DIR
from ..scoring import score_book
from ..tools import action_detect, call_tool, signal_detect
from .utils import (
    build_continuation_recommendations,
    default_reason,
    extract_filters,
    normalize,
    now_iso,
)


@dataclass(frozen=True)
class AgentCapabilities:
    mode: Literal["chat", "concierge"]
    intents: Dict[str, bool]
    signals: Dict[str, bool]
    use_filters: bool
    availability_limit: int
    recommendation_style: Literal["chat", "concierge"]


CAPABILITIES_PATH = DATA_DIR / "agent_capabilities.json"

DEFAULT_CAPABILITIES: Dict[str, AgentCapabilities] = {
    "chat": AgentCapabilities(
        mode="chat",
        intents={
            "availability": True,
            "reading_history": True,
            "series_author": True,
            "student_snapshot": True,
            "reserve_hold": True,
            "onboard_from_history": True,
            "recommendations": True,
        },
        signals={
            "onboard_save_intent": True,
            "profile_query": True,
        },
        use_filters=False,
        availability_limit=5,
        recommendation_style="chat",
    ),
    "concierge": AgentCapabilities(
        mode="concierge",
        intents={
            "availability": True,
            "reading_history": False,
            "series_author": True,
            "student_snapshot": False,
            "reserve_hold": False,
            "onboard_from_history": True,
            "recommendations": True,
        },
        signals={
            "onboard_save_intent": True,
            "profile_query": False,
        },
        use_filters=True,
        availability_limit=200,
        recommendation_style="concierge",
    ),
}


def _merge_capability(
    base: AgentCapabilities,
    overrides: Dict[str, Any],
) -> AgentCapabilities:
    intents = dict(base.intents)
    intents.update(overrides.get("intents", {}) or {})

    signals = dict(base.signals)
    signals.update(overrides.get("signals", {}) or {})

    use_filters = overrides.get("use_filters", base.use_filters)
    availability_limit = overrides.get("availability_limit", base.availability_limit)
    recommendation_style = overrides.get(
        "recommendation_style", base.recommendation_style
    )

    return AgentCapabilities(
        mode=base.mode,
        intents=intents,
        signals=signals,
        use_filters=bool(use_filters),
        availability_limit=int(availability_limit),
        recommendation_style=recommendation_style,
    )


def load_capabilities() -> Dict[str, AgentCapabilities]:
    capabilities = dict(DEFAULT_CAPABILITIES)
    if not CAPABILITIES_PATH.exists():
        return capabilities
    try:
        payload = json.loads(CAPABILITIES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return capabilities

    if not isinstance(payload, dict):
        return capabilities

    for mode, base in DEFAULT_CAPABILITIES.items():
        overrides = payload.get(mode)
        if isinstance(overrides, dict):
            capabilities[mode] = _merge_capability(base, overrides)
    return capabilities


@dataclass
class AgentResult:
    message: str
    student_id: str | None
    needs_student_id: bool
    filters: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    available_books: List[Dict[str, Any]]
    reading_history: List[Dict[str, Any]]
    onboarding_profile: Dict[str, Any] | None
    existing_profile: Dict[str, Any] | None
    onboarding_saved: bool
    onboarding_pending: bool
    hold_result: Dict[str, Any] | None
    snapshot: Dict[str, Any] | None
    continuation_recs: List[Dict[str, Any]]
    continuation_note: str | None
    intents: Dict[str, bool]
    signals: Dict[str, bool]
    tools_called: List[str]
    counts: Dict[str, int]

    def context_payload(self) -> Dict[str, Any]:
        return {
            "student_id": self.student_id,
            "needs_student_id": self.needs_student_id,
            "filters": self.filters,
            "available_books": self.available_books,
            "reading_history": self.reading_history,
            "hold_result": self.hold_result,
            "continuation_recs": self.continuation_recs,
            "continuation_note": self.continuation_note,
            "snapshot": self.snapshot,
            "onboarding_profile": self.onboarding_profile,
            "existing_profile": self.existing_profile,
            "onboarding_saved": self.onboarding_saved,
            "onboarding_pending": self.onboarding_pending,
            "recommendations": self.recommendations,
        }


def run_agent(
    *,
    mode: Literal["chat", "concierge"],
    message: str,
    student_id: str | None,
    history_texts: Iterable[str] | None = None,
    availability_only: bool = False,
    limit: int = 5,
    books: Dict[str, Any],
    students: Dict[str, Any],
    loans: List[Any],
    recommender: Any,
) -> AgentResult:
    message = message or ""
    capabilities = load_capabilities()
    cap = capabilities.get(mode, DEFAULT_CAPABILITIES[mode])
    history_texts_list = list(history_texts or [])

    state = load_state()
    resolved_student_id = student_id
    if not resolved_student_id and history_texts_list:
        resolved_student_id = extract_student_id(history_texts_list)

    existing_profile = (
        state.get("onboarding_profiles", {}).get(resolved_student_id)
        if resolved_student_id
        else None
    )

    book_genres = sorted({book.genre for book in books.values() if book.genre})

    filters: Dict[str, Any] = {}
    if cap.use_filters:
        filters = extract_filters(message, existing_profile, book_genres)
        if availability_only:
            filters["availability"] = "Available"

    tokens = [token for token in normalize(message).split() if token]

    tools_called: List[str] = []

    def _call_tool(name: str, **kwargs: Any) -> Any:
        tools_called.append(name)
        return call_tool(name, **kwargs)

    availability_hint = availability_only if cap.intents.get("availability") else False
    if cap.intents.get("availability") and action_detect("availability", message):
        availability_hint = True

    continuation_hint = cap.intents.get("series_author") and action_detect(
        "series_author", message
    )
    history_hint = cap.intents.get("reading_history") and action_detect(
        "reading_history", message
    )
    snapshot_hint = cap.intents.get("student_snapshot") and action_detect(
        "student_snapshot", message
    )
    hold_hint = cap.intents.get("reserve_hold") and action_detect(
        "reserve_hold", message
    )
    onboarding_hint = cap.intents.get("onboard_from_history") and action_detect(
        "onboard_from_history", message
    )
    save_onboarding = cap.signals.get("onboard_save_intent") and signal_detect(
        "onboard_save_intent", message
    )
    profile_query = cap.signals.get("profile_query") and "profile" in message.lower()

    if (
        not history_hint
        and resolved_student_id
        and cap.intents.get("reading_history")
        and history_texts_list
    ):
        recent = history_texts_list[-6:]
        for text in reversed(recent[:-1] if len(recent) > 1 else recent):
            if action_detect("reading_history", text):
                history_hint = True
                break
    if (
        not snapshot_hint
        and resolved_student_id
        and cap.intents.get("student_snapshot")
        and history_texts_list
    ):
        recent = history_texts_list[-6:]
        for text in reversed(recent[:-1] if len(recent) > 1 else recent):
            if action_detect("student_snapshot", text):
                snapshot_hint = True
                break
    if (
        not onboarding_hint
        and resolved_student_id
        and cap.intents.get("onboard_from_history")
        and history_texts_list
    ):
        recent = history_texts_list[-6:]
        for text in reversed(recent[:-1] if len(recent) > 1 else recent):
            if action_detect("onboard_from_history", text):
                onboarding_hint = True
                break
    if (
        not hold_hint
        and resolved_student_id
        and cap.intents.get("reserve_hold")
        and history_texts_list
    ):
        recent = history_texts_list[-6:]
        for text in reversed(recent[:-1] if len(recent) > 1 else recent):
            if action_detect("reserve_hold", text):
                hold_hint = True
                break

    if save_onboarding and not onboarding_hint:
        onboarding_hint = True
    if profile_query and not existing_profile and not onboarding_hint:
        onboarding_hint = True

    needs_student_id = False
    recommendations: List[Dict[str, Any]] = []
    available_books: List[Dict[str, Any]] = []
    available_candidates: set[str] | None = None
    continuation_recs: List[Dict[str, Any]] = []
    continuation_note: str | None = None
    reading_history: List[Dict[str, Any]] = []
    hold_result: Dict[str, Any] | None = None
    snapshot: Dict[str, Any] | None = None
    scored_candidates = 0

    if availability_hint:
        available_books = _call_tool(
            "availability",
            books=books,
            message=message,
            genres=book_genres,
            limit=cap.availability_limit,
        )
        if cap.use_filters:
            available_candidates = {book["book_id"] for book in available_books}

    if hold_hint:
        hold_result = _call_tool(
            "reserve_hold",
            books=books,
            students=students,
            student_id=resolved_student_id,
            message=message,
        )
        if hold_result.get("status") == "needs_student_id":
            needs_student_id = True

    if history_hint:
        if resolved_student_id:
            reading_history = _call_tool(
                "reading_history",
                books=books,
                loans=loans,
                student_id=resolved_student_id,
                limit=12,
            )
        else:
            needs_student_id = True

    onboarding_profile = None
    onboarding_saved = False
    onboarding_pending = False
    if onboarding_hint:
        if resolved_student_id:
            onboarding_result = _call_tool(
                "onboard_from_history",
                books=books,
                loans=loans,
                student_id=resolved_student_id,
            )
            onboarding_profile = onboarding_result.get("profile", {}) or None
            if onboarding_profile:
                existing_profile = state.get("onboarding_profiles", {}).get(
                    resolved_student_id
                )
                should_save = save_onboarding or not existing_profile
                if should_save:
                    profile = dict(existing_profile or {})
                    profile.update(onboarding_profile)
                    profile.setdefault("created_at", now_iso())
                    profile["updated_at"] = now_iso()
                    state.setdefault("onboarding_profiles", {})[
                        resolved_student_id
                    ] = profile
                    save_state(state)
                    onboarding_saved = True
                    existing_profile = profile
                else:
                    onboarding_pending = True
        else:
            needs_student_id = True

    if snapshot_hint:
        if resolved_student_id:
            snapshot = _call_tool(
                "student_snapshot",
                books=books,
                loans=loans,
                students=students,
                student_id=resolved_student_id,
                state=state,
            )
        else:
            needs_student_id = True

    def _book_matches_filters(book: Dict[str, Any]) -> bool:
        if available_candidates is not None and book.get("book_id") not in available_candidates:
            return False
        if filters.get("availability") and book.get("availability") != filters["availability"]:
            return False
        if filters.get("genres") and book.get("genre") not in filters["genres"]:
            return False
        if filters.get("reading_level") and book.get("reading_level") != filters["reading_level"]:
            return False
        if filters.get("language") and book.get("language") != filters["language"]:
            return False
        return True

    if continuation_hint:
        continuation_result = _call_tool(
            "series_author",
            books=books,
            message=message,
            limit=limit,
        )
        continuation_recs = build_continuation_recommendations(
            continuation_result, limit=limit
        )
        if continuation_recs:
            if availability_hint:
                continuation_recs = [
                    rec
                    for rec in continuation_recs
                    if rec["book"].get("availability") == "Available"
                ]
            if cap.use_filters:
                continuation_recs = [
                    rec
                    for rec in continuation_recs
                    if _book_matches_filters(rec.get("book", {}))
                ]
        if cap.use_filters:
            if continuation_recs:
                continuation_note = "Series/author continuation matches were found in the catalog."
            else:
                continuation_note = "No series/author continuation matches found in the catalog."

    wants_recs = cap.intents.get("recommendations") and wants_recommendations(message)

    if cap.recommendation_style == "concierge":
        if continuation_hint:
            recommendations = continuation_recs
        elif resolved_student_id:
            recs = recommender.recommend(resolved_student_id, k=limit)
            for rec in recs:
                book = books.get(rec.book_id)
                if not book:
                    continue
                book_data = asdict(book)
                if not _book_matches_filters(book_data):
                    continue
                similar_book = books.get(rec.similar_to) if rec.similar_to else None
                recommendations.append(
                    {
                        "book": book_data,
                        "score": round(rec.score, 3),
                        "similar_to": asdict(similar_book) if similar_book else None,
                        "reason": default_reason(
                            book_data, asdict(similar_book) if similar_book else None
                        ),
                    }
                )

        if len(recommendations) < limit and not continuation_hint:
            exclude_ids = {rec["book"]["book_id"] for rec in recommendations}
            scored: List[tuple[float, Dict[str, Any]]] = []
            for book in books.values():
                if available_candidates is not None and book.book_id not in available_candidates:
                    continue
                if book.book_id in exclude_ids:
                    continue
                book_data = asdict(book)
                score = score_book(
                    book_data,
                    tokens,
                    filters,
                    weight_reading_level=2.5,
                    weight_genre=3.0,
                    weight_availability=0.5,
                    weight_token=1.0,
                )
                if score is None:
                    continue
                score += recommender._book_counts.get(book.book_id, 0) * 0.05
                scored.append((score, book_data))

            scored_candidates = len(scored)
            scored.sort(key=lambda item: item[0], reverse=True)
            for score, book_data in scored[: limit - len(recommendations)]:
                recommendations.append(
                    {
                        "book": book_data,
                        "score": round(score, 3),
                        "similar_to": None,
                        "reason": default_reason(book_data, None),
                    }
                )
    else:
        if continuation_hint:
            recommendations = continuation_recs
        elif wants_recs:
            if resolved_student_id:
                recommendations = build_recommendations(
                    student_id=resolved_student_id,
                    k=5,
                    books=books,
                    recommender=recommender,
                    reason_fn=default_reason,
                )
                if availability_hint:
                    recommendations = [
                        rec
                        for rec in recommendations
                        if rec["book"].get("availability") == "Available"
                    ]
                    if len(recommendations) < 3 and available_books:
                        existing = {rec["book"]["book_id"] for rec in recommendations}
                        for book in available_books:
                            if book["book_id"] in existing:
                                continue
                            recommendations.append(
                                {
                                    "book": book,
                                    "score": 0.0,
                                    "similar_to": None,
                                    "reason": default_reason(book, None),
                                }
                            )
            else:
                needs_student_id = True
                if availability_hint and available_books:
                    recommendations = [
                        {
                            "book": book,
                            "score": 0.0,
                            "similar_to": None,
                            "reason": default_reason(book, None),
                        }
                        for book in available_books
                    ]

    if onboarding_hint and not resolved_student_id:
        needs_student_id = True

    intents = {
        "availability": bool(availability_hint),
        "reading_history": bool(history_hint),
        "series_author": bool(continuation_hint),
        "student_snapshot": bool(snapshot_hint),
        "reserve_hold": bool(hold_hint),
        "onboard_from_history": bool(onboarding_hint),
        "recommendations": bool(
            cap.recommendation_style == "concierge" or wants_recs or continuation_hint
        ),
    }
    signals = {
        "onboard_save_intent": bool(save_onboarding),
        "profile_query": bool(profile_query),
    }
    counts = {
        "available_candidates": len(available_candidates) if available_candidates is not None else 0,
        "available_books": len(available_books),
        "recommendations": len(recommendations),
        "reading_history": len(reading_history),
        "continuation_results": len(continuation_recs),
        "fallback_candidates": scored_candidates,
    }

    record_observability(
        {
            "event_id": new_event_id(),
            "created_at": now_iso(),
            "mode": mode,
            "message": message[:200],
            "student_id": resolved_student_id,
            "intents": intents,
            "signals": signals,
            "tools_called": tools_called,
            "filters": filters,
            "counts": counts,
        }
    )

    return AgentResult(
        message=message,
        student_id=resolved_student_id,
        needs_student_id=needs_student_id,
        filters=filters,
        recommendations=recommendations,
        available_books=available_books,
        reading_history=reading_history,
        onboarding_profile=onboarding_profile,
        existing_profile=existing_profile,
        onboarding_saved=onboarding_saved,
        onboarding_pending=onboarding_pending,
        hold_result=hold_result,
        snapshot=snapshot,
        continuation_recs=continuation_recs,
        continuation_note=continuation_note,
        intents=intents,
        signals=signals,
        tools_called=tools_called,
        counts=counts,
    )
