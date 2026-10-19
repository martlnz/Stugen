"""Đẩy job sang worker theo tên task (API không cần import code AI)."""

import uuid

from app.worker.celery_app import celery_app


def enqueue_process_lecture(lecture_id: uuid.UUID) -> None:
    celery_app.send_task("app.worker.tasks.process_lecture", args=[str(lecture_id)])


def enqueue_generate_lesson(lesson_id: uuid.UUID) -> None:
    celery_app.send_task("app.worker.tasks.generate_lesson", args=[str(lesson_id)])


def enqueue_generate_quiz(quiz_id: uuid.UUID) -> None:
    celery_app.send_task("app.worker.tasks.generate_quiz", args=[str(quiz_id)])
