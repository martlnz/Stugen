"""Mục lục, chọn bài để tạo học liệu, quiz tổng hợp của một bài giảng (ADR-0017)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.lectures import owned_lecture
from app.core.deps import get_current_user
from app.db.models import Lecture, User
from app.db.session import get_db
from app.schemas.content import (
    GenerateLessons,
    LectureQuizCreate,
    OutlineOut,
    QuizList,
    QuizSummary,
)
from app.schemas.lecture import LectureOut
from app.services import lectures as lecture_service
from app.services import lessons as lesson_service
from app.services import quizzes as quiz_service

router = APIRouter(prefix="/lectures/{lecture_id}", tags=["content"])


@router.get("/outline", response_model=OutlineOut)
async def get_outline(
    lecture: Lecture = Depends(owned_lecture), db: AsyncSession = Depends(get_db)
) -> OutlineOut:
    return await lesson_service.outline(db, lecture)


@router.post("/lessons/generate", status_code=202, response_model=OutlineOut)
async def generate_lessons(
    body: GenerateLessons,
    lecture: Lecture = Depends(owned_lecture),
    db: AsyncSession = Depends(get_db),
) -> OutlineOut:
    return await lesson_service.generate(db, lecture, body.lesson_ids)


@router.post("/regenerate", status_code=202, response_model=LectureOut)
async def regenerate(
    lecture: Lecture = Depends(owned_lecture), db: AsyncSession = Depends(get_db)
) -> LectureOut:
    await lecture_service.regenerate_lecture(db, lecture)
    return await lecture_service.lecture_out(db, lecture)


@router.get("/quizzes", response_model=QuizList)
async def list_quizzes(
    lecture: Lecture = Depends(owned_lecture),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizList:
    return QuizList(items=await quiz_service.list_quizzes(db, user, lecture))


@router.post("/quizzes", status_code=202, response_model=QuizSummary)
async def create_scope_quiz(
    body: LectureQuizCreate,
    lecture: Lecture = Depends(owned_lecture),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizSummary:
    return await quiz_service.create_scope_quiz(
        db, user, lecture, body.num_questions, body.lesson_ids
    )
