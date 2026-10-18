import asyncio
import logging
import uuid
from pathlib import PurePath

import pymupdf
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import LECTURE_NOT_FOUND, AppError
from app.db.models import Lecture, Quiz, SlideDeck, Summary, User, utcnow
from app.schemas.lecture import LectureAvailable, LectureError, LectureOut, LectureSort
from app.services.jobs import enqueue_process_lecture
from app.services.storage import get_storage, lecture_prefix

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF-"


async def get_owned_lecture(db: AsyncSession, user: User, lecture_id: str) -> Lecture:
    """Bài giảng không tồn tại hoặc không thuộc người dùng → 404 (không phải 403)."""
    try:
        lid = uuid.UUID(lecture_id)
    except ValueError:
        raise AppError(*LECTURE_NOT_FOUND, 404) from None
    lecture = await db.scalar(select(Lecture).where(Lecture.id == lid, Lecture.user_id == user.id))
    if lecture is None:
        raise AppError(*LECTURE_NOT_FOUND, 404)
    return lecture


async def availability(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, LectureAvailable]:
    result = {i: LectureAvailable() for i in ids}
    if not ids:
        return result
    for lid in await db.scalars(select(Summary.lecture_id).where(Summary.lecture_id.in_(ids))):
        result[lid].summary = True
    rows = await db.execute(
        select(SlideDeck.lecture_id, SlideDeck.pptx_key).where(SlideDeck.lecture_id.in_(ids))
    )
    for lid, pptx_key in rows:
        result[lid].slides = True
        result[lid].pptx = pptx_key is not None
    quiz_ids = await db.scalars(
        select(Quiz.lecture_id)
        .where(Quiz.lecture_id.in_(ids), Quiz.status == "completed")
        .distinct()
    )
    for lid in quiz_ids:
        result[lid].quiz = True
    return result


def to_out(lecture: Lecture, available: LectureAvailable) -> LectureOut:
    error = None
    if lecture.status == "failed" and lecture.error_code:
        error = LectureError(code=lecture.error_code, message=lecture.error_message or "")
    return LectureOut(
        id=lecture.id,
        title=lecture.title,
        original_filename=lecture.original_filename,
        file_size=lecture.file_size,
        page_count=lecture.page_count,
        status=lecture.status,  # type: ignore[arg-type]
        progress_step=lecture.progress_step,  # type: ignore[arg-type]
        error=error,
        available=available,
        created_at=lecture.created_at,
        updated_at=lecture.updated_at,
        completed_at=lecture.completed_at,
    )


async def lecture_out(db: AsyncSession, lecture: Lecture) -> LectureOut:
    avail = await availability(db, [lecture.id])
    return to_out(lecture, avail[lecture.id])


def _inspect_pdf(data: bytes) -> tuple[int, str | None]:
    """Kiểm tra PDF upload (ADR-0007); trả (số trang, tiêu đề metadata)."""
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise AppError("PDF_CORRUPTED", "Không đọc được file PDF.") from None
    with doc:
        if doc.needs_pass or doc.is_encrypted:
            raise AppError("PDF_ENCRYPTED", "PDF có mật khẩu, vui lòng gỡ mật khẩu rồi tải lại.")
        pages = doc.page_count
        if pages < 1:
            raise AppError("PDF_CORRUPTED", "Không đọc được file PDF.")
        if pages > settings.max_pages:
            raise AppError("PDF_TOO_MANY_PAGES", f"Giáo trình vượt quá {settings.max_pages} trang.")
        meta_title = ((doc.metadata or {}).get("title") or "").strip() or None
    return pages, meta_title


def _default_title(filename: str, meta_title: str | None) -> str:
    stem = PurePath(filename).stem.strip() if filename else ""
    return (meta_title or stem or "Bài giảng không tên")[:200]


async def create_lecture(
    db: AsyncSession, user: User, data: bytes, filename: str, title: str | None
) -> Lecture:
    if len(data) > settings.max_upload_bytes:
        raise AppError("FILE_TOO_LARGE", f"File vượt quá {settings.max_upload_mb} MB.", 413)
    if not data.startswith(PDF_MAGIC):
        raise AppError("INVALID_FILE_TYPE", "File không phải PDF.")
    page_count, meta_title = await asyncio.to_thread(_inspect_pdf, data)

    title = (title or "").strip() or _default_title(filename, meta_title)
    if len(title) > 200:
        raise AppError("VALIDATION_ERROR", "Tên bài giảng tối đa 200 ký tự.", 422)

    lecture_id = uuid.uuid4()
    pdf_key = f"{lecture_prefix(user.id, lecture_id)}source.pdf"
    await asyncio.to_thread(get_storage().put, pdf_key, data, "application/pdf")

    lecture = Lecture(
        id=lecture_id,
        user_id=user.id,
        title=title,
        original_filename=filename or "giao-trinh.pdf",
        pdf_key=pdf_key,
        file_size=len(data),
        page_count=page_count,
        status="queued",
    )
    db.add(lecture)
    await db.commit()
    enqueue_process_lecture(lecture.id)
    return lecture


async def list_lectures(
    db: AsyncSession,
    user: User,
    *,
    q: str | None,
    status: str | None,
    sort: LectureSort,
    page: int,
    page_size: int,
) -> tuple[list[LectureOut], int]:
    stmt = select(Lecture).where(Lecture.user_id == user.id)
    if q:
        stmt = stmt.where(Lecture.title.ilike(f"%{q}%"))
    if status:
        stmt = stmt.where(Lecture.status == status)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = {
        "-created_at": Lecture.created_at.desc(),
        "created_at": Lecture.created_at.asc(),
        "title": Lecture.title.asc(),
        "-title": Lecture.title.desc(),
    }[sort]
    lectures = list(
        await db.scalars(stmt.order_by(order).offset((page - 1) * page_size).limit(page_size))
    )
    avail = await availability(db, [lec.id for lec in lectures])
    return [to_out(lec, avail[lec.id]) for lec in lectures], total


async def rename_lecture(db: AsyncSession, lecture: Lecture, title: str) -> Lecture:
    lecture.title = title
    lecture.updated_at = utcnow()
    await db.commit()
    return lecture


async def delete_lecture(db: AsyncSession, lecture: Lecture) -> None:
    prefix = lecture_prefix(lecture.user_id, lecture.id)
    await db.delete(lecture)
    await db.commit()
    try:
        await asyncio.to_thread(get_storage().delete_prefix, prefix)
    except Exception:
        # File mồ côi được dọn bằng tác vụ định kỳ (ADR-0007); không chặn người dùng
        logger.exception("Failed to delete storage prefix %s", prefix)


async def retry_lecture(db: AsyncSession, lecture: Lecture) -> Lecture:
    if lecture.status != "failed":
        raise AppError("LECTURE_NOT_FAILED", "Chỉ thử lại được bài giảng bị lỗi.", 409)
    lecture.status = "queued"
    lecture.error_code = None
    lecture.error_message = None
    lecture.updated_at = utcnow()
    await db.commit()
    enqueue_process_lecture(lecture.id)
    return lecture
