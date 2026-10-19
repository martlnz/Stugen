"""Pipeline (ADR-0017): tách mục lục chương → bài, tạo học liệu theo bài với FakeLLMClient."""

import uuid
from pathlib import Path

from sqlalchemy import select

from app.ai.generators.lesson import _clamp_sections, summary_markdown
from app.ai.generators.quiz import allocate, default_question_count
from app.ai.llm.fake import FakeLLMClient
from app.ai.pdf import extract_chapters
from app.db.models import Chapter, Lecture, Lesson, Question, Quiz, User
from app.db.session import sync_session
from app.schemas.llm import LessonSection, LessonSlidesLLM, LessonSummaryLLM, clip
from app.worker.pipeline import LecturePipeline
from tests.fakes import MemoryStorage

FIXTURES = Path(__file__).parent / "fixtures"


def make_lecture(
    storage: MemoryStorage, pdf: str = "sample.pdf", user_id: uuid.UUID | None = None
) -> uuid.UUID:
    with sync_session() as db:
        if user_id is None:
            user = User(google_id=f"g-{uuid.uuid4()}", email="p@example.com", name="p")
            db.add(user)
            db.flush()
            user_id = user.id
        lecture = Lecture(
            user_id=user_id,
            title="giao-trinh-csdl-final",
            original_filename=pdf,
            pdf_key=f"users/{user_id}/lectures/{uuid.uuid4()}/source.pdf",
            file_size=1,
            page_count=14,
        )
        db.add(lecture)
        db.commit()
        storage.put(lecture.pdf_key, (FIXTURES / pdf).read_bytes(), "application/pdf")
        return lecture.id


def run(lecture_id: uuid.UUID, llm: FakeLLMClient, storage: MemoryStorage) -> Lecture:
    with sync_session() as db:
        LecturePipeline(db, llm, storage).run(lecture_id)
    with sync_session() as db:
        lecture = db.get(Lecture, lecture_id)
        assert lecture is not None
        return lecture


def lessons_of(lecture_id: uuid.UUID) -> list[Lesson]:
    with sync_session() as db:
        return list(
            db.scalars(select(Lesson).where(Lesson.lecture_id == lecture_id).order_by(Lesson.idx))
        )


def run_lesson(lesson_id: uuid.UUID, llm: FakeLLMClient, storage: MemoryStorage) -> Lesson:
    with sync_session() as db:
        LecturePipeline(db, llm, storage).run_lesson(lesson_id)
    with sync_session() as db:
        lesson = db.get(Lesson, lesson_id)
        assert lesson is not None
        return lesson


def test_extract_chapters_from_bookmarks() -> None:
    chapters = extract_chapters((FIXTURES / "sample.pdf").read_bytes())
    assert [c.title for c in chapters] == [
        "Chương 1. Tổng quan về cơ sở dữ liệu",
        "Chương 2. Mô hình quan hệ",
        "Chương 3. Ngôn ngữ SQL",
    ]
    assert [(c.page_start, c.page_end) for c in chapters] == [(1, 4), (5, 6), (7, 14)]
    first = chapters[0].text
    assert first.startswith("[[trang 1]]")
    # Header lặp và footer "Trang N" đã bị loại bỏ
    assert "Giáo trình Cơ sở dữ liệu" not in first
    assert "Trang 1" not in first


def test_outline_splits_chapters_into_lessons(memory_storage: MemoryStorage) -> None:
    lid = make_lecture(memory_storage)
    llm = FakeLLMClient()
    lecture = run(lid, llm, memory_storage)
    assert lecture.status == "completed"
    assert lecture.progress_step == "extracting"
    lessons = lessons_of(lid)
    assert [(ls.number, ls.title, ls.page_start, ls.page_end) for ls in lessons] == [
        # Bookmark cấp 2
        ("1.1", "1.1 Khái niệm cơ sở dữ liệu", 1, 2),
        ("1.2", "1.2 Hệ quản trị cơ sở dữ liệu", 3, 4),
        # Tiêu đề phụ theo cỡ chữ; phần mở đầu lấy tên chương bỏ "Chương N."
        ("2.1", "Mô hình quan hệ", 5, 5),
        ("2.2", "Khoá chính và khoá ngoại", 6, 6),
        # Chương dài không tiêu đề phụ → LLM tách bài
        ("3.1", "Bài mở đầu", 7, 10),
        ("3.2", "Bài tiếp theo", 11, 14),
    ]
    assert all(ls.status == "pending" for ls in lessons)
    assert [p for p, _ in llm.calls] == ["outline"]
    # Chỉ tách mục lục: chưa sinh quiz
    with sync_session() as db:
        assert db.scalar(select(Quiz.id).where(Quiz.lecture_id == lid)) is None


