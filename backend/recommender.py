from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from .data_loader import Book, Student


@dataclass
class Recommendation:
    book_id: str
    score: float
    similar_to: str | None


class Recommender:
    def __init__(
        self,
        books: Dict[str, Book],
        students: Dict[str, Student],
        loans: Sequence[Tuple[str, str, str]],
    ) -> None:
        self.books = books
        self.students = students
        self.loans = loans
        self._student_books = self._build_student_books()
        self._book_counts = self._build_book_counts()
        self._cooccurrence = self._build_cooccurrence()

    def _build_student_books(self) -> Dict[str, List[str]]:
        student_books: Dict[str, List[str]] = defaultdict(list)
        for student_id, book_id, _ in self.loans:
            if book_id in self.books:
                student_books[student_id].append(book_id)
        return student_books

    def _build_book_counts(self) -> Counter[str]:
        counts: Counter[str] = Counter()
        for _, book_id, _ in self.loans:
            if book_id in self.books:
                counts[book_id] += 1
        return counts

    def _build_cooccurrence(self) -> Dict[Tuple[str, str], int]:
        cooccur: Dict[Tuple[str, str], int] = defaultdict(int)
        for book_ids in self._student_books.values():
            unique_books = list(dict.fromkeys(book_ids))
            for i in range(len(unique_books)):
                for j in range(i + 1, len(unique_books)):
                    a = unique_books[i]
                    b = unique_books[j]
                    cooccur[(a, b)] += 1
                    cooccur[(b, a)] += 1
        return cooccur

    def _similarity(self, a: str, b: str) -> float:
        if a == b:
            return 1.0
        co = self._cooccurrence.get((a, b), 0)
        if co == 0:
            return 0.0
        return co / ((self._book_counts[a] * self._book_counts[b]) ** 0.5)

    def recommend(self, student_id: str, k: int = 5) -> List[Recommendation]:
        seen = set(self._student_books.get(student_id, []))
        if not seen:
            return self._trending(k)

        scores: Dict[str, float] = defaultdict(float)
        similar_to: Dict[str, str] = {}
        best_sim: Dict[str, float] = {}

        for read_book in seen:
            for candidate in self.books:
                if candidate in seen:
                    continue
                sim = self._similarity(read_book, candidate)
                if sim <= 0:
                    continue
                scores[candidate] += sim
                if sim > best_sim.get(candidate, 0):
                    similar_to[candidate] = read_book
                    best_sim[candidate] = sim

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        results = [
            Recommendation(book_id=book_id, score=score, similar_to=similar_to.get(book_id))
            for book_id, score in ranked[:k]
        ]

        if len(results) < k:
            results.extend(self._trending(k - len(results), exclude=seen))

        return results

    def _trending(self, k: int, exclude: Iterable[str] | None = None) -> List[Recommendation]:
        exclude_set = set(exclude or [])
        ranked = [
            (book_id, count)
            for book_id, count in self._book_counts.most_common()
            if book_id not in exclude_set
        ]
        return [
            Recommendation(book_id=book_id, score=float(count), similar_to=None)
            for book_id, count in ranked[:k]
        ]
