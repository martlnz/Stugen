import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ATTEMPT_NOT_FOUND, QUIZ_NOT_FOUND, AppError
from app.db.models import Chapter, Lecture, Question, Quiz, QuizAttempt, User
from app.schemas.content import (
    AttemptListItem,
    AttemptResult,
    ChapterScore,
    QuestionPublic,
    QuestionResult,
    QuizDetail,
    QuizSummary,
)
from app.schemas.lecture import LectureError
from app.services.jobs import enqueue_generate_quiz


def _uuid_or_404(value: str, err: tuple[str, str]) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise AppError(*err, 404) from None


async def get_owned_quiz(db: AsyncSession, user: User, quiz_id: str) -> tuple[Quiz, Lecture]:
    qid = _uuid_or_404(quiz_id, QUIZ_NOT_FOUND)
    row = (
        await db.execute(
            select(Quiz, Lecture)
            .join(Lecture, Lecture.id == Quiz.lecture_id)
            .where(Quiz.id == qid, Lecture.user_id == user.id)
        )
    ).first()
    if row is None:
        raise AppError(*QUIZ_NOT_FOUND, 404)
    return row[0], row[1]


async def _summaries(db: AsyncSession, quizzes: list[Quiz], user: User) -> list[QuizSummary]:
    ids = [q.id for q in quizzes]
    stats: dict[uuid.UUID, tuple[int, int | None, object]] = {}
    if ids:
        rows = await db.execute(
            select(
                QuizAttempt.quiz_id,
                func.count(),
                func.max(QuizAttempt.score),
                func.max(QuizAttempt.created_at),
            )
            .where(QuizAttempt.quiz_id.in_(ids), QuizAttempt.user_id == user.id)
            .group_by(QuizAttempt.quiz_id)
        )
        stats = {qid: (count, best, last) for qid, count, best, last in rows}
    items = []
    for q in quizzes:
        count, best, last = stats.get(q.id, (0, None, None))
        error = (
            LectureError(code="QUIZ_FAILED", message=q.error_message or "")
            if q.status == "failed"
            else None
        )
        items.append(
            QuizSummary(
                id=q.id,
                lecture_id=q.lecture_id,
                status=q.status,  # type: ignore[arg-type]
                num_questions=q.num_questions,
                is_default=q.is_default,
                error=error,
                attempt_count=count,
                best_score=best,
                last_attempt_at=last,  # type: ignore[arg-type]
                created_at=q.created_at,
            )
        )
    return items


async def list_quizzes(db: AsyncSession, user: User, lecture: Lecture) -> list[QuizSummary]:
    quizzes = list(
        await db.scalars(
            select(Quiz).where(Quiz.lecture_id == lecture.id).order_by(Quiz.created_at.desc())
        )
    )
    return await _summaries(db, quizzes, user)


async def create_quiz(
    db: AsyncSession, user: User, lecture: Lecture, num_questions: int
) -> QuizSummary:
    has_chapters = await db.scalar(
        select(func.count()).select_from(Chapter).where(Chapter.lecture_id == lecture.id)
    )
    if not has_chapters:
        raise AppError("LECTURE_NOT_READY", "Bài giảng chưa xử lý xong.", 409)
    quiz = Quiz(lecture_id=lecture.id, num_questions=num_questions, status="queued")
    db.add(quiz)
    await db.commit()
    enqueue_generate_quiz(quiz.id)
    return (await _summaries(db, [quiz], user))[0]


async def quiz_detail(db: AsyncSession, quiz: Quiz, lecture: Lecture) -> QuizDetail:
    if quiz.status != "completed":
        raise AppError("QUIZ_NOT_READY", "Quiz chưa được tạo xong.", 409)
    questions = await db.scalars(
        select(Question).where(Question.quiz_id == quiz.id).order_by(Question.position)
    )
    return QuizDetail(
        id=quiz.id,
        lecture_id=lecture.id,
        lecture_title=lecture.title,
        num_questions=quiz.num_questions,
        questions=[
            QuestionPublic(
                id=q.id,
                position=q.position,
                question=q.question,
                options=q.options,
                page_ref=q.page_ref,
            )
            for q in questions
        ],
    )


