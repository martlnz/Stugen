from fastapi import APIRouter

from app.api import auth, content, health, lectures, me, quizzes

router = APIRouter()
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(me.router)
router.include_router(lectures.router)
router.include_router(content.router)
router.include_router(quizzes.router)
