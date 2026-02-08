from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

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
