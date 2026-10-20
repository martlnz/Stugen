from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.models import Lecture, Quiz, User
from app.db.session import get_db
from app.schemas.content import (
    AttemptCreate,
    AttemptPage,
    AttemptResult,
    QuizDetail,
    QuizEditable,
    QuizQuestionsUpdate,
)
from app.services import quizzes as service

router = APIRouter(tags=["quizzes"])


async def owned_quiz(
    quiz_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[Quiz, Lecture]:
    return await service.get_owned_quiz(db, user, quiz_id)


@router.get("/quizzes/{quiz_id}", response_model=QuizDetail)
async def get_quiz(
    owned: tuple[Quiz, Lecture] = Depends(owned_quiz), db: AsyncSession = Depends(get_db)
) -> QuizDetail:
    return await service.quiz_detail(db, *owned)


@router.get("/quizzes/{quiz_id}/edit", response_model=QuizEditable)
async def get_quiz_for_edit(
    owned: tuple[Quiz, Lecture] = Depends(owned_quiz),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizEditable:
    return await service.quiz_for_edit(db, user, *owned)


@router.put("/quizzes/{quiz_id}/questions", response_model=QuizEditable)
async def update_questions(
    body: QuizQuestionsUpdate,
    owned: tuple[Quiz, Lecture] = Depends(owned_quiz),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizEditable:
    return await service.update_questions(db, user, owned[0], owned[1], body)


@router.delete("/quizzes/{quiz_id}", status_code=204)
async def delete_quiz(
    owned: tuple[Quiz, Lecture] = Depends(owned_quiz), db: AsyncSession = Depends(get_db)
) -> Response:
    await service.delete_quiz(db, owned[0])
    return Response(status_code=204)


@router.post("/quizzes/{quiz_id}/attempts", status_code=201, response_model=AttemptResult)
async def submit_attempt(
    body: AttemptCreate,
    owned: tuple[Quiz, Lecture] = Depends(owned_quiz),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AttemptResult:
    return await service.submit_attempt(db, user, owned[0], owned[1], body.answers)


@router.get("/quizzes/{quiz_id}/attempts", response_model=AttemptPage)
async def list_attempts(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    owned: tuple[Quiz, Lecture] = Depends(owned_quiz),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AttemptPage:
    items, total = await service.list_attempts(db, user, owned[0], page, page_size)
    return AttemptPage(items=items, page=page, page_size=page_size, total=total)


@router.get("/attempts/{attempt_id}", response_model=AttemptResult)
async def get_attempt(
    attempt_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AttemptResult:
    return await service.get_attempt(db, user, attempt_id)
