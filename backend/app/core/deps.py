from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import User
from app.db.session import get_db
from app.services.auth import resolve_session

SESSION_COOKIE = "sid"


async def get_current_user(
    sid: str | None = Cookie(default=None, include_in_schema=False),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not sid:
        raise AppError("UNAUTHENTICATED", "Bạn cần đăng nhập.", 401)
    session = await resolve_session(db, sid)
    if session is None:
        raise AppError("UNAUTHENTICATED", "Phiên đăng nhập đã hết hạn.", 401)
    return session.user
