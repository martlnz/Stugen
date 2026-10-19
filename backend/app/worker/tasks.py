import logging
import uuid

import botocore.exceptions
import redis.exceptions
import sqlalchemy.exc
from celery import Task

from app.ai.llm import get_llm
from app.db.session import sync_session
from app.services.storage import get_storage
from app.worker.celery_app import celery_app
from app.worker.pipeline import (
    LecturePipeline,
    mark_failed,
    mark_lesson_failed,
    mark_quiz_failed,
)

logger = logging.getLogger(__name__)

# Celery chỉ retry lỗi hạ tầng; lỗi LLM đã được LLMClient xử lý (ADR-0015)
INFRA_ERRORS = (
    sqlalchemy.exc.OperationalError,
    sqlalchemy.exc.InterfaceError,
    redis.exceptions.ConnectionError,
    botocore.exceptions.EndpointConnectionError,
    botocore.exceptions.ConnectionClosedError,
)
MAX_INFRA_RETRIES = 2


def _pipeline_for(db) -> LecturePipeline:  # type: ignore[no-untyped-def]
    return LecturePipeline(db, get_llm(), get_storage())


@celery_app.task(name="app.worker.tasks.ping")
def ping() -> str:
    logger.info("pong")
    return "pong"


@celery_app.task(bind=True, name="app.worker.tasks.process_lecture")
def process_lecture(self: Task, lecture_id: str) -> None:
    lid = uuid.UUID(lecture_id)
    try:
        with sync_session() as db:
            _pipeline_for(db).run(lid)
    except INFRA_ERRORS as exc:
        if self.request.retries < MAX_INFRA_RETRIES:
            logger.warning("Infra error on lecture %s, retrying: %s", lecture_id, exc)
            raise self.retry(exc=exc, countdown=15 * (self.request.retries + 1)) from exc
        logger.exception("Infra error on lecture %s, giving up", lecture_id)
        _safe(lambda: _mark(lid))
    except Exception:
        logger.exception("Unexpected error processing lecture %s", lecture_id)
        _safe(lambda: _mark(lid))


@celery_app.task(bind=True, name="app.worker.tasks.generate_lesson")
def generate_lesson(self: Task, lesson_id: str) -> None:
    """Tóm tắt, slide, quiz mặc định cho một bài đã chọn (ADR-0017)."""
    lid = uuid.UUID(lesson_id)
    try:
        with sync_session() as db:
            _pipeline_for(db).run_lesson(lid)
    except INFRA_ERRORS as exc:
        if self.request.retries < MAX_INFRA_RETRIES:
            raise self.retry(exc=exc, countdown=15 * (self.request.retries + 1)) from exc
        _safe(lambda: _mark_lesson(lid))
    except Exception:
        logger.exception("Unexpected error generating lesson %s", lesson_id)
        _safe(lambda: _mark_lesson(lid))


@celery_app.task(bind=True, name="app.worker.tasks.generate_quiz")
def generate_quiz(self: Task, quiz_id: str) -> None:
    qid = uuid.UUID(quiz_id)
    try:
        with sync_session() as db:
            _pipeline_for(db).run_quiz(qid)
    except INFRA_ERRORS as exc:
        if self.request.retries < MAX_INFRA_RETRIES:
            raise self.retry(exc=exc, countdown=15 * (self.request.retries + 1)) from exc
        _safe(lambda: _mark_quiz(qid))
    except Exception:
        logger.exception("Unexpected error generating quiz %s", quiz_id)
        _safe(lambda: _mark_quiz(qid))


def _mark(lecture_id: uuid.UUID) -> None:
    with sync_session() as db:
        mark_failed(db, lecture_id)


def _mark_lesson(lesson_id: uuid.UUID) -> None:
    with sync_session() as db:
        mark_lesson_failed(db, lesson_id)


def _mark_quiz(quiz_id: uuid.UUID) -> None:
    with sync_session() as db:
        mark_quiz_failed(db, quiz_id)


def _safe(fn) -> None:  # type: ignore[no-untyped-def]
    try:
        fn()
    except Exception:
        logger.exception("Could not record failure")
