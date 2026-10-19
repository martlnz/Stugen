import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

LectureStatus = Literal["queued", "processing", "completed", "failed"]
ProgressStep = Literal["extracting", "summarizing", "slides", "quiz"]


class LectureError(BaseModel):
    code: str
    message: str


class LessonCounts(BaseModel):
    """Số bài theo trạng thái tạo học liệu (ADR-0017)."""

    total: int = 0
    completed: int = 0
    processing: int = 0
    failed: int = 0


class LectureOut(BaseModel):
    id: uuid.UUID
    title: str
    original_filename: str
    file_size: int
    page_count: int
    status: LectureStatus
    progress_step: ProgressStep | None
    error: LectureError | None
    lessons: LessonCounts
    needs_regenerate: bool = Field(
        description="Bài giảng định dạng cũ (trước ADR-0017): cần tạo lại nội dung"
    )
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class LecturePage(BaseModel):
    items: list[LectureOut]
    page: int
    page_size: int
    total: int


class LectureUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


LectureSort = Literal["-created_at", "created_at", "title", "-title"]
