from __future__ import annotations

from pydantic import BaseModel, Field


class ConciergeRequest(BaseModel):
    message: str
    student_id: str | None = None
    limit: int = Field(5, ge=1, le=10)
    availability_only: bool = False


class OnboardingRequest(BaseModel):
    student_id: str
    interests: str | None = None
    preferred_genres: str | None = None
    reading_level: str | None = None
    goals: str | None = None
    avoid_topics: str | None = None
    notes: str | None = None


class HoldRequest(BaseModel):
    student_id: str
    book_id: str
    notes: str | None = None


class FeedbackRequest(BaseModel):
    student_id: str
    book_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = None
