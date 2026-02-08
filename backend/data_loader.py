from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Book:
    book_id: str
    title: str
    author: str
    genre: str
    reading_level: str
    keywords: str


@dataclass(frozen=True)
class Student:
    student_id: str
    grade: str
    interests: str


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
        )
        books[book.book_id] = book
    return books


def load_students() -> Dict[str, Student]:
    students: Dict[str, Student] = {}
    for row in _read_csv(DATA_DIR / "students.csv"):
        student = Student(
            student_id=row["student_id"],
            grade=row["grade"],
            interests=row["interests"],
        )
        students[student.student_id] = student
    return students


def load_loans() -> List[Tuple[str, str, str]]:
    loans: List[Tuple[str, str, str]] = []
    for row in _read_csv(DATA_DIR / "loans.csv"):
        loans.append((row["student_id"], row["book_id"], row["borrowed_at"]))
    return loans
