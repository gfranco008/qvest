from __future__ import annotations

import os
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from openai import OpenAI

from ..agent_state import load_state, save_state
from . import prompts
from .models import ConciergeRequest, FeedbackRequest, HoldRequest, OnboardingRequest
from .utils import (
    default_reason,
    extract_filters,
    format_concierge_reply,
    build_continuation_recommendations,
    next_id,
    normalize,
    now_iso,
    score_book,
)
from ..tools import call_tool, tool_detect


def _get_openai_client_optional() -> OpenAI | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None
    return OpenAI()


def create_router(
    *,
    books: Dict[str, Any],
    students: Dict[str, Any],
    loans: List[Any],
    recommender: Any,
) -> APIRouter:
    router = APIRouter(prefix="/agents")
    book_genres = sorted({book.genre for book in books.values() if book.genre})

    @router.post("/concierge")
    async def concierge(payload: ConciergeRequest) -> Dict[str, Any]:
        if payload.student_id and payload.student_id not in students:
            raise HTTPException(status_code=404, detail="Student not found")

        state = load_state()
        onboarding_profile = (
            state.get("onboarding_profiles", {}).get(payload.student_id or "", None)
        )
        filters = extract_filters(payload.message, onboarding_profile, book_genres)
        if payload.availability_only:
            filters["availability"] = "Available"

        tokens = [token for token in normalize(payload.message).split() if token]
        recommendations: List[Dict[str, Any]] = []
        continuation_hint = tool_detect("series_author", payload.message)

        availability_hint = payload.availability_only or tool_detect(
            "availability", payload.message
        )
        onboarding_hint = tool_detect("onboard_from_history", payload.message)
        save_onboarding = tool_detect("onboard_save_intent", payload.message)
        if save_onboarding and not onboarding_hint:
            onboarding_hint = True
        available_candidates = None
        if availability_hint:
            available_candidates = {
                book["book_id"]
                for book in call_tool(
                    "availability",
                    books=books,
                    message=payload.message,
                    genres=book_genres,
                    limit=200,
                )
            }

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
        continuation_recs: List[Dict[str, Any]] = []
        continuation_note = ""
        if continuation_hint:
            continuation_result = call_tool(
                "series_author",
                books=books,
                message=payload.message,
                limit=payload.limit,
            )
            continuation_recs = build_continuation_recommendations(
                continuation_result, limit=payload.limit
            )
            if continuation_recs:
                continuation_recs = [
                    rec
                    for rec in continuation_recs
                    if _book_matches_filters(rec.get("book", {}))
                ]
            if not continuation_recs:
                continuation_note = "No series/author continuation matches found in the catalog."
            else:
                continuation_note = "Series/author continuation matches were found in the catalog."
            recommendations = continuation_recs

        onboarding_profile = None
        onboarding_saved = False
        onboarding_pending = False
        if onboarding_hint and payload.student_id:
            onboarding_result = call_tool(
                "onboard_from_history",
                books=books,
                loans=loans,
                student_id=payload.student_id,
            )
            onboarding_profile = onboarding_result.get("profile", {}) or None
            if onboarding_profile:
                state = load_state()
                existing_profile = state.get("onboarding_profiles", {}).get(payload.student_id)
                should_save = save_onboarding or not existing_profile
                if should_save:
                    profile = dict(existing_profile or {})
                    profile.update(onboarding_profile)
                    profile.setdefault("created_at", now_iso())
                    profile["updated_at"] = now_iso()
                    state.setdefault("onboarding_profiles", {})[payload.student_id] = profile
                    save_state(state)
                    onboarding_saved = True
                else:
                    onboarding_pending = True

        if payload.student_id and not continuation_hint:
            recs = recommender.recommend(payload.student_id, k=payload.limit)
            for rec in recs:
                book = books.get(rec.book_id)
                if not book:
                    continue
                book_data = asdict(book)
                if available_candidates is not None and book_data["book_id"] not in available_candidates:
                    continue
                if filters.get("availability") and book_data["availability"] != filters["availability"]:
                    continue
                if filters.get("genres") and book_data["genre"] not in filters["genres"]:
                    continue
                if filters.get("reading_level") and book_data["reading_level"] != filters["reading_level"]:
                    continue
                if filters.get("language") and book_data["language"] != filters["language"]:
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

        if len(recommendations) < payload.limit and not continuation_hint:
            exclude_ids = {rec["book"]["book_id"] for rec in recommendations}
            scored: List[tuple[float, Dict[str, Any]]] = []
            for book in books.values():
                if available_candidates is not None and book.book_id not in available_candidates:
                    continue
                if book.book_id in exclude_ids:
                    continue
                book_data = asdict(book)
                score = score_book(book_data, tokens, filters)
                if score is None:
                    continue
                score += recommender._book_counts.get(book.book_id, 0) * 0.05
                scored.append((score, book_data))

            scored.sort(key=lambda item: item[0], reverse=True)
            for score, book_data in scored[: payload.limit - len(recommendations)]:
                recommendations.append(
                    {
                        "book": book_data,
                        "score": round(score, 3),
                        "similar_to": None,
                        "reason": default_reason(book_data, None),
                    }
                )

        client = _get_openai_client_optional()
        reply = format_concierge_reply(
            payload.message, recommendations, use_llm=bool(client)
        )
        if client:
            summary_lines = [
                (
                    f"{rec['book']['title']} by {rec['book']['author']} "
                    f"({rec['book']['genre']}, level {rec['book']['reading_level']}) "
                    f"- {rec['book']['availability']}"
                )
                for rec in recommendations
            ]
            profile_note = ""
            if onboarding_profile:
                profile_note = (
                    "Onboarding preferences: "
                    f"{onboarding_profile.get('preferred_genres', 'n/a')}; "
                    f"interests {onboarding_profile.get('interests', 'n/a')}; "
                    f"reading level {onboarding_profile.get('reading_level', 'n/a')}."
                )
            if continuation_note:
                profile_note = (profile_note + " " if profile_note else "") + continuation_note
            if onboarding_hint and not payload.student_id:
                profile_note = (profile_note + " " if profile_note else "") + (
                    "Student_id is missing. Ask for it before saving onboarding."
                )
            if onboarding_profile:
                summary_parts = []
                if onboarding_profile.get("preferred_genres"):
                    summary_parts.append(
                        f"Genres: {onboarding_profile['preferred_genres']}"
                    )
                if onboarding_profile.get("reading_level"):
                    summary_parts.append(f"Level: {onboarding_profile['reading_level']}")
                if onboarding_profile.get("interests"):
                    summary_parts.append(f"Interests: {onboarding_profile['interests']}")
                summary = " · ".join(summary_parts) if summary_parts else "Profile generated."
                decision_note = ""
                if onboarding_saved:
                    decision_note = " Saved."
                elif onboarding_pending:
                    decision_note = " A profile already exists; ask to save changes."
                profile_note = (profile_note + " " if profile_note else "") + (
                    f"Onboarding profile summary: {summary}.{decision_note}"
                )
            system_prompt = prompts.CONCIERGE_SYSTEM_PROMPT
            user_prompt = prompts.CONCIERGE_USER_TEMPLATE.format(
                request=payload.message,
                profile_note=profile_note,
                recommendations="\n".join(summary_lines),
            )
            model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
            try:
                response = client.responses.create(
                    model=model,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                reply = response.output_text
            except Exception:
                reply = format_concierge_reply(
                    payload.message, recommendations, use_llm=False
                )

        return {
            "reply": reply,
            "recommendations": recommendations,
            "filters": filters,
            "onboarding_profile": onboarding_profile,
            "onboarding_saved": onboarding_saved,
            "onboarding_pending": onboarding_pending,
        }

    @router.get("/onboarding/{student_id}")
    async def onboarding_profile(student_id: str) -> Dict[str, Any]:
        if student_id not in students:
            raise HTTPException(status_code=404, detail="Student not found")
        state = load_state()
        profile = state.get("onboarding_profiles", {}).get(student_id)
        student = asdict(students[student_id])
        merged = dict(student)
        if profile:
            merged.update(profile)
        return {"student": student, "profile": profile, "merged": merged}

    @router.post("/onboarding")
    async def onboarding_update(payload: OnboardingRequest) -> Dict[str, Any]:
        if payload.student_id not in students:
            raise HTTPException(status_code=404, detail="Student not found")
        state = load_state()
        profile = dict(state.get("onboarding_profiles", {}).get(payload.student_id, {}))
        updates = {
            "interests": payload.interests,
            "preferred_genres": payload.preferred_genres,
            "reading_level": payload.reading_level,
            "goals": payload.goals,
            "avoid_topics": payload.avoid_topics,
            "notes": payload.notes,
        }
        for key, value in updates.items():
            if value is not None and str(value).strip():
                profile[key] = value.strip()
        profile.setdefault("created_at", now_iso())
        profile["updated_at"] = now_iso()
        state.setdefault("onboarding_profiles", {})[payload.student_id] = profile
        save_state(state)
        student = asdict(students[payload.student_id])
        merged = dict(student)
        merged.update(profile)
        return {"student": student, "profile": profile, "merged": merged}

    @router.get("/snapshot/{student_id}")
    async def student_snapshot(student_id: str) -> Dict[str, Any]:
        if student_id not in students:
            raise HTTPException(status_code=404, detail="Student not found")
        state = load_state()
        return call_tool(
            "student_snapshot",
            books=books,
            loans=loans,
            students=students,
            student_id=student_id,
            state=state,
        )

    @router.get("/availability")
    async def agent_availability(
        genre: str | None = None,
        availability: str | None = None,
        reading_level: str | None = None,
        language: str | None = None,
        limit: int = Query(60, ge=1, le=200),
    ) -> Dict[str, Any]:
        items = [asdict(book) for book in books.values()]
        if genre:
            items = [book for book in items if book["genre"] == genre]
        if availability:
            items = [book for book in items if book["availability"] == availability]
        if reading_level:
            items = [book for book in items if book["reading_level"] == reading_level]
        if language:
            items = [book for book in items if book["language"] == language]
        return {"results": items[:limit], "total": len(items)}

    @router.get("/holds")
    async def agent_holds(student_id: str | None = None) -> Dict[str, Any]:
        state = load_state()
        holds = state.get("holds", [])
        if student_id:
            holds = [hold for hold in holds if hold.get("student_id") == student_id]
        response_holds = []
        for hold in holds:
            hold_data = dict(hold)
            book = books.get(hold.get("book_id", ""))
            hold_data["book"] = asdict(book) if book else None
            response_holds.append(hold_data)
        return {"holds": response_holds, "count": len(response_holds)}

    @router.post("/holds")
    async def agent_place_hold(payload: HoldRequest) -> Dict[str, Any]:
        if payload.student_id not in students:
            raise HTTPException(status_code=404, detail="Student not found")
        if payload.book_id not in books:
            raise HTTPException(status_code=404, detail="Book not found")

        state = load_state()
        holds = state.get("holds", [])
        for hold in holds:
            if (
                hold.get("student_id") == payload.student_id
                and hold.get("book_id") == payload.book_id
                and hold.get("status") in {"Requested", "Ready"}
            ):
                hold_copy = dict(hold)
                hold_copy["book"] = asdict(books[payload.book_id])
                return {"hold": hold_copy, "message": "Hold already exists for this student."}

        hold_id = next_id("H", [hold.get("hold_id", "") for hold in holds])
        book = books[payload.book_id]
        status = "Ready" if book.availability == "Available" else "Requested"
        now = datetime.now(timezone.utc)
        hold = {
            "hold_id": hold_id,
            "student_id": payload.student_id,
            "book_id": payload.book_id,
            "status": status,
            "notes": payload.notes or "",
            "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expires_at": (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        holds.append(hold)
        state["holds"] = holds
        save_state(state)
        hold_copy = dict(hold)
        hold_copy["book"] = asdict(book)
        message = (
            "This title is available now. Hold is marked Ready for pickup."
            if status == "Ready"
            else "Hold placed and queued."
        )
        return {"hold": hold_copy, "message": message}

    @router.post("/holds/{hold_id}/cancel")
    async def agent_cancel_hold(hold_id: str) -> Dict[str, Any]:
        state = load_state()
        holds = state.get("holds", [])
        for hold in holds:
            if hold.get("hold_id") == hold_id:
                hold["status"] = "Canceled"
                hold["canceled_at"] = now_iso()
                save_state(state)
                hold_copy = dict(hold)
                book = books.get(hold.get("book_id", ""))
                hold_copy["book"] = asdict(book) if book else None
                return {"hold": hold_copy, "message": "Hold canceled."}
        raise HTTPException(status_code=404, detail="Hold not found")

    @router.get("/collection-gaps")
    async def agent_collection_gaps() -> Dict[str, Any]:
        loan_books = [books[loan.book_id] for loan in loans if loan.book_id in books]
        genre_loan_counts = Counter(book.genre for book in loan_books)
        genre_catalog_counts = Counter(book.genre for book in books.values())
        genre_pressure = []
        for genre, catalog_count in genre_catalog_counts.items():
            loans_count = genre_loan_counts.get(genre, 0)
            ratio = loans_count / catalog_count if catalog_count else 0
            genre_pressure.append(
                {
                    "genre": genre,
                    "loans": loans_count,
                    "catalog": catalog_count,
                    "demand_ratio": round(ratio, 2),
                }
            )
        genre_pressure.sort(key=lambda item: item["demand_ratio"], reverse=True)

        level_catalog_counts = Counter(book.reading_level for book in books.values())
        level_student_counts = Counter(student.reading_level for student in students.values())
        level_pressure = []
        for level, student_count in level_student_counts.items():
            catalog_count = level_catalog_counts.get(level, 0)
            ratio = student_count / catalog_count if catalog_count else student_count
            level_pressure.append(
                {
                    "reading_level": level,
                    "students": student_count,
                    "catalog": catalog_count,
                    "student_ratio": round(ratio, 2),
                }
            )
        level_pressure.sort(key=lambda item: item["student_ratio"], reverse=True)

        unavailable_by_genre = Counter(
            book.genre for book in books.values() if book.availability != "Available"
        )
        availability_hotspots = []
        for genre, total in genre_catalog_counts.items():
            unavailable = unavailable_by_genre.get(genre, 0)
            rate = unavailable / total if total else 0
            availability_hotspots.append(
                {
                    "genre": genre,
                    "unavailable": unavailable,
                    "total": total,
                    "unavailable_rate": round(rate, 2),
                }
            )
        availability_hotspots.sort(key=lambda item: item["unavailable_rate"], reverse=True)

        loan_counts = Counter(loan.book_id for loan in loans if loan.book_id in books)
        high_demand_unavailable = []
        for book_id, count in loan_counts.most_common(10):
            book = books.get(book_id)
            if not book or book.availability == "Available":
                continue
            high_demand_unavailable.append(
                {
                    "book_id": book_id,
                    "title": book.title,
                    "genre": book.genre,
                    "loans": count,
                    "availability": book.availability,
                }
            )

        recommendations = []
        for item in genre_pressure[:2]:
            recommendations.append(
                f"Add more {item['genre']} titles; demand ratio {item['demand_ratio']}."
            )
        if level_pressure:
            top_level = level_pressure[0]
            recommendations.append(
                f"Expand level {top_level['reading_level']} inventory to match student demand."
            )
        if availability_hotspots:
            top_hotspot = availability_hotspots[0]
            recommendations.append(
                f"Reduce waitlists in {top_hotspot['genre']} ("
                f"{int(top_hotspot['unavailable_rate'] * 100)}% unavailable)."
            )

        return {
            "generated_at": now_iso(),
            "summary": {
                "total_books": len(books),
                "total_loans": len(loans),
            },
            "genre_pressure": genre_pressure[:6],
            "reading_level_pressure": level_pressure[:6],
            "availability_hotspots": availability_hotspots[:6],
            "high_demand_unavailable": high_demand_unavailable,
            "recommendations": recommendations,
        }

    @router.post("/feedback")
    async def agent_feedback(payload: FeedbackRequest) -> Dict[str, Any]:
        if payload.student_id not in students:
            raise HTTPException(status_code=404, detail="Student not found")
        if payload.book_id not in books:
            raise HTTPException(status_code=404, detail="Book not found")

        state = load_state()
        feedback = state.get("feedback", [])
        feedback_id = next_id("F", [entry.get("feedback_id", "") for entry in feedback])
        entry = {
            "feedback_id": feedback_id,
            "student_id": payload.student_id,
            "book_id": payload.book_id,
            "rating": payload.rating,
            "comment": payload.comment or "",
            "created_at": now_iso(),
        }
        feedback.append(entry)
        state["feedback"] = feedback
        save_state(state)
        entry_copy = dict(entry)
        entry_copy["book"] = asdict(books[payload.book_id])
        return {"feedback": entry_copy}

    @router.get("/feedback")
    async def agent_feedback_list(
        student_id: str | None = None,
        book_id: str | None = None,
        limit: int = Query(50, ge=1, le=200),
    ) -> Dict[str, Any]:
        state = load_state()
        feedback = state.get("feedback", [])
        if student_id:
            feedback = [entry for entry in feedback if entry.get("student_id") == student_id]
        if book_id:
            feedback = [entry for entry in feedback if entry.get("book_id") == book_id]
        feedback = list(reversed(feedback))[:limit]
        response_feedback = []
        for entry in feedback:
            entry_copy = dict(entry)
            book = books.get(entry.get("book_id", ""))
            entry_copy["book"] = asdict(book) if book else None
            response_feedback.append(entry_copy)
        return {"feedback": response_feedback, "count": len(response_feedback)}

    @router.get("/feedback/insights")
    async def agent_feedback_insights() -> Dict[str, Any]:
        state = load_state()
        feedback = state.get("feedback", [])
        if not feedback:
            return {
                "top_rated": [],
                "genre_sentiment": [],
                "recent_feedback": [],
            }

        ratings_by_book: Dict[str, List[int]] = {}
        ratings_by_genre: Dict[str, List[int]] = {}
        for entry in feedback:
            book_id = entry.get("book_id")
            rating = entry.get("rating")
            if not book_id or rating is None:
                continue
            ratings_by_book.setdefault(book_id, []).append(rating)
            book = books.get(book_id)
            if book:
                ratings_by_genre.setdefault(book.genre, []).append(rating)

        top_rated = []
        for book_id, ratings in ratings_by_book.items():
            avg = sum(ratings) / len(ratings)
            book = books.get(book_id)
            top_rated.append(
                {
                    "book_id": book_id,
                    "title": book.title if book else book_id,
                    "avg_rating": round(avg, 2),
                    "count": len(ratings),
                }
            )
        top_rated.sort(key=lambda item: (item["avg_rating"], item["count"]), reverse=True)

        genre_sentiment = []
        for genre, ratings in ratings_by_genre.items():
            avg = sum(ratings) / len(ratings)
            genre_sentiment.append(
                {
                    "genre": genre,
                    "avg_rating": round(avg, 2),
                    "count": len(ratings),
                }
            )
        genre_sentiment.sort(key=lambda item: (item["avg_rating"], item["count"]), reverse=True)

        recent_feedback = []
        for entry in list(reversed(feedback))[:5]:
            entry_copy = dict(entry)
            book = books.get(entry.get("book_id", ""))
            entry_copy["book"] = asdict(book) if book else None
            recent_feedback.append(entry_copy)

        return {
            "top_rated": top_rated[:6],
            "genre_sentiment": genre_sentiment[:6],
            "recent_feedback": recent_feedback,
        }

    @router.get("/feedback/recommendations")
    async def agent_feedback_recommendations(
        student_id: str = Query(..., description="Student identifier"),
        k: int = Query(5, ge=1, le=20),
    ) -> Dict[str, Any]:
        if student_id not in students:
            raise HTTPException(status_code=404, detail="Student not found")

        state = load_state()
        feedback = state.get("feedback", [])
        ratings_by_book: Dict[str, List[int]] = {}
        for entry in feedback:
            book_id = entry.get("book_id")
            rating = entry.get("rating")
            if not book_id or rating is None:
                continue
            ratings_by_book.setdefault(book_id, []).append(rating)

        recs = recommender.recommend(student_id, k=k)
        enriched = []
        for rec in recs:
            book = books.get(rec.book_id)
            if not book:
                continue
            ratings = ratings_by_book.get(rec.book_id, [])
            avg_rating = sum(ratings) / len(ratings) if ratings else None
            feedback_bonus = ((avg_rating - 3) / 2) if avg_rating is not None else 0
            enriched.append(
                {
                    "book": asdict(book),
                    "base_score": round(rec.score, 3),
                    "feedback_bonus": round(feedback_bonus, 2),
                    "avg_rating": round(avg_rating, 2) if avg_rating is not None else None,
                    "feedback_count": len(ratings),
                    "score": round(rec.score + feedback_bonus, 3),
                }
            )
        enriched.sort(key=lambda item: item["score"], reverse=True)
        return {"student": asdict(students[student_id]), "recommendations": enriched[:k]}

    return router