def test_outline_is_idempotent(memory_storage: MemoryStorage) -> None:
    lid = make_lecture(memory_storage)
    run(lid, FakeLLMClient(), memory_storage)
    with sync_session() as db:
        db.get(Lecture, lid).status = "queued"  # type: ignore[union-attr]
        db.commit()
    llm = FakeLLMClient()
    run(lid, llm, memory_storage)
    assert llm.calls == []
    assert len(lessons_of(lid)) == 6


def test_outline_llm_failure_falls_back_to_page_chunks(memory_storage: MemoryStorage) -> None:
    lid = make_lecture(memory_storage)
    llm = FakeLLMClient({"OutlineLLM": ["xấu", "xấu"]})
    assert run(lid, llm, memory_storage).status == "completed"
    chapter3 = [ls for ls in lessons_of(lid) if ls.number.startswith("3.")]
    assert [ls.title for ls in chapter3] == ["Ngôn ngữ SQL (phần 1)", "Ngôn ngữ SQL (phần 2)"]


def test_scan_pdf_fails_with_no_text(memory_storage: MemoryStorage) -> None:
    lid = make_lecture(memory_storage, "scan.pdf")
    lecture = run(lid, FakeLLMClient(), memory_storage)
    assert lecture.status == "failed"
    assert lecture.progress_step == "extracting"
    assert lecture.error_code == "PDF_NO_TEXT"
    assert lecture.error_message == "Giáo trình có vẻ là bản scan, hiện chưa được hỗ trợ."


def test_generate_lesson(memory_storage: MemoryStorage) -> None:
    lid = make_lecture(memory_storage)
    run(lid, FakeLLMClient(), memory_storage)
    lesson = lessons_of(lid)[0]
    llm = FakeLLMClient()
    done = run_lesson(lesson.id, llm, memory_storage)
    assert done.status == "completed"
    assert done.progress_step == "quiz"
    assert [p for p, _ in llm.calls] == ["lesson_summary", "slides", "quiz"]

    summary = LessonSummaryLLM.model_validate(done.summary)
    assert all(1 <= s.page_start <= s.page_end <= 2 for s in summary.sections)
    md = summary_markdown(summary)
    # Không có tên file/tên giáo trình
    assert "giao-trinh-csdl-final" not in md
    assert not md.startswith("# ")
    assert "*(tr. 1)*" in md

    deck = done.slides
    assert deck is not None
    layouts = [s["layout"] for s in deck["slides"]]
    assert layouts[:2] == ["title", "agenda"] and layouts[-1] == "summary"
    # Tên bài từ bookmark đủ rõ nên được giữ nguyên
    assert deck["title"] == done.title == "1.1 Khái niệm cơ sở dữ liệu"
    assert all("tr." in b for b in deck["slides"][1]["bullets"])
    content = [s for s in deck["slides"] if s["layout"] == "bullets"]
    assert content and all(s.get("example") and s.get("explanation") for s in content)
    assert done.pptx_key in memory_storage.objects

    with sync_session() as db:
        quiz = db.scalar(select(Quiz).where(Quiz.lesson_id == lesson.id))
        assert quiz is not None and quiz.is_default and quiz.status == "completed"
        questions = list(db.scalars(select(Question).where(Question.quiz_id == quiz.id)))
        assert len(questions) == default_question_count(1, 2) == 5
        for q in questions:
            assert 1 <= q.page_ref <= 2
            assert q.options[q.answer_index] == "Đáp án A"


def test_lesson_failure_and_retry_skip_done_steps(memory_storage: MemoryStorage) -> None:
    lid = make_lecture(memory_storage)
    run(lid, FakeLLMClient(), memory_storage)
    lesson = lessons_of(lid)[0]
    bad = "không phải json"
    failed = run_lesson(lesson.id, FakeLLMClient({"LessonSlidesLLM": [bad, bad]}), memory_storage)
    assert failed.status == "failed"
    assert failed.progress_step == "slides"
    assert failed.error_code == "LLM_INVALID_OUTPUT"
    assert failed.summary is not None

    with sync_session() as db:
        db.get(Lesson, lesson.id).status = "queued"  # type: ignore[union-attr]
        db.commit()
    llm2 = FakeLLMClient()
    assert run_lesson(lesson.id, llm2, memory_storage).status == "completed"
    # Tóm tắt đã có → không gọi lại (ADR-0015)
    assert [p for p, _ in llm2.calls] == ["slides", "quiz"]


