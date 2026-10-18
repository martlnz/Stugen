"""Pipeline xử lý bài giảng với FakeLLMClient và storage trong bộ nhớ."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.ai.generators.quiz import allocate
from app.ai.llm.fake import FakeLLMClient
from app.ai.pdf import extract_chapters
from app.db.models import Chapter, Lecture, Question, Quiz, SlideDeck, Summary, User
from app.db.session import sync_session
from app.schemas.llm import ChapterSlidesLLM, clip
from app.worker.pipeline import LecturePipeline
from tests.fakes import MemoryStorage

FIXTURES = Path(__file__).parent / "fixtures"


def make_lecture(storage: MemoryStorage, pdf: str = "sample.pdf") -> uuid.UUID:
    with sync_session() as db:
        user = User(google_id=f"g-{uuid.uuid4()}", email="p@example.com", name="p")
        db.add(user)
        db.flush()
        lecture = Lecture(
            user_id=user.id,
            title="Nhập môn CSDL",
            original_filename=pdf,
            pdf_key=f"users/{user.id}/lectures/x/source.pdf",
            file_size=1,
            page_count=6,
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


def test_extract_chapters_from_bookmarks() -> None:
    chapters = extract_chapters((FIXTURES / "sample.pdf").read_bytes())
    assert [c.title for c in chapters] == [
        "Chương 1. Tổng quan về cơ sở dữ liệu",
        "Chương 2. Mô hình quan hệ",
        "Chương 3. Ngôn ngữ SQL",
    ]
    assert [(c.page_start, c.page_end) for c in chapters] == [(1, 2), (3, 4), (5, 6)]
    first = chapters[0].text
    assert first.startswith("[[trang 1]]")
    assert "[[trang 2]]" in first
    # Header lặp và footer "Trang N" đã bị loại bỏ
    assert "Giáo trình Cơ sở dữ liệu" not in first
    assert "Trang 1" not in first


def test_allocate_questions() -> None:
    assert allocate(10, [100, 100, 100]) in ([4, 3, 3], [3, 4, 3], [3, 3, 4])
    assert sum(allocate(10, [5000, 1000, 1000, 1000])) == 10
    assert allocate(10, [5000, 1000, 1000, 1000])[0] > 3
    assert allocate(2, [10, 30, 20]) == [0, 1, 1]


def test_full_pipeline(memory_storage: MemoryStorage) -> None:
    lid = make_lecture(memory_storage)
    llm = FakeLLMClient()
    lecture = run(lid, llm, memory_storage)
    assert lecture.status == "completed"
    assert lecture.progress_step == "quiz"
    with sync_session() as db:
        chapters = list(db.scalars(select(Chapter).where(Chapter.lecture_id == lid)))
        assert len(chapters) == 3
        assert all(c.summary and c.slides for c in chapters)
        summary = db.scalar(select(Summary).where(Summary.lecture_id == lid))
        assert summary is not None
        assert summary.chapters[0]["page_start"] == 1
        assert "## Chương 1. Tổng quan về cơ sở dữ liệu" in summary.content_md
        deck = db.scalar(select(SlideDeck).where(SlideDeck.lecture_id == lid))
        assert deck is not None and deck.pptx_key in memory_storage.objects
        layouts = [s["layout"] for s in deck.deck["slides"]]
        assert layouts[:2] == ["title", "agenda"]
        assert layouts[-1] == "summary"
        assert layouts.count("section") == 3
        quiz = db.scalar(select(Quiz).where(Quiz.lecture_id == lid))
        assert quiz is not None and quiz.is_default and quiz.status == "completed"
        questions = list(db.scalars(select(Question).where(Question.quiz_id == quiz.id)))
        assert len(questions) == 10
        assert sorted(q.position for q in questions) == list(range(1, 11))
        by_idx = {c.idx: c for c in chapters}
        for q in questions:
            ch = by_idx[q.chapter_idx]
            assert ch.page_start <= q.page_ref <= ch.page_end
            # Fake luôn đặt đáp án đúng ở "Đáp án A"; sau xáo trộn answer_index vẫn trỏ đúng
            assert q.options[q.answer_index] == "Đáp án A"
    # 3 tóm tắt + 1 tổng quan + 3 slide + 3 quiz
    purposes = [p for p, _ in llm.calls]
    assert purposes.count("chapter_summary") == 3
    assert purposes.count("overview") == 1
    assert purposes.count("slides") == 3
    assert purposes.count("quiz") == 3


def test_scan_pdf_fails_with_no_text(memory_storage: MemoryStorage) -> None:
    lid = make_lecture(memory_storage, "scan.pdf")
    lecture = run(lid, FakeLLMClient(), memory_storage)
    assert lecture.status == "failed"
    assert lecture.progress_step == "extracting"
    assert lecture.error_code == "PDF_NO_TEXT"
    assert lecture.error_message == "Giáo trình có vẻ là bản scan, hiện chưa được hỗ trợ."


def test_invalid_output_is_repaired_once(memory_storage: MemoryStorage) -> None:
    lid = make_lecture(memory_storage)
    # Lần đầu sai schema, lần sửa đúng → vẫn hoàn tất
    llm = FakeLLMClient({"OverviewLLM": ['{"overview": ""}']})
    assert run(lid, llm, memory_storage).status == "completed"


def test_invalid_output_twice_fails_and_retry_skips_done_chapters(
    memory_storage: MemoryStorage,
) -> None:
    lid = make_lecture(memory_storage)
    bad = "không phải json"
    llm = FakeLLMClient({"OverviewLLM": [bad, bad]})
    lecture = run(lid, llm, memory_storage)
    assert lecture.status == "failed"
    assert lecture.error_code == "LLM_INVALID_OUTPUT"
    assert lecture.progress_step == "summarizing"
    assert [p for p, _ in llm.calls].count("chapter_summary") == 3

    # Chạy lại: không gọi lại LLM cho các chương đã tóm tắt (ADR-0015)
    llm2 = FakeLLMClient()
    assert run(lid, llm2, memory_storage).status == "completed"
    assert [p for p, _ in llm2.calls].count("chapter_summary") == 0


def test_quiz_page_ref_out_of_range_is_invalid(memory_storage: MemoryStorage) -> None:
    lid = make_lecture(memory_storage)
    question = {
        "question": "?",
        "options": ["a", "b", "c", "d"],
        "answer_index": 1,
        "explanation": "x",
        "page_ref": 99,
    }
    bad = {"questions": [question] * 4}
    llm = FakeLLMClient({"QuestionSetLLM": [bad, bad]})
    lecture = run(lid, llm, memory_storage)
    assert lecture.status == "failed"
    assert lecture.progress_step == "quiz"
    assert lecture.error_code == "LLM_INVALID_OUTPUT"
    with sync_session() as db:
        quiz = db.scalar(select(Quiz).where(Quiz.lecture_id == lid))
        assert quiz is not None and quiz.status == "failed"


def test_deleted_lecture_stops_quietly(memory_storage: MemoryStorage) -> None:
    lid = make_lecture(memory_storage)
    llm = FakeLLMClient()

    def delete_during_summary(purpose: str, _: str) -> None:
        if purpose == "overview":
            with sync_session() as db:
                db.delete(db.get(Lecture, lid))
                db.commit()

    llm.on_call = delete_during_summary
    with sync_session() as db:
        LecturePipeline(db, llm, memory_storage).run(lid)
    with sync_session() as db:
        assert db.get(Lecture, lid) is None
    assert "slides" not in [p for p, _ in llm.calls]


@pytest.mark.parametrize("status", ["completed"])
def test_completed_lecture_is_skipped(memory_storage: MemoryStorage, status: str) -> None:
    lid = make_lecture(memory_storage)
    with sync_session() as db:
        db.get(Lecture, lid).status = status  # type: ignore[union-attr]
        db.commit()
    llm = FakeLLMClient()
    run(lid, llm, memory_storage)
    assert llm.calls == []


def test_long_bullets_are_clipped_not_rejected() -> None:
    long = "Consistency (tính nhất quán): giao dịch đưa cơ sở dữ liệu từ trạng thái hợp lệ " * 3
    out = ChapterSlidesLLM.model_validate(
        {"slides": [{"title": "T" * 100, "bullets": [long] * 8, "page_refs": [1]}] * 4}
    )
    assert len(out.slides) == 3
    slide = out.slides[0]
    assert len(slide.title) <= 80
    assert len(slide.bullets) == 6
    assert all(len(b) <= 120 and b.endswith("…") for b in slide.bullets)
    assert clip("ngắn", 120) == "ngắn"
