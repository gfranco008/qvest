from __future__ import annotations

import os
from pathlib import Path
from dataclasses import asdict
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

from .data_loader import load_catalog, load_loans, load_students
from .recommender import Recommender

app = FastAPI(title="QVest Reading Recommender", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"] ,
)

books = load_catalog()
students = load_students()
loans = load_loans()
recommender = Recommender(books=books, students=students, loans=loans)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class ChatRequest(BaseModel):
    message: str


def _get_openai_client() -> OpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY is not set on the server.",
        )
    return OpenAI()


def _default_reason(book: Dict[str, Any], similar_book: Dict[str, Any] | None) -> str:
    if similar_book:
        return (
            f"Because they liked {similar_book['title']}, which shares {book['genre']} themes"
        )
    return f"Popular right now among students who enjoy {book['genre']} stories"


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/catalog")
async def catalog() -> List[Dict[str, Any]]:
    return [asdict(book) for book in books.values()]


@app.get("/students")
async def student_list() -> List[Dict[str, Any]]:
    return [asdict(student) for student in students.values()]


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
        response.append(
            {
                "book": asdict(book),
                "score": round(rec.score, 3),
                "similar_to": asdict(similar_book) if similar_book else None,
                "reason": _default_reason(asdict(book), asdict(similar_book) if similar_book else None),
            }
        )

    return {"student": asdict(students[student_id]), "recommendations": response}


@app.post("/chat")
async def chat(payload: ChatRequest) -> Dict[str, str]:
    client = _get_openai_client()
    system_prompt = (
        "You are a helpful librarian assistant. Provide concise, friendly "
        "recommendations and talking points for students and librarians."
    )
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload.message},
        ],
    )
    return {"reply": response.output_text}
