"""Tóm tắt, slide, quiz gắn với một bài giảng: /lectures/{id}/summary|slides|slides.pptx|quizzes."""

import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.lectures import content_disposition, owned_lecture
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.db.models import Lecture, SlideDeck, Summary, User
from app.db.session import get_db
from app.schemas.content import QuizCreate, QuizList, QuizSummary, SlidesOut, SummaryOut
from app.services import quizzes as quiz_service
from app.services.storage import ObjectNotFound, get_storage

router = APIRouter(prefix="/lectures/{lecture_id}", tags=["content"])

PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def not_ready() -> AppError:
    return AppError("LECTURE_NOT_READY", "Nội dung chưa được tạo xong.", 409)


@router.get("/summary", response_model=SummaryOut)
async def get_summary(
    lecture: Lecture = Depends(owned_lecture), db: AsyncSession = Depends(get_db)
) -> SummaryOut:
    summary = await db.scalar(select(Summary).where(Summary.lecture_id == lecture.id))
    if summary is None:
        raise not_ready()
    return SummaryOut.model_validate(summary, from_attributes=True)


@router.get("/slides", response_model=SlidesOut)
async def get_slides(
    lecture: Lecture = Depends(owned_lecture), db: AsyncSession = Depends(get_db)
) -> SlidesOut:
    deck = await db.scalar(select(SlideDeck).where(SlideDeck.lecture_id == lecture.id))
    if deck is None:
        raise not_ready()
    return SlidesOut(
        lecture_id=lecture.id,
        deck=deck.deck,  # type: ignore[arg-type]
        pptx_available=deck.pptx_key is not None,
        created_at=deck.created_at,
    )


@router.get(
    "/slides.pptx",
    response_class=StreamingResponse,
    responses={200: {"content": {PPTX_TYPE: {}}}},
)
async def download_pptx(
    lecture: Lecture = Depends(owned_lecture), db: AsyncSession = Depends(get_db)
) -> Response:
    key = await db.scalar(select(SlideDeck.pptx_key).where(SlideDeck.lecture_id == lecture.id))
    if not key:
        raise not_ready()
    try:
        obj = await asyncio.to_thread(get_storage().open, key)
    except ObjectNotFound:
        raise not_ready() from None
    return StreamingResponse(
        obj.body,
        media_type=PPTX_TYPE,
        headers={
            "Content-Length": str(obj.length),
            "Content-Disposition": content_disposition("attachment", f"{lecture.title}.pptx"),
        },
    )


@router.get("/quizzes", response_model=QuizList)
async def list_quizzes(
    lecture: Lecture = Depends(owned_lecture),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizList:
    return QuizList(items=await quiz_service.list_quizzes(db, user, lecture))


@router.post("/quizzes", status_code=202, response_model=QuizSummary)
async def create_quiz(
    body: QuizCreate | None = None,
    lecture: Lecture = Depends(owned_lecture),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizSummary:
    num = body.num_questions if body else 10
    return await quiz_service.create_quiz(db, user, lecture, num)
