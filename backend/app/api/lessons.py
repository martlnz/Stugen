"""Nội dung một bài: /lessons/{id}/summary|slides|slides.pptx|quizzes (ADR-0017)."""

import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.lectures import content_disposition
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.db.models import Lecture, Lesson, User
from app.db.session import get_db
from app.schemas.content import (
    LessonSlidesOut,
    LessonSummaryOut,
    QuizCreate,
    QuizList,
    QuizSummary,
)
from app.services import lessons as service
from app.services import quizzes as quiz_service
from app.services.storage import ObjectNotFound, get_storage

router = APIRouter(prefix="/lessons/{lesson_id}", tags=["lessons"])

PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


async def owned_lesson(
    lesson_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[Lesson, Lecture]:
    return await service.get_owned_lesson(db, user, lesson_id)


@router.get("/summary", response_model=LessonSummaryOut)
async def get_summary(owned: tuple[Lesson, Lecture] = Depends(owned_lesson)) -> LessonSummaryOut:
    return service.lesson_summary(owned[0])


@router.get("/slides", response_model=LessonSlidesOut)
async def get_slides(owned: tuple[Lesson, Lecture] = Depends(owned_lesson)) -> LessonSlidesOut:
    return service.lesson_slides(owned[0])


@router.get(
    "/slides.pptx",
    response_class=StreamingResponse,
    responses={200: {"content": {PPTX_TYPE: {}}}},
)
async def download_pptx(owned: tuple[Lesson, Lecture] = Depends(owned_lesson)) -> Response:
    lesson = owned[0]
    if not lesson.pptx_key:
        raise AppError("LESSON_NOT_READY", "Bài học chưa có file PPTX.", 409)
    try:
        obj = await asyncio.to_thread(get_storage().open, lesson.pptx_key)
    except ObjectNotFound:
        raise AppError("LESSON_NOT_READY", "Bài học chưa có file PPTX.", 409) from None
    return StreamingResponse(
        obj.body,
        media_type=PPTX_TYPE,
        headers={
            "Content-Length": str(obj.length),
            "Content-Disposition": content_disposition(
                "attachment", f"{lesson.number} {lesson.title}.pptx"
            ),
        },
    )


@router.get("/quizzes", response_model=QuizList)
async def list_quizzes(
    owned: tuple[Lesson, Lecture] = Depends(owned_lesson),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizList:
    lesson, lecture = owned
    return QuizList(items=await quiz_service.list_quizzes(db, user, lecture, lesson))


@router.post("/quizzes", status_code=202, response_model=QuizSummary)
async def create_quiz(
    body: QuizCreate | None = None,
    owned: tuple[Lesson, Lecture] = Depends(owned_lesson),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizSummary:
    num = body.num_questions if body else 10
    return await quiz_service.create_lesson_quiz(db, user, owned[0], num)
