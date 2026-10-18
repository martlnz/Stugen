"""Test chạy trên DB riêng `<POSTGRES_DB>_test`, storage trong bộ nhớ, không gọi LLM thật."""

import os
import re

_base_sync = os.environ.get(
    "DATABASE_URL_SYNC", "postgresql+psycopg://stugen:stugen@postgres/stugen"
)
_base_async = os.environ.get("DATABASE_URL", "postgresql+asyncpg://stugen:stugen@postgres/stugen")
TEST_DB = re.sub(r".*/", "", _base_sync) + "_test"
os.environ["DATABASE_URL_SYNC"] = re.sub(r"/[^/]+$", f"/{TEST_DB}", _base_sync)
os.environ["DATABASE_URL"] = re.sub(r"/[^/]+$", f"/{TEST_DB}", _base_async)
os.environ["LLM_PROVIDER"] = "fake"

import uuid  # noqa: E402
from collections.abc import AsyncIterator, Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.db.models import Base, User  # noqa: E402
from app.db.session import AsyncSessionLocal, sync_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import storage as storage_module  # noqa: E402
from app.services.auth import create_session  # noqa: E402
from tests.fakes import MemoryStorage  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def _test_database() -> Iterator[None]:
    admin_url = re.sub(r"/[^/]+$", "/postgres", _base_sync)
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
    admin.dispose()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    yield
    sync_engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    names = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    with sync_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} CASCADE"))


@pytest.fixture(autouse=True)
def memory_storage(monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    store = MemoryStorage()
    monkeypatch.setattr(storage_module, "_storage", store)
    return store


async def _make_user(name: str) -> tuple[User, str]:
    async with AsyncSessionLocal() as db:
        user = User(google_id=f"g-{uuid.uuid4()}", email=f"{name}@example.com", name=name)
        db.add(user)
        await db.flush()
        token = await create_session(db, user)
        await db.commit()
        return user, token


def _client(token: str | None) -> AsyncClient:
    client = AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Requested-With": "fetch"},
    )
    if token:
        client.cookies.set("sid", token)
    return client


@pytest.fixture
async def anon_client() -> AsyncIterator[AsyncClient]:
    async with _client(None) as client:
        yield client


@pytest.fixture
async def user_a() -> tuple[User, str]:
    return await _make_user("alice")


@pytest.fixture
async def user_b() -> tuple[User, str]:
    return await _make_user("bob")


@pytest.fixture
async def client_a(user_a: tuple[User, str]) -> AsyncIterator[AsyncClient]:
    async with _client(user_a[1]) as client:
        yield client


@pytest.fixture
async def client_b(user_b: tuple[User, str]) -> AsyncIterator[AsyncClient]:
    async with _client(user_b[1]) as client:
        yield client
