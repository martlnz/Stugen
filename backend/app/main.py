import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.sessions import SessionMiddleware

from app.api import router as api_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.services.storage import get_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        await asyncio.to_thread(get_storage().ensure_bucket)
    except Exception:
        logger.exception("Could not ensure storage bucket at startup")
    yield


app = FastAPI(
    title="Stugen API",
    version="0.1.0",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)
register_error_handlers(app)


@app.middleware("http")
async def csrf_guard(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
    """Request thay đổi dữ liệu phải có `X-Requested-With: fetch` (ADR-0005)."""
    if request.method in UNSAFE_METHODS and request.headers.get("x-requested-with") != "fetch":
        return JSONResponse(
            {"code": "CSRF_REJECTED", "detail": "Yêu cầu bị từ chối."}, status_code=403
        )
    return await call_next(request)


# Authlib lưu state + PKCE verifier của luồng OAuth trong cookie ký riêng (không phải `sid`)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="oauth_state",
    max_age=600,
    same_site="lax",
    https_only=settings.app_url.startswith("https://"),
)

app.include_router(api_router, prefix="/api")
