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

from .agents import create_router, prompts
from .agents.engine import run_agent
from .agent_state import update_observability
from .agents.utils import default_reason, estimate_token_cost, parse_token_usage
from .chat_memory import get_history, set_history
from .data_loader import load_catalog, load_loans, load_students
from .labels import DRIVER_LABELS
from .recommender import Recommender

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

    result = run_agent(
        mode="chat",
        message=payload.message,
        student_id=payload.student_id,
        history_texts=history_texts,
        books=books,
        students=students,
        loans=loans,
        recommender=recommender,
    )

    context_note = prompts.build_context_note(result.context_payload())
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
    usage = parse_token_usage(getattr(response, "usage", None))
    if usage:
        update_observability(
            result.event_id,
            {
                "model": model,
                "token_usage": usage,
                "cost_estimate": estimate_token_cost(usage, model=model),
            },
        )

    if result.reading_history and "reading history" not in assistant_reply.lower():
        history_lines = [
            f"- {item['book']['title']} by {item['book']['author']} ({item['last_checkout'] or 'date unknown'})"
            for item in result.reading_history
        ]
        assistant_reply = (
            assistant_reply.strip()
            + "\n\nReading history:\n"
            + "\n".join(history_lines)
        )

    if result.onboarding_profile and "onboarding profile" not in assistant_reply.lower():
        summary_parts = []
        if result.onboarding_profile.get("preferred_genres"):
            summary_parts.append(f"Genres: {result.onboarding_profile['preferred_genres']}")
        if result.onboarding_profile.get("reading_level"):
            summary_parts.append(f"Level: {result.onboarding_profile['reading_level']}")
        if result.onboarding_profile.get("interests"):
            summary_parts.append(f"Interests: {result.onboarding_profile['interests']}")
        summary = " · ".join(summary_parts) if summary_parts else "Profile generated from history."
        if result.onboarding_saved:
            decision_line = "\nSaved."
        elif result.onboarding_pending:
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
        and result.existing_profile
        and "profile" not in assistant_reply.lower()
    ):
        summary_parts = []
        if result.existing_profile.get("preferred_genres"):
            summary_parts.append(f"Genres: {result.existing_profile['preferred_genres']}")
        if result.existing_profile.get("reading_level"):
            summary_parts.append(f"Level: {result.existing_profile['reading_level']}")
        if result.existing_profile.get("interests"):
            summary_parts.append(f"Interests: {result.existing_profile['interests']}")
        summary = " · ".join(summary_parts) if summary_parts else "Profile saved."
        assistant_reply = assistant_reply.strip() + "\n\nProfile:\n" + summary

    history.append({"role": "assistant", "content": assistant_reply})
    history = history[-12:]
    set_history(session_id, history)
    return {
        "reply": assistant_reply,
        "session_id": session_id,
        "memory_size": len(history),
        "student_id": result.student_id,
        "needs_student_id": result.needs_student_id,
        "recommendations": result.recommendations,
        "reading_history": result.reading_history,
        "onboarding_profile": result.onboarding_profile,
        "onboarding_saved": result.onboarding_saved,
        "onboarding_pending": result.onboarding_pending,
        "hold_result": result.hold_result,
        "student_snapshot": result.snapshot,
    }
