import asyncio
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.db.models import Lecture, User
from app.db.session import get_db
from app.schemas.lecture import (
    LectureOut,
    LecturePage,
    LectureSort,
    LectureStatus,
    LectureUpdate,
)
from app.services import lectures as service
from app.services.storage import InvalidRange, ObjectNotFound, get_storage

router = APIRouter(prefix="/lectures", tags=["lectures"])


async def owned_lecture(
    lecture_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Lecture:
    return await service.get_owned_lecture(db, user, lecture_id)


def content_disposition(kind: str, filename: str) -> str:
    """Tên file giữ tiếng Việt theo RFC 5987, kèm bản ASCII dự phòng."""
    ascii_name = filename.encode("ascii", "ignore").decode().replace('"', "") or "file"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


@router.post("", status_code=201, response_model=LectureOut)
async def upload_lecture(
    response: Response,
    file: Annotated[UploadFile, File(description="PDF ≤ 20 MB, ≤ 200 trang")],
    title: Annotated[str | None, Form(max_length=200)] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LectureOut:
    data = await file.read(settings.max_upload_bytes + 1)
    lecture = await service.create_lecture(db, user, data, file.filename or "", title)
    response.headers["Location"] = f"/api/lectures/{lecture.id}"
    return await service.lecture_out(db, lecture)


@router.get("", response_model=LecturePage)
async def list_lectures(
    q: Annotated[str | None, Query(max_length=200)] = None,
    status: LectureStatus | None = None,
    sort: LectureSort = "-created_at",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LecturePage:
    items, total = await service.list_lectures(
        db, user, q=q, status=status, sort=sort, page=page, page_size=page_size
    )
    return LecturePage(items=items, page=page, page_size=page_size, total=total)


@router.get("/{lecture_id}", response_model=LectureOut)
async def get_lecture(
    lecture: Lecture = Depends(owned_lecture), db: AsyncSession = Depends(get_db)
) -> LectureOut:
    return await service.lecture_out(db, lecture)


@router.patch("/{lecture_id}", response_model=LectureOut)
async def update_lecture(
    body: LectureUpdate,
    lecture: Lecture = Depends(owned_lecture),
    db: AsyncSession = Depends(get_db),
) -> LectureOut:
    await service.rename_lecture(db, lecture, body.title)
    return await service.lecture_out(db, lecture)


@router.delete("/{lecture_id}", status_code=204)
async def delete_lecture(
    lecture: Lecture = Depends(owned_lecture), db: AsyncSession = Depends(get_db)
) -> Response:
    await service.delete_lecture(db, lecture)
    return Response(status_code=204)


@router.post("/{lecture_id}/retry", status_code=202, response_model=LectureOut)
async def retry_lecture(
    lecture: Lecture = Depends(owned_lecture), db: AsyncSession = Depends(get_db)
) -> LectureOut:
    await service.retry_lecture(db, lecture)
    return await service.lecture_out(db, lecture)


@router.get(
    "/{lecture_id}/pdf",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/pdf": {}}}, 206: {"description": "Partial"}},
)
async def get_pdf(
    download: bool = False,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
    lecture: Lecture = Depends(owned_lecture),
) -> Response:
    try:
        obj = await asyncio.to_thread(get_storage().open, lecture.pdf_key, range_header)
    except InvalidRange:
        return Response(status_code=416, headers={"Content-Range": "bytes */*"})
    except ObjectNotFound:
        raise AppError("LECTURE_NOT_FOUND", "Không tìm thấy file PDF.", 404) from None
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(obj.length),
        "Content-Disposition": content_disposition(
            "attachment" if download else "inline", lecture.original_filename
        ),
        "Cache-Control": "private, max-age=3600",
    }
    if obj.content_range:
        headers["Content-Range"] = obj.content_range
    return StreamingResponse(
        obj.body,
        status_code=206 if obj.content_range else 200,
        media_type="application/pdf",
        headers=headers,
    )
