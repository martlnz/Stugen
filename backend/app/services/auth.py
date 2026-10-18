from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_token, new_session_token
from app.db.models import Session, User, utcnow


async def upsert_google_user(db: AsyncSession, claims: dict[str, Any]) -> User:
    """Tạo/cập nhật user theo `sub` của Google (không theo email)."""
    now = utcnow()
    user = await db.scalar(select(User).where(User.google_id == claims["sub"]))
    name = claims.get("name") or claims["email"].split("@")[0]
    if user is None:
        user = User(
            google_id=claims["sub"],
            email=claims["email"],
            name=name,
            avatar_url=claims.get("picture"),
            created_at=now,
            last_login_at=now,
        )
        db.add(user)
    else:
        user.email = claims["email"]
        user.name = name
        user.avatar_url = claims.get("picture")
        user.last_login_at = now
    await db.flush()
    return user


async def create_session(db: AsyncSession, user: User) -> str:
    token = new_session_token()
    db.add(
        Session(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=utcnow() + timedelta(days=settings.session_days),
        )
    )
    await db.flush()
    return token


async def resolve_session(db: AsyncSession, token: str) -> Session | None:
    """Trả phiên còn hạn; gia hạn (sliding) khi còn dưới `session_renew_days`."""
    now = utcnow()
    session = await db.scalar(select(Session).where(Session.token_hash == hash_token(token)))
    if session is None or session.expires_at <= now:
        return None
    if session.expires_at - now < timedelta(days=settings.session_renew_days):
        session.expires_at = now + timedelta(days=settings.session_days)
        await db.commit()
    return session


async def delete_session(db: AsyncSession, token: str) -> None:
    await db.execute(delete(Session).where(Session.token_hash == hash_token(token)))
    await db.commit()
