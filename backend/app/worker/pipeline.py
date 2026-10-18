"""Điều phối xử lý bài giảng (ADR-0008, ADR-0015). Mọi bước idempotent: có kết quả thì bỏ qua."""

import logging
import random
import uuid
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.generators import quiz as quiz_gen
from app.ai.generators import slides as slides_gen
from app.ai.generators import summary as summary_gen
from app.ai.generators.pptx import build_pptx
from app.ai.llm import LLMClient, LLMError
from app.ai.pdf import PdfError, extract_chapters
from app.core.config import settings
from app.db.models import Chapter, Lecture, Question, Quiz, SlideDeck, Summary, utcnow
from app.schemas.llm import OverviewLLM
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
DEFAULT_QUIZ_SIZE = 10


class LectureGone(Exception):
    """Bài giảng đã bị xoá trong lúc xử lý → dừng ở bước kế tiếp."""


def _parallel[T, R](
    items: Iterable[T], work: Callable[[T], R], on_result: Callable[[T, R], None]
) -> None:
    """Gọi LLM song song (≤ LLM_MAX_CONCURRENCY); ghi kết quả ở luồng chính ngay khi xong.

    Lỗi ở một phần không huỷ các phần đang chạy: phần đã xong vẫn được lưu để lần chạy
    lại không gọi lại LLM; lỗi đầu tiên được ném ra sau cùng.
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


class LecturePipeline:
    def __init__(self, db: Session, llm: LLMClient, storage: Storage) -> None:
        self.db = db
        self.llm = llm
        self.storage = storage

    # ---------- tiện ích ----------
    def _commit(self) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            # FK tới lecture đã bị xoá
            self.db.rollback()
            raise LectureGone() from exc

    def _step(self, lecture: Lecture, step: str) -> None:
        exists = self.db.scalar(select(Lecture.id).where(Lecture.id == lecture.id))
        if exists is None:
            raise LectureGone()
        lecture.progress_step = step
        lecture.updated_at = utcnow()
        self._commit()

    def _chapters(self, lecture: Lecture) -> list[Chapter]:
        return list(
            self.db.scalars(
                select(Chapter).where(Chapter.lecture_id == lecture.id).order_by(Chapter.idx)
            )
        )

    # ---------- các bước ----------
    def ensure_chapters(self, lecture: Lecture) -> list[Chapter]:
        chapters = self._chapters(lecture)
        if chapters:
            return chapters
        data = self.storage.get_bytes(lecture.pdf_key)
        for idx, ch in enumerate(extract_chapters(data)):
            self.db.add(
                Chapter(
                    lecture_id=lecture.id,
                    idx=idx,
                    title=ch.title,
                    page_start=ch.page_start,
                    page_end=ch.page_end,
                    text=ch.text,
                    char_count=ch.char_count,
                )
            )
        self._commit()
        return self._chapters(lecture)

    def ensure_summary(self, lecture: Lecture, chapters: list[Chapter]) -> Summary:
        existing = self.db.scalar(select(Summary).where(Summary.lecture_id == lecture.id))
        if existing:
            return existing

        def save(ch: Chapter, result: object) -> None:
            ch.summary = result.model_dump()  # type: ignore[attr-defined]
            self._commit()

        _parallel(
            [ch for ch in chapters if ch.summary is None],
            lambda ch: summary_gen.summarize_chapter(self.llm, lecture.title, ch),
            save,
        )
        summaries = summary_gen.chapter_summaries(chapters)
        overview = summary_gen.make_overview(self.llm, lecture.title, summaries)
        summary = Summary(
            lecture_id=lecture.id,
            overview=overview.overview,
            learning_objectives=overview.learning_objectives,
            chapters=[s.model_dump() for s in summaries],
            content_md=summary_gen.build_markdown(lecture.title, overview, summaries),
        )
        self.db.add(summary)
        self._commit()
        return summary

    def ensure_slides(self, lecture: Lecture, chapters: list[Chapter], summary: Summary) -> None:
        if self.db.scalar(select(SlideDeck.id).where(SlideDeck.lecture_id == lecture.id)):
            return

        def save(ch: Chapter, slides: list) -> None:  # type: ignore[type-arg]
            ch.slides = [s.model_dump(exclude_none=True) for s in slides]
            self._commit()

        _parallel(
            [ch for ch in chapters if ch.slides is None],
            lambda ch: slides_gen.chapter_slides(self.llm, lecture.title, ch),
            save,
        )
        objectives = OverviewLLM.model_validate(
            {"overview": summary.overview, "learning_objectives": summary.learning_objectives}
        ).learning_objectives
        deck = slides_gen.build_deck(lecture.title, chapters, objectives)
        pptx_key: str | None = f"{lecture_prefix(lecture.user_id, lecture.id)}slides.pptx"
        try:
            content = build_pptx(deck)
            self.storage.put(
                pptx_key,
                content,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        except Exception:
            # Xuất PPTX lỗi không chặn slide web (pptx_key = NULL)
            logger.exception("PPTX export failed for lecture %s", lecture.id)
            pptx_key = None
        self.db.add(
            SlideDeck(
                lecture_id=lecture.id,
                deck=deck.model_dump(exclude_none=True),
                pptx_key=pptx_key,
            )
        )
        self._commit()

    def ensure_default_quiz(self, lecture: Lecture, chapters: list[Chapter]) -> None:
        quiz = self.db.scalar(
            select(Quiz).where(Quiz.lecture_id == lecture.id, Quiz.is_default.is_(True))
        )
        if quiz and quiz.status == "completed":
            return
        if quiz is None:
            quiz = Quiz(lecture_id=lecture.id, num_questions=DEFAULT_QUIZ_SIZE, is_default=True)
            self.db.add(quiz)
        self.fill_quiz(quiz, lecture, chapters)

    def fill_quiz(self, quiz: Quiz, lecture: Lecture, chapters: list[Chapter]) -> None:
        """Sinh câu hỏi cho quiz; lỗi LLM → quiz `failed` rồi ném lỗi tiếp."""
        quiz.status = "processing"
        quiz.error_message = None
        self.db.execute(delete(Question).where(Question.quiz_id == quiz.id))
        self._commit()
        avoid = list(
            self.db.scalars(
                select(Question.question)
                .join(Quiz, Quiz.id == Question.quiz_id)
                .where(Quiz.lecture_id == lecture.id, Quiz.id != quiz.id)
            )
        )
        counts = quiz_gen.allocate(quiz.num_questions, [ch.char_count for ch in chapters])
        rng = random.Random()
        results: dict[int, list[quiz_gen.GeneratedQuestion]] = {}
        try:
            _parallel(
                [(ch, n) for ch, n in zip(chapters, counts, strict=True) if n > 0],
                lambda item: quiz_gen.questions_for_chapter(
                    self.llm, lecture.title, item[0], item[1], avoid, rng
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
                        chapter_idx=q.chapter_idx,
                    )
                )
                position += 1
        quiz.status = "completed"
        self._commit()

    # ---------- điều phối ----------
    def run(self, lecture_id: uuid.UUID) -> None:
        lecture = self.db.get(Lecture, lecture_id)
        if lecture is None or lecture.status == "completed":
            return
        lecture.status = "processing"
        lecture.error_code = None
        lecture.error_message = None
        self._commit()
        try:
            self._step(lecture, "extracting")
            chapters = self.ensure_chapters(lecture)
            self._step(lecture, "summarizing")
            summary = self.ensure_summary(lecture, chapters)
            self._step(lecture, "slides")
            self.ensure_slides(lecture, chapters, summary)
            self._step(lecture, "quiz")
            self.ensure_default_quiz(lecture, chapters)
            lecture.status = "completed"
            lecture.completed_at = utcnow()
            lecture.updated_at = utcnow()
            self._commit()
            logger.info("Lecture %s completed", lecture.id)
        except LectureGone:
            logger.info("Lecture %s was deleted during processing; stopping", lecture_id)
        except PdfError as exc:
            self._fail(lecture, exc.code)
        except LLMError as exc:
            self._fail(lecture, exc.code)
        except SoftTimeLimitExceeded:
            self._fail(lecture, "TIMEOUT")

    def _fail(self, lecture: Lecture, code: str) -> None:
        logger.warning("Lecture %s failed at %s: %s", lecture.id, lecture.progress_step, code)
        self.db.rollback()
        lecture = self.db.get(Lecture, lecture.id)  # type: ignore[assignment]
        if lecture is None:
            return
        lecture.status = "failed"
        lecture.error_code = code
        lecture.error_message = ERROR_MESSAGES.get(code, ERROR_MESSAGES["INTERNAL"])
        lecture.updated_at = utcnow()
        self.db.commit()

    def run_quiz(self, quiz_id: uuid.UUID) -> None:
        quiz = self.db.get(Quiz, quiz_id)
        if quiz is None or quiz.status == "completed":
            return
        lecture = self.db.get(Lecture, quiz.lecture_id)
        if lecture is None:
            return
        chapters = self._chapters(lecture)
        try:
            self.fill_quiz(quiz, lecture, chapters)
        except LectureGone:
            logger.info("Quiz %s was deleted during processing; stopping", quiz_id)
        except LLMError:
            logger.warning("Quiz %s failed", quiz_id)
        except SoftTimeLimitExceeded:
            self.db.rollback()
            quiz.status = "failed"
            quiz.error_message = ERROR_MESSAGES["TIMEOUT"]
            self.db.commit()


def mark_failed(db: Session, lecture_id: uuid.UUID, code: str = "INTERNAL") -> None:
    lecture = db.get(Lecture, lecture_id)
    if lecture is not None and lecture.status != "completed":
        lecture.status = "failed"
        lecture.error_code = code
        lecture.error_message = ERROR_MESSAGES[code]
        lecture.updated_at = utcnow()
        db.commit()


def mark_quiz_failed(db: Session, quiz_id: uuid.UUID) -> None:
    quiz = db.get(Quiz, quiz_id)
    if quiz is not None and quiz.status != "completed":
        quiz.status = "failed"
        quiz.error_message = ERROR_MESSAGES["INTERNAL"]
        db.commit()
