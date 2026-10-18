from celery import Celery

from app.core.config import settings

celery_app = Celery("stugen", broker=settings.redis_url, include=["app.worker.tasks"])
celery_app.conf.update(
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=settings.celery_concurrency,
    task_time_limit=900,
    task_soft_time_limit=840,
    task_default_queue="default",
    task_routes={
        "app.worker.tasks.process_lecture": {"queue": "ai"},
        "app.worker.tasks.generate_quiz": {"queue": "ai"},
    },
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
)