async def delete_quiz(db: AsyncSession, quiz: Quiz) -> None:
    await db.delete(quiz)
    await db.commit()


async def _result(db: AsyncSession, attempt: QuizAttempt, lecture: Lecture) -> AttemptResult:
    questions = list(
        await db.scalars(
            select(Question).where(Question.quiz_id == attempt.quiz_id).order_by(Question.position)
        )
    )
    chapters = {
        c.idx: c.title
        for c in await db.scalars(select(Chapter).where(Chapter.lecture_id == lecture.id))
    }
    results: list[QuestionResult] = []
    by_chapter: dict[int, list[int]] = {}
    for q in questions:
        selected = attempt.answers.get(str(q.id))
        correct = selected == q.answer_index
        results.append(
            QuestionResult(
                question_id=q.id,
                position=q.position,
                question=q.question,
                options=q.options,
                selected_index=selected,
                correct_index=q.answer_index,
                is_correct=correct,
                explanation=q.explanation,
                page_ref=q.page_ref,
            )
        )
        bucket = by_chapter.setdefault(q.chapter_idx, [0, 0])
        bucket[0] += int(correct)
        bucket[1] += 1
    return AttemptResult(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        lecture_id=lecture.id,
        lecture_title=lecture.title,
        score=attempt.score,
        total=attempt.total,
        created_at=attempt.created_at,
        results=results,
        by_chapter=[
            ChapterScore(
                chapter_idx=idx, title=chapters.get(idx, f"Chương {idx + 1}"), correct=c, total=t
            )
            for idx, (c, t) in sorted(by_chapter.items())
        ],
    )


def _validation(field: str, message: str) -> AppError:
    return AppError(
        "VALIDATION_ERROR",
        "Dữ liệu không hợp lệ.",
        422,
        errors=[{"field": field, "message": message}],
    )


async def submit_attempt(
    db: AsyncSession,
    user: User,
    quiz: Quiz,
    lecture: Lecture,
    answers: dict[uuid.UUID, int | None],
) -> AttemptResult:
    """Chấm điểm phía server; câu bỏ trống hoặc không gửi tính sai (ADR-0012)."""
    if quiz.status != "completed":
        raise AppError("QUIZ_NOT_READY", "Quiz chưa được tạo xong.", 409)
    questions = list(await db.scalars(select(Question).where(Question.quiz_id == quiz.id)))
    by_id = {q.id: q for q in questions}
    for qid, value in answers.items():
        if qid not in by_id:
            raise _validation(f"answers.{qid}", "Câu hỏi không thuộc quiz này.")
        if value is not None and not 0 <= value <= 3:
            raise _validation(f"answers.{qid}", "Lựa chọn phải từ 0 đến 3.")
    stored = {str(q.id): answers.get(q.id) for q in questions}
    score = sum(1 for q in questions if stored[str(q.id)] == q.answer_index)
    attempt = QuizAttempt(
        quiz_id=quiz.id, user_id=user.id, answers=stored, score=score, total=len(questions)
    )
    db.add(attempt)
    await db.commit()
    return await _result(db, attempt, lecture)


async def list_attempts(
    db: AsyncSession, user: User, quiz: Quiz, page: int, page_size: int
) -> tuple[list[AttemptListItem], int]:
    base = select(QuizAttempt).where(QuizAttempt.quiz_id == quiz.id, QuizAttempt.user_id == user.id)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = await db.scalars(
        base.order_by(QuizAttempt.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    items = [
        AttemptListItem(id=a.id, score=a.score, total=a.total, created_at=a.created_at)
        for a in rows
    ]
    return items, total


async def get_attempt(db: AsyncSession, user: User, attempt_id: str) -> AttemptResult:
    aid = _uuid_or_404(attempt_id, ATTEMPT_NOT_FOUND)
    row = (
        await db.execute(
            select(QuizAttempt, Lecture)
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .join(Lecture, Lecture.id == Quiz.lecture_id)
            .where(
                QuizAttempt.id == aid,
                QuizAttempt.user_id == user.id,
                Lecture.user_id == user.id,
            )
        )
    ).first()
    if row is None:
        raise AppError(*ATTEMPT_NOT_FOUND, 404)
    return await _result(db, row[0], row[1])
