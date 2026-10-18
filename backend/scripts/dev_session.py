"""CHỈ DÙNG LOCAL: tạo user + phiên để thử luồng cần đăng nhập mà không qua Google.

    docker compose exec api python -m scripts.dev_session [email]

In ra token cho cookie `sid` (dùng với curl: -b "sid=<token>").
"""

import asyncio
import sys

from sqlalchemy import select

from app.db.models import User
from app.db.session import AsyncSessionLocal
from app.services.auth import create_session


async def main(email: str) -> None:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.google_id == f"dev:{email}"))
        if user is None:
            user = User(google_id=f"dev:{email}", email=email, name=email.split("@")[0])
            db.add(user)
            await db.flush()
        token = await create_session(db, user)
        await db.commit()
    print(token)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "dev@example.com"))
