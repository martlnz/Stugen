"""Bài nhỏ (ADR-0017): mục lục, chọn bài để tạo học liệu, nội dung từng bài."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.generators.lesson import summary_markdown
from app.core.errors import LESSON_NOT_FOUND, AppError
from app.db.models import Chapter, Lecture, Lesson, Quiz, User, utcnow
from app.schemas.content import (
    ChapterOutline,
    LessonAvailable,
    LessonOut,
    LessonSlidesOut,
    LessonSummaryOut,
    OutlineOut,
    SectionRef,
)
from app.schemas.lecture import LectureError
from app.schemas.llm import LessonSummaryLLM
from app.services.jobs import enqueue_generate_lesson

GENERATABLE = ("pending", "failed")


async def get_owned_lesson(db: AsyncSession, user: User, lesson_id: str) -> tuple[Lesson, Lecture]:
    """Bài không tồn tại hoặc thuộc bài giảng của người khác → 404."""
    try:
        lid = uuid.UUID(lesson_id)
    except ValueError:
        raise AppError(*LESSON_NOT_FOUND, 404) from None
    row = (
        await db.execute(
            select(Lesson, Lecture)
            .join(Lecture, Lecture.id == Lesson.lecture_id)
            .where(Lesson.id == lid, Lecture.user_id == user.id)
        )
    ).first()
    if row is None:
        raise AppError(*LESSON_NOT_FOUND, 404)
    return row[0], row[1]


def _lesson_out(lesson: Lesson, has_quiz: bool) -> LessonOut:
    error = None
    if lesson.status == "failed":
        error = LectureError(
            code=lesson.error_code or "INTERNAL", message=lesson.error_message or ""
        )
    sections: list[SectionRef] = []
    if lesson.summary:
        sections = [
            SectionRef(title=s["title"], page_start=s["page_start"], page_end=s["page_end"])
            for s in lesson.summary.get("sections", [])
        ]
    return LessonOut(
        id=lesson.id,
        idx=lesson.idx,
        number=lesson.number,
        title=lesson.title,
        page_start=lesson.page_start,
        page_end=lesson.page_end,
        status=lesson.status,  # type: ignore[arg-type]
        progress_step=lesson.progress_step,  # type: ignore[arg-type]
        error=error,
        available=LessonAvailable(
            summary=lesson.summary is not None,
            slides=lesson.slides is not None,
            pptx=lesson.pptx_key is not None,
            quiz=has_quiz,
        ),
        sections=sections,
    )


async def outline(db: AsyncSession, lecture: Lecture) -> OutlineOut:
    chapters = list(
        await db.scalars(
            select(Chapter).where(Chapter.lecture_id == lecture.id).order_by(Chapter.idx)
        )
    )
    lessons = list(
        await db.scalars(select(Lesson).where(Lesson.lecture_id == lecture.id).order_by(Lesson.idx))
    )
    with_quiz = set(
        await db.scalars(
            select(Quiz.lesson_id).where(
                Quiz.lecture_id == lecture.id,
                Quiz.lesson_id.is_not(None),
                Quiz.status == "completed",
            )
        )
    )
    by_chapter: dict[uuid.UUID, list[LessonOut]] = {}
    for lesson in lessons:
        by_chapter.setdefault(lesson.chapter_id, []).append(
            _lesson_out(lesson, lesson.id in with_quiz)
        )
    return OutlineOut(
        lecture_id=lecture.id,
        chapters=[
            ChapterOutline(
                id=ch.id,
                idx=ch.idx,
                title=ch.title,
                page_start=ch.page_start,
                page_end=ch.page_end,
                lessons=by_chapter.get(ch.id, []),
            )
            for ch in chapters
            if ch.id in by_chapter
        ],
    )


async def generate(db: AsyncSession, lecture: Lecture, lesson_ids: list[uuid.UUID]) -> OutlineOut:
    """Xếp hàng tạo học liệu cho các bài đã chọn; bài đang chạy/đã xong được bỏ qua."""
    if lecture.status != "completed":
        raise AppError("LECTURE_NOT_READY", "Mục lục bài giảng chưa sẵn sàng.", 409)
    lessons = list(
        await db.scalars(
            select(Lesson).where(Lesson.lecture_id == lecture.id, Lesson.id.in_(lesson_ids))
        )
    )
    if len(lessons) != len(set(lesson_ids)):
        raise AppError(
            "VALIDATION_ERROR",
            "Dữ liệu không hợp lệ.",
            422,
            errors=[{"field": "lesson_ids", "message": "Có bài không thuộc bài giảng này."}],
        )
    queued = [lesson for lesson in lessons if lesson.status in GENERATABLE]
    for lesson in queued:
        lesson.status = "queued"
        lesson.progress_step = None
        lesson.error_code = None
        lesson.error_message = None
        lesson.updated_at = utcnow()
    await db.commit()
    for lesson in sorted(queued, key=lambda x: x.idx):
        enqueue_generate_lesson(lesson.id)
    return await outline(db, lecture)


def lesson_summary(lesson: Lesson) -> LessonSummaryOut:
    if lesson.summary is None:
        raise AppError("LESSON_NOT_READY", "Bài học chưa được tạo nội dung.", 409)
    summary = LessonSummaryLLM.model_validate(lesson.summary)
    return LessonSummaryOut(
        lesson_id=lesson.id,
        number=lesson.number,
        title=lesson.title,
        page_start=lesson.page_start,
        page_end=lesson.page_end,
        overview=summary.overview,
        sections=summary.sections,
        terms=summary.terms,
        content_md=summary_markdown(summary),
    )


def lesson_slides(lesson: Lesson) -> LessonSlidesOut:
    if lesson.slides is None:
        raise AppError("LESSON_NOT_READY", "Bài học chưa được tạo nội dung.", 409)
    return LessonSlidesOut(
        lesson_id=lesson.id,
        deck=lesson.slides,  # type: ignore[arg-type]
        pptx_available=lesson.pptx_key is not None,
    )