def test_quiz_page_ref_out_of_range_fails_lesson(memory_storage: MemoryStorage) -> None:
    lid = make_lecture(memory_storage)
    run(lid, FakeLLMClient(), memory_storage)
    lesson = lessons_of(lid)[0]
    question = {
        "question": "?",
        "options": ["a", "b", "c", "d"],
        "answer_index": 1,
        "explanation": "x",
        "page_ref": 99,
    }
    bad = {"questions": [question] * 5}
    done = run_lesson(lesson.id, FakeLLMClient({"QuestionSetLLM": [bad, bad]}), memory_storage)
    assert done.status == "failed"
    assert done.progress_step == "quiz"
    with sync_session() as db:
        quiz = db.scalar(select(Quiz).where(Quiz.lesson_id == lesson.id))
        assert quiz is not None and quiz.status == "failed"


def test_deleted_lecture_stops_lesson_quietly(memory_storage: MemoryStorage) -> None:
    lid = make_lecture(memory_storage)
    run(lid, FakeLLMClient(), memory_storage)
    lesson = lessons_of(lid)[0]
    llm = FakeLLMClient()

    def delete_during_summary(purpose: str, _: str) -> None:
        if purpose == "lesson_summary":
            with sync_session() as db:
                db.delete(db.get(Lecture, lid))
                db.commit()

    llm.on_call = delete_during_summary
    with sync_session() as db:
        LecturePipeline(db, llm, memory_storage).run_lesson(lesson.id)
    with sync_session() as db:
        assert db.get(Lecture, lid) is None
        assert db.scalar(select(Chapter.id).where(Chapter.lecture_id == lid)) is None
    assert "slides" not in [p for p, _ in llm.calls]


def test_allocate_and_default_count() -> None:
    assert allocate(10, [100, 100, 100]) in ([4, 3, 3], [3, 4, 3], [3, 3, 4])
    assert sum(allocate(10, [5000, 1000, 1000, 1000])) == 10
    assert allocate(2, [10, 30, 20]) == [0, 1, 1]
    assert default_question_count(1, 1) == 5
    assert default_question_count(1, 6) == 9
    assert default_question_count(1, 20) == 15


def test_long_slide_fields_are_clipped_not_rejected() -> None:
    long = "Consistency (tính nhất quán): giao dịch đưa cơ sở dữ liệu từ trạng thái hợp lệ " * 3
    slide = {
        "title": "T" * 100,
        "bullets": [long] * 8,
        "explanation": long * 3,
        "example": long * 5,
        "page_refs": [1],
    }
    out = LessonSlidesLLM.model_validate({"slides": [slide] * 14, "takeaways": [long] * 9})
    assert len(out.slides) == 12
    first = out.slides[0]
    assert len(first.title) <= 80
    assert len(first.bullets) == 5
    assert all(len(b) <= 120 and b.endswith("…") for b in first.bullets)
    assert first.explanation and len(first.explanation) <= 300
    assert first.example and len(first.example) <= 400
    assert len(out.takeaways) == 6
    assert clip("ngắn", 120) == "ngắn"


def test_vague_lesson_titles_are_replaced() -> None:
    from app.ai.generators.lesson import better_title

    suggested = "Mục đích nghiên cứu của trí tuệ nhân tạo"
    assert better_title("Mục đích", suggested) == suggested
    assert better_title("Phát triển; Phân loại máy tính", suggested) == suggested
    assert better_title("Ngôn ngữ SQL (phần 2)", suggested) == suggested
    assert better_title("Đặc điểm chung của ngôn ngữ lập trình", suggested).startswith("Đặc")
    assert better_title("Mục đích", None) == "Mục đích"


def test_section_pages_are_clamped() -> None:
    sections = [
        LessonSection(title="B", page_start=9, page_end=12, key_points=["x"]),
        LessonSection(title="A", page_start=0, page_end=3, key_points=["x"]),
    ]
    fixed = _clamp_sections(sections, 2, 5)
    assert [(s.title, s.page_start, s.page_end) for s in fixed] == [("A", 2, 3), ("B", 5, 5)]
