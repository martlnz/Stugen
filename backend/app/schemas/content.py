import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.lecture import LectureError, LectureStatus
from app.schemas.llm import ChapterSummary, SlideDeck


class SummaryOut(BaseModel):
    lecture_id: uuid.UUID
    overview: str
    learning_objectives: list[str]
    chapters: list[ChapterSummary]
    content_md: str
    created_at: datetime


class SlidesOut(BaseModel):
    lecture_id: uuid.UUID
    deck: SlideDeck
    pptx_available: bool
    created_at: datetime


class QuizSummary(BaseModel):
    id: uuid.UUID
    lecture_id: uuid.UUID
    status: LectureStatus
    num_questions: int
    is_default: bool
    error: LectureError | None
    attempt_count: int
    best_score: int | None
    last_attempt_at: datetime | None
    created_at: datetime


class QuizList(BaseModel):
    items: list[QuizSummary]


class QuizCreate(BaseModel):
    num_questions: Literal[10, 20, 30] = 10


class QuestionPublic(BaseModel):
    """Câu hỏi khi làm bài: KHÔNG có answer_index và explanation (ADR-0012)."""

    id: uuid.UUID
    position: int
    question: str
    options: list[str]
    page_ref: int


class QuizDetail(BaseModel):
    id: uuid.UUID
    lecture_id: uuid.UUID
    lecture_title: str
    num_questions: int
    questions: list[QuestionPublic]


class AttemptCreate(BaseModel):
    answers: dict[uuid.UUID, int | None] = Field(
        default_factory=dict, description="question_id → chỉ số lựa chọn 0–3, null = bỏ trống"
    )


class QuestionResult(BaseModel):
    question_id: uuid.UUID
    position: int
    question: str
    options: list[str]
    selected_index: int | None
    correct_index: int
    is_correct: bool
    explanation: str
    page_ref: int


class ChapterScore(BaseModel):
    chapter_idx: int
    title: str
    correct: int
    total: int


class AttemptResult(BaseModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    lecture_id: uuid.UUID
    lecture_title: str
    score: int
    total: int
    created_at: datetime
    results: list[QuestionResult]
    by_chapter: list[ChapterScore]


class AttemptListItem(BaseModel):
    id: uuid.UUID
    score: int
    total: int
    created_at: datetime


class AttemptPage(BaseModel):
    items: list[AttemptListItem]
    page: int
    page_size: int
    total: int
