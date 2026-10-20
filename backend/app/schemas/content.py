import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.schemas.lecture import LectureError, LectureStatus
from app.schemas.llm import LessonSection, SlideDeck, Term

LessonStatus = Literal["pending", "queued", "processing", "completed", "failed"]
LessonStep = Literal["summarizing", "slides", "quiz"]


# ---------- Mục lục: chương → bài (ADR-0017) ----------


class SectionRef(BaseModel):
    title: str
    page_start: int
    page_end: int


class LessonAvailable(BaseModel):
    summary: bool = False
    slides: bool = False
    pptx: bool = False
    quiz: bool = False


class LessonOut(BaseModel):
    id: uuid.UUID
    idx: int
    number: str
    title: str
    page_start: int
    page_end: int
    status: LessonStatus
    progress_step: LessonStep | None
    error: LectureError | None
    available: LessonAvailable
    sections: list[SectionRef] = Field(description="Mục nhỏ kèm trang, có sau khi tóm tắt")


class ChapterOutline(BaseModel):
    id: uuid.UUID
    idx: int
    title: str
    page_start: int
    page_end: int
    lessons: list[LessonOut]


class OutlineOut(BaseModel):
    lecture_id: uuid.UUID
    chapters: list[ChapterOutline]


class GenerateLessons(BaseModel):
    lesson_ids: list[uuid.UUID] = Field(min_length=1, max_length=300)


# ---------- Nội dung một bài ----------


class LessonSummaryOut(BaseModel):
    lesson_id: uuid.UUID
    number: str
    title: str
    page_start: int
    page_end: int
    overview: str
    sections: list[LessonSection]
    terms: list[Term]
    content_md: str


class LessonSlidesOut(BaseModel):
    lesson_id: uuid.UUID
    deck: SlideDeck
    pptx_available: bool


# ---------- Quiz ----------


class QuizSummary(BaseModel):
    id: uuid.UUID
    lecture_id: uuid.UUID
    lesson_id: uuid.UUID | None = Field(description="Quiz của một bài; null với quiz tổng hợp")
    lesson_ids: list[uuid.UUID] | None = Field(description="Phạm vi của quiz tổng hợp")
    status: LectureStatus
    num_questions: int
    is_default: bool
    error: LectureError | None
    attempt_count: int
    best_score: int | None
    last_attempt_at: datetime | None
    edited_at: datetime | None = Field(description="Lần lưu chỉnh sửa gần nhất (ADR-0018)")
    created_at: datetime


class QuizList(BaseModel):
    items: list[QuizSummary]


class QuizCreate(BaseModel):
    num_questions: int = Field(default=10, ge=5, le=30)


class LectureQuizCreate(BaseModel):
    """Quiz tổng hợp theo phạm vi người dùng chọn."""

    num_questions: int = Field(default=20, ge=5, le=30)
    lesson_ids: list[uuid.UUID] = Field(min_length=1, max_length=300)


class QuestionPublic(BaseModel):
    """Câu hỏi khi làm bài: KHÔNG có answer_index và explanation (ADR-0012)."""

    id: uuid.UUID
    position: int
    question: str
    options: list[str]
    page_ref: int | None


class QuizDetail(BaseModel):
    id: uuid.UUID
    lecture_id: uuid.UUID
    lecture_title: str
    lesson_id: uuid.UUID | None
    scope_title: str = Field(description="Tên bài, hoặc mô tả phạm vi quiz tổng hợp")
    num_questions: int
    questions: list[QuestionPublic]


QuestionSource = Literal["ai", "edited", "manual"]


class EditLesson(BaseModel):
    """Bài trong phạm vi quiz: chọn bài cho câu hỏi và kiểm tra khoảng trang."""

    id: uuid.UUID
    number: str
    title: str
    page_start: int
    page_end: int


class QuestionEditable(BaseModel):
    """Câu hỏi kèm đáp án – chỉ dùng ở chế độ sửa của chủ quiz (ADR-0018)."""

    id: uuid.UUID
    position: int
    question: str
    options: list[str]
    answer_index: int
    explanation: str
    page_ref: int | None
    lesson_id: uuid.UUID | None
    source: QuestionSource


class QuizEditable(BaseModel):
    id: uuid.UUID
    lecture_id: uuid.UUID
    lecture_title: str
    lesson_id: uuid.UUID | None
    scope_title: str
    num_questions: int
    attempt_count: int = Field(description="Số lần làm bài sẽ bị xoá khi lưu chỉnh sửa")
    edited_at: datetime | None
    lessons: list[EditLesson]
    questions: list[QuestionEditable]


QuestionText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]
OptionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
ExplanationText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class QuestionInput(BaseModel):
    id: uuid.UUID | None = Field(default=None, description="null = câu mới")
    question: QuestionText
    options: list[OptionText] = Field(min_length=4, max_length=4)
    answer_index: int = Field(ge=0, le=3)
    explanation: ExplanationText = ""
    page_ref: int | None = Field(default=None, ge=1)
    lesson_id: uuid.UUID | None = Field(
        default=None, description="Bắt buộc với quiz tổng hợp; bỏ qua với quiz của một bài"
    )

    @field_validator("options")
    @classmethod
    def _distinct(cls, value: list[str]) -> list[str]:
        if len({o.casefold() for o in value}) != len(value):
            raise ValueError("Các lựa chọn không được trùng nhau.")
        return value


class QuizQuestionsUpdate(BaseModel):
    """Thay toàn bộ danh sách câu hỏi; thứ tự trong mảng là thứ tự hiển thị."""

    questions: list[QuestionInput] = Field(min_length=1, max_length=30)


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
    page_ref: int | None


class ChapterScore(BaseModel):
    """Điểm theo bài (quiz mới) hoặc theo chương (quiz định dạng cũ)."""

    chapter_idx: int
    title: str
    correct: int
    total: int


class AttemptResult(BaseModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    lecture_id: uuid.UUID
    lecture_title: str
    lesson_id: uuid.UUID | None
    scope_title: str
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
