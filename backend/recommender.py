from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from math import exp, log
from typing import Dict, Iterable, List, Sequence, Tuple

from .data_loader import Book, Loan, Student


@dataclass
class Recommendation:
    book_id: str
    score: float
    similar_to: str | None
    signals: Dict[str, float]
    driver: str


class Recommender:
    def __init__(
        self,
        books: Dict[str, Book],
        students: Dict[str, Student],
        loans: Sequence[Loan],
    ) -> None:
        self.books = books
        self.students = students
        self.loans = loans
        self._student_books = self._build_student_books()
        self._book_counts = self._build_book_counts()
        self._cooccurrence = self._build_cooccurrence()
        self._book_tokens = self._build_book_tokens()
        self._student_tokens = self._build_student_tokens()
        self._book_levels = self._build_book_levels()
        self._max_checkout_date = self._build_max_checkout_date()
        self._loan_weights = self._build_loan_weights()

    def _build_student_books(self) -> Dict[str, List[str]]:
        student_books: Dict[str, List[str]] = defaultdict(list)
        for loan in self.loans:
            if loan.book_id in self.books:
                student_books[loan.student_id].append(loan.book_id)
        return student_books

    def _build_book_counts(self) -> Counter[str]:
        counts: Counter[str] = Counter()
        for loan in self.loans:
            if loan.book_id in self.books:
                counts[loan.book_id] += 1
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

    def _build_book_tokens(self) -> Dict[str, set[str]]:
        tokens: Dict[str, set[str]] = {}
        for book in self.books.values():
            parts = [
                book.genre,
                book.keywords,
                book.subject_tags,
                book.series,
                book.author,
                book.language,
                book.audience,
            ]
            tokens[book.book_id] = self._tokenize(";".join(filter(None, parts)))
        return tokens

    def _build_student_tokens(self) -> Dict[str, set[str]]:
        tokens: Dict[str, set[str]] = {}
        for student in self.students.values():
            parts = [student.interests, student.preferred_genres]
            tokens[student.student_id] = self._tokenize(";".join(filter(None, parts)))
        return tokens

    def _build_book_levels(self) -> Dict[str, float]:
        levels: Dict[str, float] = {}
        for book in self.books.values():
            levels[book.book_id] = self._parse_level(book.reading_level)
        return levels

    def _build_max_checkout_date(self) -> date | None:
        dates: List[date] = []
        for loan in self.loans:
            parsed = self._parse_date(loan.checkout_date)
            if parsed:
                dates.append(parsed)
        return max(dates) if dates else None

    def _build_loan_weights(self) -> Dict[Tuple[str, str], float]:
        weights: Dict[Tuple[str, str], float] = {}
        positive_words = {"love", "loved", "enjoyed", "asked", "favorite", "great", "cool"}
        negative_words = {"not", "dislike", "boring", "hard", "challenging"}

        for loan in self.loans:
            key = (loan.student_id, loan.book_id)
            weight = 1.0
            try:
                renewals = int(loan.renewals)
            except (TypeError, ValueError):
                renewals = 0
            weight += 0.25 * max(0, renewals)

            feedback = (loan.student_feedback or "").lower()
            if any(word in feedback for word in positive_words):
                weight += 0.35
            if any(word in feedback for word in negative_words):
                weight -= 0.2

            checkout = self._parse_date(loan.checkout_date)
            if checkout and self._max_checkout_date:
                delta_days = (self._max_checkout_date - checkout).days
                recency = exp(-delta_days / 180) if delta_days >= 0 else 1.0
                weight += 0.3 * recency

            weights[key] = max(0.2, weight)
        return weights

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        normalized = (
            text.replace(",", ";")
            .replace("/", ";")
            .replace("|", ";")
            .replace("&", ";")
        )
        tokens = {
            token.strip().lower()
            for token in normalized.split(";")
            if token and token.strip()
        }
        return tokens

    @staticmethod
    def _parse_level(level: str) -> float:
        if not level:
            return 0.0
        parts = [part for part in level.replace("–", "-").split("-") if part.strip()]
        try:
            nums = [float(part.strip()) for part in parts]
        except ValueError:
            return 0.0
        if not nums:
            return 0.0
        return sum(nums) / len(nums)

    @staticmethod
    def _parse_date(value: str) -> date | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _content_similarity(self, a: str, b: str) -> float:
        tokens_a = self._book_tokens.get(a, set())
        tokens_b = self._book_tokens.get(b, set())
        if not tokens_a or not tokens_b:
            token_sim = 0.0
        else:
            token_sim = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

        level_a = self._book_levels.get(a, 0.0)
        level_b = self._book_levels.get(b, 0.0)
        if level_a and level_b:
            level_sim = max(0.0, 1 - abs(level_a - level_b) / 4)
        else:
            level_sim = 0.0

        return 0.7 * token_sim + 0.3 * level_sim

    def _similarity_parts(self, a: str, b: str) -> Tuple[float, float, float]:
        if a == b:
            return 1.0, 1.0, 1.0
        co = self._cooccurrence.get((a, b), 0)
        collab = 0.0
        if co > 0:
            collab = co / ((self._book_counts[a] * self._book_counts[b]) ** 0.5)
        content = self._content_similarity(a, b)
        combined = 0.6 * collab + 0.4 * content
        return collab, content, combined

    def _profile_fit(self, student_id: str, book_id: str) -> float:
        student = self.students.get(student_id)
        book = self.books.get(book_id)
        if not student or not book:
            return 0.0
        tokens = self._student_tokens.get(student_id, set())
        book_tokens = self._book_tokens.get(book_id, set())
        overlap = len(tokens & book_tokens) if tokens and book_tokens else 0

        score = 0.0
        if overlap:
            score += min(0.6, overlap * 0.2)
        if book.genre and book.genre.lower() in tokens:
            score += 0.2

        student_level = self._parse_level(student.reading_level)
        book_level = self._book_levels.get(book_id, 0.0)
        if student_level and book_level:
            score += max(0.0, 0.4 - abs(student_level - book_level) * 0.1)

        try:
            grade = int(student.grade)
        except (TypeError, ValueError):
            grade = 0
        if book.audience == "Upper Elementary" and grade and grade <= 5:
            score += 0.2
        if book.audience == "Middle School" and grade and grade >= 6:
            score += 0.2

        return score

    def _similarity(self, a: str, b: str) -> float:
        return self._similarity_parts(a, b)[2]

    @staticmethod
    def _primary_driver(signals: Dict[str, float]) -> str:
        positives = {key: value for key, value in signals.items() if value > 0}
        if not positives:
            return "popularity"
        return max(positives.items(), key=lambda item: item[1])[0]

    def recommend(self, student_id: str, k: int = 5) -> List[Recommendation]:
        seen = set(self._student_books.get(student_id, []))
        if not seen:
            return self._trending(k, student_id=student_id)

        scores: Dict[str, float] = defaultdict(float)
        signal_map: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {
                "history_similarity": 0.0,
                "profile_fit": 0.0,
                "popularity": 0.0,
                "availability_penalty": 0.0,
                "collaborative_similarity": 0.0,
                "content_similarity": 0.0,
            }
        )
        similar_to: Dict[str, str] = {}
        best_sim: Dict[str, float] = {}

        for read_book in seen:
            for candidate in self.books:
                if candidate in seen:
                    continue
                collab, content, sim = self._similarity_parts(read_book, candidate)
                if sim <= 0:
                    continue
                weight = self._loan_weights.get((student_id, read_book), 1.0)
                contribution = sim * weight
                scores[candidate] += contribution
                signal_map[candidate]["history_similarity"] += contribution
                signal_map[candidate]["collaborative_similarity"] += collab
                signal_map[candidate]["content_similarity"] += content
                if contribution > best_sim.get(candidate, 0):
                    similar_to[candidate] = read_book
                    best_sim[candidate] = contribution

        for candidate in list(scores.keys()):
            profile = self._profile_fit(student_id, candidate)
            if profile:
                scores[candidate] += profile
                signal_map[candidate]["profile_fit"] += profile
            popularity = 0.05 * log(1 + self._book_counts.get(candidate, 0))
            if popularity:
                scores[candidate] += popularity
                signal_map[candidate]["popularity"] += popularity
            book = self.books.get(candidate)
            if book and book.availability and book.availability != "Available":
                before = scores[candidate]
                scores[candidate] *= 0.85
                signal_map[candidate]["availability_penalty"] += scores[candidate] - before

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        results = [
            Recommendation(
                book_id=book_id,
                score=score,
                similar_to=similar_to.get(book_id),
                signals=signal_map.get(book_id, {}),
                driver=self._primary_driver(signal_map.get(book_id, {})),
            )
            for book_id, score in ranked[:k]
        ]

        if len(results) < k:
            results.extend(self._trending(k - len(results), exclude=seen, student_id=student_id))

        return results

    def _trending(
        self,
        k: int,
        exclude: Iterable[str] | None = None,
        student_id: str | None = None,
    ) -> List[Recommendation]:
        exclude_set = set(exclude or [])
        ranked: List[Tuple[str, float]] = []
        signal_map: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {
                "history_similarity": 0.0,
                "profile_fit": 0.0,
                "popularity": 0.0,
                "availability_penalty": 0.0,
            }
        )
        for book_id, count in self._book_counts.most_common():
            if book_id in exclude_set:
                continue
            score = float(count)
            signal_map[book_id]["popularity"] += score
            if student_id:
                profile = self._profile_fit(student_id, book_id)
                score += profile
                signal_map[book_id]["profile_fit"] += profile
            book = self.books.get(book_id)
            if book and book.availability and book.availability != "Available":
                before = score
                score *= 0.9
                signal_map[book_id]["availability_penalty"] += score - before
            ranked.append((book_id, score))
        return [
            Recommendation(
                book_id=book_id,
                score=float(score),
                similar_to=None,
                signals=signal_map.get(book_id, {}),
                driver=self._primary_driver(signal_map.get(book_id, {})),
            )
            for book_id, score in ranked[:k]
        ]
