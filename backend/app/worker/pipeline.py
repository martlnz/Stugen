"""Điều phối xử lý (ADR-0008, ADR-0015, ADR-0017). Mọi bước idempotent: có kết quả thì bỏ qua.

- `LecturePipeline.run`: tách mục lục chương → bài ngay sau khi tải lên.
- `LecturePipeline.run_lesson`: tạo tóm tắt, slide (+ PPTX), quiz mặc định cho một bài đã chọn.
- `LecturePipeline.run_quiz`: sinh quiz thêm (của một bài hoặc tổng hợp nhiều bài).
"""

import logging
import random
import uuid
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.ai.generators import lesson as lesson_gen
from app.ai.generators import quiz as quiz_gen
from app.ai.generators.pptx import build_pptx
from app.ai.llm import LLMClient, LLMError
from app.ai.pdf import ExtractedChapter, PdfError, extract_outline
from app.core.config import settings
from app.db.models import Chapter, Lecture, Lesson, Question, Quiz, utcnow
from app.schemas.llm import LessonSlidesLLM, LessonSummaryLLM
from app.services.storage import Storage, lecture_prefix

logger = logging.getLogger(__name__)

ERROR_MESSAGES = {
    "PDF_NO_TEXT": "Giáo trình có vẻ là bản scan, hiện chưa được hỗ trợ.",
    "PDF_CORRUPTED": "Không đọc được file PDF.",
    "LLM_UNAVAILABLE": "Dịch vụ AI tạm thời gián đoạn, vui lòng thử lại sau.",
    "LLM_INVALID_OUTPUT": "Không tạo được nội dung, vui lòng thử lại.",
    "TIMEOUT": "Xử lý quá lâu, vui lòng thử lại.",
    "INTERNAL": "Đã xảy ra lỗi, vui lòng thử lại.",
}
PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class Gone(Exception):
    """Bài giảng/bài/quiz đã bị xoá trong lúc xử lý → dừng ở bước kế tiếp."""


def _parallel[T, R](
    items: Iterable[T], work: Callable[[T], R], on_result: Callable[[T, R], None]
) -> None:
    """Gọi LLM song song (≤ LLM_MAX_CONCURRENCY); ghi kết quả ở luồng chính ngay khi xong.

    Lỗi ở một phần không huỷ các phần đang chạy; lỗi đầu tiên được ném ra sau cùng.
    """
    items = list(items)
    if not items:
        return
    first_error: BaseException | None = None
    with ThreadPoolExecutor(max_workers=max(1, settings.llm_max_concurrency)) as pool:
        futures = {pool.submit(work, item): item for item in items}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:
                first_error = first_error or exc
                continue
            on_result(futures[future], result)
    if first_error:
        raise first_error


def lesson_pptx_key(lecture: Lecture, lesson: Lesson) -> str:
    return f"{lecture_prefix(lecture.user_id, lecture.id)}lessons/{lesson.id}.pptx"


