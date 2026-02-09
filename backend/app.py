from __future__ import annotations

import os
from uuid import uuid4
from pathlib import Path
from dataclasses import asdict
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

from .agent_state import load_state, save_state
from .agents import create_router, prompts
from .agents.utils import default_reason, now_iso, build_continuation_recommendations
from .chat_utils import build_recommendations, extract_student_id, wants_recommendations
from .chat_memory import get_history, set_history
from .data_loader import load_catalog, load_loans, load_students
from .recommender import Recommender
from .tools import call_tool, tool_detect

app = FastAPI(title="QVest Reading Recommender", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"] ,
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")

books = load_catalog()
students = load_students()
loans = load_loans()
recommender = Recommender(books=books, students=students, loans=loans)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
app.include_router(
    create_router(
        books=books,
        students=students,
        loans=loans,
        recommender=recommender,
    )
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    student_id: str | None = None


def _get_openai_client() -> OpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY is not set on the server.",
        )
    return OpenAI()


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/chatbot.html")


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/catalog")
async def catalog() -> List[Dict[str, Any]]:
    return [asdict(book) for book in books.values()]


@app.get("/students")
async def student_list() -> List[Dict[str, Any]]:
    return [asdict(student) for student in students.values()]


@app.get("/loans")
async def loan_list() -> List[Dict[str, Any]]:
    return [asdict(loan) for loan in loans]


@app.get("/recommendations")
async def recommendations(
    student_id: str = Query(..., description="Student identifier"),
    k: int = Query(5, ge=1, le=20),
) -> Dict[str, Any]:
    if student_id not in students:
        raise HTTPException(status_code=404, detail="Student not found")

    recs = recommender.recommend(student_id, k=k)
    response: List[Dict[str, Any]] = []

    for rec in recs:
        book = books.get(rec.book_id)
        if not book:
            continue
        similar_book = books.get(rec.similar_to) if rec.similar_to else None
        driver_label = DRIVER_LABELS.get(rec.driver, rec.driver)
        reason = default_reason(
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

    return {"student": asdict(students[student_id]), "recommendations": response}


@app.post("/chat")
async def chat(payload: ChatRequest) -> Dict[str, Any]:
    client = _get_openai_client()
    system_prompt = prompts.CHAT_SYSTEM_PROMPT
    session_id = payload.session_id or f"CHAT-{uuid4().hex[:12]}"
    history = get_history(session_id)
    history.append({"role": "user", "content": payload.message})
    history = history[-12:]
    set_history(session_id, history)
    history_texts = [item.get("content", "") for item in history]
    student_id = payload.student_id or extract_student_id(history_texts)
    state = load_state()
    existing_profile = (
        state.get("onboarding_profiles", {}).get(student_id) if student_id else None
    )
    wants_recs = wants_recommendations(payload.message)
    recommendations: List[Dict[str, Any]] = []
    needs_student_id = False
    availability_hint = tool_detect("availability", payload.message)
    history_hint = tool_detect("reading_history", payload.message)
    continuation_hint = tool_detect("series_author", payload.message)
    snapshot_hint = tool_detect("student_snapshot", payload.message)
    profile_query = "profile" in (payload.message or "").lower()
    hold_hint = tool_detect("reserve_hold", payload.message)
    onboarding_hint = tool_detect("onboard_from_history", payload.message)
    save_onboarding = tool_detect("onboard_save_intent", payload.message)
    if save_onboarding and not onboarding_hint:
        onboarding_hint = True
    if profile_query and not existing_profile and not onboarding_hint:
        onboarding_hint = True
    available_books = (
        call_tool("availability", books=books, message=payload.message, limit=5)
        if availability_hint
        else []
    )
    continuation_recs: List[Dict[str, Any]] = []
    if continuation_hint:
        continuation_recs = build_continuation_recommendations(
            call_tool("series_author", books=books, message=payload.message, limit=5),
            limit=5,
        )
        if availability_hint:
            continuation_recs = [
                rec
                for rec in continuation_recs
                if rec["book"].get("availability") == "Available"
            ]
    hold_result = None
    if hold_hint:
        hold_result = call_tool(
            "reserve_hold",
            books=books,
            students=students,
            student_id=student_id,
            message=payload.message,
        )
        if hold_result.get("status") == "needs_student_id":
            needs_student_id = True
    reading_history = []
    if history_hint and student_id:
        reading_history = call_tool(
            "reading_history",
            books=books,
            loans=loans,
            student_id=student_id,
            limit=12,
        )
    if history_hint and not student_id:
        needs_student_id = True
    onboarding_profile = None
    onboarding_saved = False
    onboarding_pending = False
    if onboarding_hint and student_id:
        onboarding_result = call_tool(
            "onboard_from_history",
            books=books,
            loans=loans,
            student_id=student_id,
        )
        onboarding_profile = onboarding_result.get("profile", {}) or None
        if onboarding_profile:
            existing_profile = state.get("onboarding_profiles", {}).get(student_id)
            should_save = save_onboarding or not existing_profile
            if should_save:
                profile = dict(existing_profile or {})
                profile.update(onboarding_profile)
                profile.setdefault("created_at", now_iso())
                profile["updated_at"] = now_iso()
                state.setdefault("onboarding_profiles", {})[student_id] = profile
                save_state(state)
                onboarding_saved = True
            else:
                onboarding_pending = True
    if onboarding_hint and not student_id:
        needs_student_id = True
    snapshot = None
    if snapshot_hint and student_id:
        snapshot = call_tool(
            "student_snapshot",
            books=books,
            loans=loans,
            students=students,
            student_id=student_id,
            state=state,
        )
    if snapshot_hint and not student_id:
        needs_student_id = True
    if continuation_hint:
        recommendations = continuation_recs
    elif wants_recs:
        if student_id:
            recommendations = build_recommendations(
                student_id=student_id,
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
    context_lines = [f"Known student_id: {student_id or 'unknown'}."]
    if needs_student_id:
        context_lines.append(
            "Student_id is missing. Ask for it before recommending or updating records."
        )
    if available_books:
        available_lines = [
            f"{book['title']} by {book['author']} ({book['genre']}, level {book['reading_level']})"
            for book in available_books
        ]
        context_lines.append(
            "Available titles matching request:\n" + "\n".join(available_lines)
        )
    if reading_history:
        history_lines = [
            f"{item['book']['title']} by {item['book']['author']} ({item['last_checkout'] or 'date unknown'})"
            for item in reading_history
        ]
        context_lines.append("Reading history:\n" + "\n".join(history_lines))
    if hold_result:
        status = hold_result.get("status", "unknown")
        message = hold_result.get("message", "")
        if status == "ambiguous":
            matches = hold_result.get("matches", [])
            match_lines = [
                f"{item.get('title')} by {item.get('author')} (ID {item.get('book_id')})"
                for item in matches
            ]
            context_lines.append(
                "Hold request needs clarification. Matches:\n" + "\n".join(match_lines)
            )
        else:
            context_lines.append(f"Hold request status: {status}. {message}")
    if continuation_hint:
        if continuation_recs:
            continuation_lines = [
                f"{rec['book']['title']} by {rec['book']['author']} ({rec['book']['genre']})"
                for rec in continuation_recs
            ]
            context_lines.append(
                "Series/author continuation matches:\n"
                + "\n".join(continuation_lines)
            )
        else:
            context_lines.append(
                "Series/author continuation: no matching titles found in the catalog."
            )
    if snapshot:
        stats = snapshot.get("stats", {})
        top_genres = ", ".join([item["genre"] for item in stats.get("top_genres", [])])
        top_authors = ", ".join(
            [item["author"] for item in stats.get("top_authors", [])]
        )
        recent_titles = ", ".join(
            [item["title"] for item in stats.get("recent_books", [])]
        )
        snapshot_line = (
            f"Student snapshot: total loans {stats.get('total_loans', 0)}, "
            f"unique books {stats.get('unique_books', 0)}, "
            f"last checkout {stats.get('last_checkout') or 'n/a'}."
        )
        if top_genres:
            snapshot_line += f" Top genres: {top_genres}."
        if top_authors:
            snapshot_line += f" Top authors: {top_authors}."
        if recent_titles:
            snapshot_line += f" Recent reads: {recent_titles}."
        context_lines.append(snapshot_line)
    if onboarding_profile:
        summary_parts = []
        if onboarding_profile.get("preferred_genres"):
            summary_parts.append(f"Genres: {onboarding_profile['preferred_genres']}")
        if onboarding_profile.get("reading_level"):
            summary_parts.append(f"Level: {onboarding_profile['reading_level']}")
        if onboarding_profile.get("interests"):
            summary_parts.append(f"Interests: {onboarding_profile['interests']}")
        summary = " · ".join(summary_parts) if summary_parts else "Profile generated from history."
        context_lines.append(f"Onboarding profile summary: {summary}")
    elif existing_profile:
        summary_parts = []
        if existing_profile.get("preferred_genres"):
            summary_parts.append(f"Genres: {existing_profile['preferred_genres']}")
        if existing_profile.get("reading_level"):
            summary_parts.append(f"Level: {existing_profile['reading_level']}")
        if existing_profile.get("interests"):
            summary_parts.append(f"Interests: {existing_profile['interests']}")
        summary = " · ".join(summary_parts) if summary_parts else "Profile saved."
        context_lines.append(f"Existing onboarding profile: {summary}")
    elif student_id:
        context_lines.append("No saved onboarding profile was found for this student.")
    if recommendations:
        summary_lines = [
            (
                f"{rec['book']['title']} by {rec['book']['author']} "
                f"({rec['book']['genre']}, level {rec['book']['reading_level']})"
            )
            for rec in recommendations
        ]
        context_lines.append(
            "Recommended titles for reference (use only these in your reply):\n"
            + "\n".join(summary_lines)
        )
    context_note = "\n".join(context_lines)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": context_note},
            *history,
        ],
    )
    assistant_reply = response.output_text
    if reading_history and "reading history" not in assistant_reply.lower():
        history_lines = [
            f"- {item['book']['title']} by {item['book']['author']} ({item['last_checkout'] or 'date unknown'})"
            for item in reading_history
        ]
        assistant_reply = (
            assistant_reply.strip()
            + "\n\nReading history:\n"
            + "\n".join(history_lines)
        )
    if onboarding_profile and "onboarding profile" not in assistant_reply.lower():
        summary_lines = []
        if onboarding_profile.get("preferred_genres"):
            summary_lines.append(f"Genres: {onboarding_profile['preferred_genres']}")
        if onboarding_profile.get("reading_level"):
            summary_lines.append(f"Level: {onboarding_profile['reading_level']}")
        if onboarding_profile.get("interests"):
            summary_lines.append(f"Interests: {onboarding_profile['interests']}")
        summary = " · ".join(summary_lines) if summary_lines else "Profile generated from history."
        if onboarding_saved:
            decision_line = "\nSaved."
        elif onboarding_pending:
            decision_line = "\nA profile already exists. Save these changes?"
        else:
            decision_line = "\nWould you like me to save this profile?"
        assistant_reply = (
            assistant_reply.strip()
            + "\n\nOnboarding profile:\n"
            + summary
            + decision_line
        )
    elif (
        "profile" in payload.message.lower()
        and existing_profile
        and "profile" not in assistant_reply.lower()
    ):
        summary_lines = []
        if existing_profile.get("preferred_genres"):
            summary_lines.append(f"Genres: {existing_profile['preferred_genres']}")
        if existing_profile.get("reading_level"):
            summary_lines.append(f"Level: {existing_profile['reading_level']}")
        if existing_profile.get("interests"):
            summary_lines.append(f"Interests: {existing_profile['interests']}")
        summary = " · ".join(summary_lines) if summary_lines else "Profile saved."
        assistant_reply = (
            assistant_reply.strip()
            + "\n\nProfile:\n"
            + summary
        )
    history.append({"role": "assistant", "content": assistant_reply})
    history = history[-12:]
    set_history(session_id, history)
    return {
        "reply": assistant_reply,
        "session_id": session_id,
        "memory_size": len(history),
        "student_id": student_id,
        "needs_student_id": needs_student_id,
        "recommendations": recommendations,
        "reading_history": reading_history,
        "onboarding_profile": onboarding_profile,
        "onboarding_saved": onboarding_saved,
        "onboarding_pending": onboarding_pending,
        "hold_result": hold_result,
        "student_snapshot": snapshot,
    }
DRIVER_LABELS = {
    "history_similarity": "Borrowing history match",
    "collaborative_similarity": "Borrowing pattern similarity",
    "content_similarity": "Content similarity",
    "profile_fit": "Student profile fit",
    "popularity": "Popularity",
    "availability_penalty": "Availability penalty",
}
