import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ATTEMPT_NOT_FOUND, QUIZ_NOT_FOUND, AppError
from app.db.models import Chapter, Lecture, Lesson, Question, Quiz, QuizAttempt, User
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


def _validation(field: str, message: str) -> AppError:
    return AppError(
        "VALIDATION_ERROR",
        "Dữ liệu không hợp lệ.",
        422,
        errors=[{"field": field, "message": message}],
    )


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
                lesson_id=q.lesson_id,
                lesson_ids=[uuid.UUID(i) for i in q.lesson_ids] if q.lesson_ids else None,
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


async def list_quizzes(
    db: AsyncSession, user: User, lecture: Lecture, lesson: Lesson | None = None
) -> list[QuizSummary]:
    stmt = select(Quiz).where(Quiz.lecture_id == lecture.id)
    if lesson is not None:
        stmt = stmt.where(Quiz.lesson_id == lesson.id)
    quizzes = list(await db.scalars(stmt.order_by(Quiz.created_at.desc())))
    return await _summaries(db, quizzes, user)


async def _queue(db: AsyncSession, user: User, quiz: Quiz) -> QuizSummary:
    db.add(quiz)
    await db.commit()
    enqueue_generate_quiz(quiz.id)
    return (await _summaries(db, [quiz], user))[0]


async def create_lesson_quiz(
    db: AsyncSession, user: User, lesson: Lesson, num_questions: int
) -> QuizSummary:
    if lesson.summary is None:
        raise AppError("LESSON_NOT_READY", "Bài học chưa được tạo nội dung.", 409)
    quiz = Quiz(
        lecture_id=lesson.lecture_id,
        lesson_id=lesson.id,
        num_questions=num_questions,
        status="queued",
    )
    return await _queue(db, user, quiz)


async def create_scope_quiz(
    db: AsyncSession,
    user: User,
    lecture: Lecture,
    num_questions: int,
    lesson_ids: list[uuid.UUID],
) -> QuizSummary:
    """Quiz tổng hợp trên các bài người dùng chọn (đã tạo học liệu)."""
    lessons = list(
        await db.scalars(
            select(Lesson).where(Lesson.lecture_id == lecture.id, Lesson.id.in_(lesson_ids))
        )
    )
    if len(lessons) != len(set(lesson_ids)):
        raise _validation("lesson_ids", "Có bài không thuộc bài giảng này.")
    if any(lesson.summary is None for lesson in lessons):
        raise AppError("LESSON_NOT_READY", "Chỉ chọn được các bài đã tạo học liệu.", 409)
    quiz = Quiz(
        lecture_id=lecture.id,
        lesson_ids=[str(lesson.id) for lesson in sorted(lessons, key=lambda x: x.idx)],
        num_questions=num_questions,
        status="queued",
    )
    return await _queue(db, user, quiz)


async def _scope(db: AsyncSession, quiz: Quiz) -> tuple[str, dict[int, str]]:
    """(tên phạm vi, idx → tên bài/chương) để hiển thị và chấm điểm theo bài."""
    if quiz.lesson_id or quiz.lesson_ids:
        ids = [quiz.lesson_id] if quiz.lesson_id else [uuid.UUID(i) for i in quiz.lesson_ids or []]
        lessons = list(await db.scalars(select(Lesson).where(Lesson.id.in_(ids))))
        names = {ls.idx: f"{ls.number} {ls.title}" for ls in lessons}
        if quiz.lesson_id and lessons:
            return f"Bài {lessons[0].number}: {lessons[0].title}", names
        return f"Quiz tổng hợp {len(ids)} bài", names
    # Quiz định dạng cũ: chapter_idx là chỉ số chương
    chapters = await db.scalars(select(Chapter).where(Chapter.lecture_id == quiz.lecture_id))
    return "Toàn bài giảng", {c.idx: c.title for c in chapters}


async def quiz_detail(db: AsyncSession, quiz: Quiz, lecture: Lecture) -> QuizDetail:
    if quiz.status != "completed":
        raise AppError("QUIZ_NOT_READY", "Quiz chưa được tạo xong.", 409)
    questions = await db.scalars(
        select(Question).where(Question.quiz_id == quiz.id).order_by(Question.position)
    )
    scope_title, _ = await _scope(db, quiz)
    return QuizDetail(
        id=quiz.id,
        lecture_id=lecture.id,
        lecture_title=lecture.title,
        lesson_id=quiz.lesson_id,
        scope_title=scope_title,
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


async def _result(
    db: AsyncSession, attempt: QuizAttempt, quiz: Quiz, lecture: Lecture
) -> AttemptResult:
    questions = list(
        await db.scalars(
            select(Question).where(Question.quiz_id == attempt.quiz_id).order_by(Question.position)
        )
    )
    scope_title, names = await _scope(db, quiz)
    results: list[QuestionResult] = []
    by_unit: dict[int, list[int]] = {}
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
        bucket = by_unit.setdefault(q.chapter_idx, [0, 0])
        bucket[0] += int(correct)
        bucket[1] += 1
    return AttemptResult(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        lecture_id=lecture.id,
        lecture_title=lecture.title,
        lesson_id=quiz.lesson_id,
        scope_title=scope_title,
        score=attempt.score,
        total=attempt.total,
        created_at=attempt.created_at,
        results=results,
        by_chapter=[
            ChapterScore(
                chapter_idx=idx, title=names.get(idx, f"Phần {idx + 1}"), correct=c, total=t
            )
            for idx, (c, t) in sorted(by_unit.items())
        ],
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
    return await _result(db, attempt, quiz, lecture)


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
            select(QuizAttempt, Quiz, Lecture)
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
    return await _result(db, row[0], row[1], row[2])