class LecturePipeline:
    def __init__(self, db: Session, llm: LLMClient, storage: Storage) -> None:
        self.db = db
        self.llm = llm
        self.storage = storage

    def _commit(self) -> None:
        try:
            self.db.commit()
        except (IntegrityError, StaleDataError) as exc:
            # FK tới bản ghi đã bị xoá, hoặc cập nhật bản ghi đã bị xoá
            self.db.rollback()
            raise Gone() from exc

    def _exists(self, model: type[Lecture] | type[Lesson] | type[Quiz], id_: uuid.UUID) -> None:
        if self.db.scalar(select(model.id).where(model.id == id_)) is None:
            raise Gone()

    # ---------- Tách mục lục ----------

    def _refine(self, chapter: ExtractedChapter):  # type: ignore[no-untyped-def]
        return lesson_gen.outline_hint(self.llm, chapter)

    def ensure_outline(self, lecture: Lecture) -> None:
        has_lessons = self.db.scalar(select(Lesson.id).where(Lesson.lecture_id == lecture.id))
        if has_lessons:
            return
        # Chương định dạng cũ (chưa có bài) được tách lại từ đầu
        self.db.execute(delete(Chapter).where(Chapter.lecture_id == lecture.id))
        data = self.storage.get_bytes(lecture.pdf_key)
        extracted = extract_outline(data, refine=self._refine, workers=settings.llm_max_concurrency)
        lesson_idx = 0
        for ci, ch in enumerate(extracted):
            chapter = Chapter(
                lecture_id=lecture.id,
                idx=ci,
                title=ch.title,
                page_start=ch.page_start,
                page_end=ch.page_end,
                text=ch.text,
                char_count=ch.char_count,
            )
            self.db.add(chapter)
            self.db.flush()
            for li, ls in enumerate(ch.lessons):
                self.db.add(
                    Lesson(
                        lecture_id=lecture.id,
                        chapter_id=chapter.id,
                        idx=lesson_idx,
                        number=f"{ci + 1}.{li + 1}",
                        title=ls.title,
                        page_start=ls.page_start,
                        page_end=ls.page_end,
                        text=ls.text,
                        char_count=ls.char_count,
                    )
                )
                lesson_idx += 1
        self._commit()

    def run(self, lecture_id: uuid.UUID) -> None:
        lecture = self.db.get(Lecture, lecture_id)
        if lecture is None or lecture.status == "completed":
            return
        lecture.status = "processing"
        lecture.progress_step = "extracting"
        lecture.error_code = None
        lecture.error_message = None
        try:
            self._commit()
            self.ensure_outline(lecture)
            self._exists(Lecture, lecture.id)
            lecture.status = "completed"
            lecture.completed_at = utcnow()
            lecture.updated_at = utcnow()
            self._commit()
            logger.info("Lecture %s outline ready", lecture.id)
        except Gone:
            logger.info("Lecture %s was deleted during processing; stopping", lecture_id)
        except PdfError as exc:
            self._fail_lecture(lecture_id, exc.code)
        except SoftTimeLimitExceeded:
            self._fail_lecture(lecture_id, "TIMEOUT")

    def _fail_lecture(self, lecture_id: uuid.UUID, code: str) -> None:
        logger.warning("Lecture %s failed: %s", lecture_id, code)
        self.db.rollback()
        lecture = self.db.get(Lecture, lecture_id)
        if lecture is None:
            return
        lecture.status = "failed"
        lecture.error_code = code
        lecture.error_message = ERROR_MESSAGES.get(code, ERROR_MESSAGES["INTERNAL"])
        lecture.updated_at = utcnow()
        self.db.commit()

    # ---------- Học liệu theo bài ----------

    def _step(self, lesson: Lesson, step: str) -> None:
        self._exists(Lesson, lesson.id)
        lesson.progress_step = step
        lesson.updated_at = utcnow()
        self._commit()

    def ensure_lesson_summary(self, lesson: Lesson) -> LessonSummaryLLM:
        if lesson.summary is not None:
            return LessonSummaryLLM.model_validate(lesson.summary)
        summary = lesson_gen.summarize_lesson(self.llm, lesson)
        lesson.title = lesson_gen.better_title(lesson.title, summary.title)
        lesson.summary = summary.model_dump()
        self._commit()
        return summary

    def ensure_lesson_slides(
        self, lecture: Lecture, lesson: Lesson, summary: LessonSummaryLLM
    ) -> None:
        if lesson.slides is not None:
            return
        content: LessonSlidesLLM = lesson_gen.lesson_slides(self.llm, lesson, summary)
        chapter_title = self.db.scalar(select(Chapter.title).where(Chapter.id == lesson.chapter_id))
        deck = lesson_gen.build_deck(lesson, lesson.number, chapter_title or "", summary, content)
        key: str | None = lesson_pptx_key(lecture, lesson)
        try:
            self.storage.put(key, build_pptx(deck), PPTX_TYPE)  # type: ignore[arg-type]
        except Exception:
            # Xuất PPTX lỗi không chặn slide web (pptx_key = NULL)
            logger.exception("PPTX export failed for lesson %s", lesson.id)
            key = None
        lesson.slides = deck.model_dump(exclude_none=True)
        lesson.pptx_key = key
        self._commit()

    def ensure_lesson_quiz(self, lesson: Lesson, summary: LessonSummaryLLM) -> None:
        quiz = self.db.scalar(
            select(Quiz).where(Quiz.lesson_id == lesson.id, Quiz.is_default.is_(True))
        )
        if quiz and quiz.status == "completed":
            return
        if quiz is None:
            quiz = Quiz(
                lecture_id=lesson.lecture_id,
                lesson_id=lesson.id,
                num_questions=quiz_gen.default_question_count(lesson.page_start, lesson.page_end),
                is_default=True,
            )
            self.db.add(quiz)
        self.fill_quiz(quiz, [lesson], {lesson.id: summary})

    def run_lesson(self, lesson_id: uuid.UUID) -> None:
        lesson = self.db.get(Lesson, lesson_id)
        if lesson is None or lesson.status == "completed":
            return
        lecture = self.db.get(Lecture, lesson.lecture_id)
        if lecture is None:
            return
        lesson.status = "processing"
        lesson.error_code = None
        lesson.error_message = None
        try:
            self._commit()
            self._step(lesson, "summarizing")
            summary = self.ensure_lesson_summary(lesson)
            self._step(lesson, "slides")
            self.ensure_lesson_slides(lecture, lesson, summary)
            self._step(lesson, "quiz")
            self.ensure_lesson_quiz(lesson, summary)
            lesson.status = "completed"
            lesson.updated_at = utcnow()
            self._commit()
            logger.info("Lesson %s completed", lesson.id)
        except Gone:
            logger.info("Lesson %s was deleted during processing; stopping", lesson_id)
        except LLMError as exc:
            self._fail_lesson(lesson_id, exc.code)
        except SoftTimeLimitExceeded:
            self._fail_lesson(lesson_id, "TIMEOUT")

    def _fail_lesson(self, lesson_id: uuid.UUID, code: str) -> None:
        logger.warning("Lesson %s failed: %s", lesson_id, code)
        self.db.rollback()
        mark_lesson_failed(self.db, lesson_id, code)

    # ---------- Quiz ----------

    def fill_quiz(
        self,
        quiz: Quiz,
        lessons: list[Lesson],
        summaries: dict[uuid.UUID, LessonSummaryLLM] | None = None,
    ) -> None:
        """Sinh câu hỏi phân bổ theo độ dài các bài; lỗi LLM → quiz `failed` rồi ném tiếp."""
        quiz.status = "processing"
        quiz.error_message = None
        self.db.execute(delete(Question).where(Question.quiz_id == quiz.id))
        self._commit()
        lesson_ids = [lesson.id for lesson in lessons]
        avoid = list(
            self.db.scalars(
                select(Question.question)
                .join(Quiz, Quiz.id == Question.quiz_id)
                .where(Quiz.lesson_id.in_(lesson_ids), Quiz.id != quiz.id)
            )
        )
        summaries = summaries or {}
        for lesson in lessons:
            if lesson.id not in summaries and lesson.summary is not None:
                summaries[lesson.id] = LessonSummaryLLM.model_validate(lesson.summary)
        counts = quiz_gen.allocate(quiz.num_questions, [ls.char_count for ls in lessons])
        rng = random.Random()
        results: dict[int, list[quiz_gen.GeneratedQuestion]] = {}
        try:
            _parallel(
                [(ls, n) for ls, n in zip(lessons, counts, strict=True) if n > 0],
                lambda item: quiz_gen.questions_for_source(
                    self.llm,
                    item[0],
                    item[1],
                    avoid,
                    rng,
                    summaries[item[0].id].sections if item[0].id in summaries else None,
                ),
                lambda item, qs: results.__setitem__(item[0].idx, qs),
            )
        except LLMError as exc:
            quiz.status = "failed"
            quiz.error_message = ERROR_MESSAGES[exc.code]
            self._commit()
            raise
        position = 1
        for idx in sorted(results):
            for q in results[idx]:
                self.db.add(
                    Question(
                        quiz_id=quiz.id,
                        position=position,
                        question=q.question,
                        options=q.options,
                        answer_index=q.answer_index,
                        explanation=q.explanation,
                        page_ref=q.page_ref,
                        chapter_idx=q.source_idx,
                    )
                )
                position += 1
        quiz.status = "completed"
        self._commit()

    def run_quiz(self, quiz_id: uuid.UUID) -> None:
        quiz = self.db.get(Quiz, quiz_id)
        if quiz is None or quiz.status == "completed":
            return
        ids = [quiz.lesson_id] if quiz.lesson_id else [uuid.UUID(i) for i in quiz.lesson_ids or []]
        lessons = list(
            self.db.scalars(select(Lesson).where(Lesson.id.in_(ids)).order_by(Lesson.idx))
        )
        if not lessons:
            mark_quiz_failed(self.db, quiz_id)
            return
        try:
            self.fill_quiz(quiz, lessons)
        except Gone:
            logger.info("Quiz %s was deleted during processing; stopping", quiz_id)
        except LLMError:
            logger.warning("Quiz %s failed", quiz_id)
        except SoftTimeLimitExceeded:
            self.db.rollback()
            mark_quiz_failed(self.db, quiz_id, "TIMEOUT")


def mark_failed(db: Session, lecture_id: uuid.UUID, code: str = "INTERNAL") -> None:
    lecture = db.get(Lecture, lecture_id)
    if lecture is not None and lecture.status != "completed":
        lecture.status = "failed"
        lecture.error_code = code
        lecture.error_message = ERROR_MESSAGES[code]
        lecture.updated_at = utcnow()
        db.commit()


def mark_lesson_failed(db: Session, lesson_id: uuid.UUID, code: str = "INTERNAL") -> None:
    lesson = db.get(Lesson, lesson_id)
    if lesson is not None and lesson.status != "completed":
        lesson.status = "failed"
        lesson.error_code = code
        lesson.error_message = ERROR_MESSAGES.get(code, ERROR_MESSAGES["INTERNAL"])
        lesson.updated_at = utcnow()
        db.commit()


def mark_quiz_failed(db: Session, quiz_id: uuid.UUID, code: str = "INTERNAL") -> None:
    quiz = db.get(Quiz, quiz_id)
    if quiz is not None and quiz.status != "completed":
        quiz.status = "failed"
        quiz.error_message = ERROR_MESSAGES[code]
        db.commit()
