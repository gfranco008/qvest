from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Book:
    book_id: str
    title: str
    author: str
    genre: str
    reading_level: str
    keywords: str
    publisher: str
    publication_year: str
    edition: str
    series: str
    language: str
    subject_tags: str
    audience: str
    isbn: str
    pages: str
    format: str
    availability: str


@dataclass(frozen=True)
class Student:
    student_id: str
    grade: str
    age: str
    interests: str
    reading_level: str
    preferred_genres: str
    account_status: str
    items_checkedout: str
    notes: str
    homeroom: str


@dataclass(frozen=True)
class Loan:
    transaction_id: str
    student_id: str
    book_id: str
    checkout_date: str
    return_date: str
    renewals: str
    recommended_by: str
    grade: str
    recommendation_reason: str
    student_feedback: str


def _read_csv(path: Path) -> Iterable[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield {k: (v or "").strip() for k, v in row.items()}


def load_catalog() -> Dict[str, Book]:
    books: Dict[str, Book] = {}
    for row in _read_csv(DATA_DIR / "catalog.csv"):
        book = Book(
            book_id=row["book_id"],
            title=row["title"],
            author=row["author"],
            genre=row["genre"],
            reading_level=row["reading_level"],
            keywords=row["keywords"],
            publisher=row.get("publisher", ""),
            publication_year=row.get("publication_year", ""),
            edition=row.get("edition", ""),
            series=row.get("series", ""),
            language=row.get("language", ""),
            subject_tags=row.get("subject_tags", ""),
            audience=row.get("audience", ""),
            isbn=row.get("isbn", ""),
            pages=row.get("pages", ""),
            format=row.get("format", ""),
            availability=row.get("availability", ""),
        )
        books[book.book_id] = book
    return books


def load_students() -> Dict[str, Student]:
    students: Dict[str, Student] = {}
    for row in _read_csv(DATA_DIR / "students.csv"):
        student = Student(
            student_id=row["student_id"],
            grade=row["grade"],
            age=row.get("age", ""),
            interests=row["interests"],
            reading_level=row.get("reading_level", ""),
            preferred_genres=row.get("preferred_genres", ""),
            account_status=row.get("account_status", ""),
            items_checkedout=row.get("items_checkedout", ""),
            notes=row.get("notes", ""),
            homeroom=row.get("homeroom", ""),
        )
        students[student.student_id] = student
    return students


def load_loans() -> List[Loan]:
    loans: List[Loan] = []
    for row in _read_csv(DATA_DIR / "loans.csv"):
        loans.append(
            Loan(
                transaction_id=row.get("transaction_id", ""),
                student_id=row["student_id"],
                book_id=row["book_id"],
                checkout_date=row.get("checkout_date", ""),
                return_date=row.get("return_date", ""),
                renewals=row.get("renewals", ""),
                recommended_by=row.get("recommended_by", ""),
                grade=row.get("grade", ""),
                recommendation_reason=row.get("recommendation_reason", ""),
                student_feedback=row.get("student_feedback", ""),
            )
        )
    return loans
