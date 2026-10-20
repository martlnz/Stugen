"""Model SQLAlchemy theo docs/design/data-model.md v1.4 (chưa có llm_calls)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map = {
        uuid.UUID: UUID(as_uuid=True),
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
        list[Any]: JSONB,
    }


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class User(UUIDPk, Base):
    __tablename__ = "users"

    google_id: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), default=utcnow)
    last_login_at: Mapped[datetime] = mapped_column(server_default=func.now(), default=utcnow)


class Session(UUIDPk, Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_expires_at", "expires_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), default=utcnow)

    user: Mapped[User] = relationship(lazy="joined")


LECTURE_STATUSES = ("queued", "processing", "completed", "failed")
PROGRESS_STEPS = ("extracting", "summarizing", "slides", "quiz")
QUESTION_SOURCES = ("ai", "edited", "manual")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


class Lecture(UUIDPk, Base):
    __tablename__ = "lectures"
    __table_args__ = (
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint("file_size <= 20971520", name="file_size_max"),
        CheckConstraint("page_count BETWEEN 1 AND 200", name="page_count_range"),
        CheckConstraint(_in("status", LECTURE_STATUSES), name="status_valid"),
        CheckConstraint(_in("progress_step", PROGRESS_STEPS), name="progress_step_valid"),
        Index("ix_lectures_user_created", "user_id", text("created_at DESC")),
        Index(
            "ix_lectures_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(Text)
    pdf_key: Mapped[str] = mapped_column(Text)
    file_size: Mapped[int] = mapped_column(BigInteger)
    page_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default="queued", default="queued")
    progress_step: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None]

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="lecture", order_by="Chapter.idx", passive_deletes=True
    )


class Chapter(UUIDPk, Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("lecture_id", "idx"),
        CheckConstraint("idx >= 0", name="idx_nonneg"),
        CheckConstraint("page_end >= page_start", name="page_range"),
    )

    lecture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"))
    idx: Mapped[int]
    title: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int]
    page_end: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int]
    # Không còn sinh từ ADR-0017 (giữ cho dữ liệu cũ); kết quả nằm ở bảng lessons
    summary: Mapped[dict[str, Any] | None]
    slides: Mapped[list[Any] | None]

    lecture: Mapped[Lecture] = relationship(back_populates="chapters")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="chapter", order_by="Lesson.idx", passive_deletes=True
    )


LESSON_STATUSES = ("pending", "queued", "processing", "completed", "failed")
LESSON_STEPS = ("summarizing", "slides", "quiz")


class Lesson(UUIDPk, Base):
    """Bài nhỏ (2–8 trang) trong một chương; đơn vị tạo học liệu (ADR-0017)."""

    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint("lecture_id", "idx"),
        CheckConstraint("idx >= 0", name="idx_nonneg"),
        CheckConstraint("page_end >= page_start", name="page_range"),
        CheckConstraint(_in("status", LESSON_STATUSES), name="status_valid"),
        CheckConstraint(_in("progress_step", LESSON_STEPS), name="progress_step_valid"),
        Index("ix_lessons_chapter_idx", "chapter_id", "idx"),
    )

    lecture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"))
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    idx: Mapped[int]
    number: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int]
    page_end: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int]
    status: Mapped[str] = mapped_column(Text, server_default="pending", default="pending")
    progress_step: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[dict[str, Any] | None]
    slides: Mapped[dict[str, Any] | None]
    pptx_key: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), default=utcnow, onupdate=utcnow
    )

    chapter: Mapped[Chapter] = relationship(back_populates="lessons")


class Summary(UUIDPk, Base):
    __tablename__ = "summaries"

    lecture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lectures.id", ondelete="CASCADE"), unique=True
    )
    overview: Mapped[str] = mapped_column(Text)
    learning_objectives: Mapped[list[Any]]
    chapters: Mapped[list[Any]]
    content_md: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), default=utcnow)


class SlideDeck(UUIDPk, Base):
    __tablename__ = "slide_decks"

    lecture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lectures.id", ondelete="CASCADE"), unique=True
    )
    deck: Mapped[dict[str, Any]]
    pptx_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), default=utcnow)


class Quiz(UUIDPk, Base):
    __tablename__ = "quizzes"
    __table_args__ = (
        CheckConstraint(_in("status", LECTURE_STATUSES), name="status_valid"),
        CheckConstraint("num_questions BETWEEN 1 AND 30", name="num_questions_valid"),
        Index("ix_quizzes_lecture_created", "lecture_id", text("created_at DESC")),
    )

    lecture_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"))
    # Quiz của một bài (ADR-0017); NULL với quiz tổng hợp hoặc quiz cũ
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), index=True
    )
    # Phạm vi quiz tổng hợp: danh sách lesson_id (chuỗi)
    lesson_ids: Mapped[list[Any] | None]
    status: Mapped[str] = mapped_column(Text, server_default="queued", default="queued")
    num_questions: Mapped[int]
    is_default: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    # Lần lưu chỉnh sửa gần nhất (ADR-0018)
    edited_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), default=utcnow)

    lecture: Mapped[Lecture] = relationship()
    questions: Mapped[list["Question"]] = relationship(
        order_by="Question.position", passive_deletes=True
    )


class Question(UUIDPk, Base):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("quiz_id", "position"),
        CheckConstraint("jsonb_array_length(options) = 4", name="options_len"),
        CheckConstraint("answer_index BETWEEN 0 AND 3", name="answer_index_range"),
        CheckConstraint(_in("source", QUESTION_SOURCES), name="source_valid"),
    )

    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"))
    position: Mapped[int]
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[list[Any]]
    answer_index: Mapped[int] = mapped_column(SmallInteger)
    explanation: Mapped[str] = mapped_column(Text)
    # NULL với câu nhập tay không ghi trang (ADR-0018)
    page_ref: Mapped[int | None]
    chapter_idx: Mapped[int]
    source: Mapped[str] = mapped_column(Text, server_default="ai", default="ai")


class QuizAttempt(UUIDPk, Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        CheckConstraint("score >= 0", name="score_nonneg"),
        CheckConstraint("total > 0", name="total_pos"),
        Index("ix_attempts_quiz_created", "quiz_id", text("created_at DESC")),
    )

    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    answers: Mapped[dict[str, Any]]
    score: Mapped[int]
    total: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), default=utcnow)

    quiz: Mapped[Quiz] = relationship()
