import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.common import HealthOut

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut, responses={503: {"model": HealthOut}})
async def health(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    result = {"status": "ok", "db": "ok", "redis": "ok"}
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unavailable")
        result["db"] = "error"
    try:
        redis = Redis.from_url(settings.redis_url)
        try:
            await redis.ping()
        finally:
            await redis.aclose()
    except Exception:
        logger.exception("Health check: redis unavailable")
        result["redis"] = "error"
    if "error" in result.values():
        result["status"] = "error"
        return JSONResponse(result, status_code=503)
    return JSONResponse(result)
