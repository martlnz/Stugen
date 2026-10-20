"""API bài học + quiz (ADR-0017, 0018): sở hữu, chọn bài, ẩn đáp án, chấm điểm, sửa quiz."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.ai.llm.fake import FakeLLMClient
from app.db.models import Lecture, Question, Quiz, User
from app.db.session import sync_session
from app.services import lectures as lecture_service
from app.services import lessons as lesson_service
from app.services import quizzes as quiz_service
from app.worker.pipeline import LecturePipeline
from tests.fakes import MemoryStorage
from tests.test_pipeline import lessons_of, make_lecture


@pytest.fixture(autouse=True)
def jobs(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[object]]:
    calls: dict[str, list[object]] = {"lesson": [], "quiz": [], "lecture": []}
    monkeypatch.setattr(lesson_service, "enqueue_generate_lesson", calls["lesson"].append)
    monkeypatch.setattr(quiz_service, "enqueue_generate_quiz", calls["quiz"].append)
    monkeypatch.setattr(lecture_service, "enqueue_process_lecture", calls["lecture"].append)
    return calls


@pytest.fixture
def lecture_id(user_a: tuple[User, str], memory_storage: MemoryStorage) -> uuid.UUID:
    """Bài giảng của alice đã tách mục lục; bài 1.1 đã tạo học liệu."""
    lid = make_lecture(memory_storage, user_id=user_a[0].id)
    with sync_session() as db:
        pipeline = LecturePipeline(db, FakeLLMClient(), memory_storage)
        pipeline.run(lid)
        pipeline.run_lesson(lessons_of(lid)[0].id)
    return lid


async def outline(client: AsyncClient, lid: uuid.UUID) -> list[dict]:
    res = await client.get(f"/api/lectures/{lid}/outline")
    assert res.status_code == 200, res.text
    return [lesson for ch in res.json()["chapters"] for lesson in ch["lessons"]]


async def lesson_quiz(client: AsyncClient, lesson_id: str) -> dict:
    res = await client.get(f"/api/lessons/{lesson_id}/quizzes")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    return items[0]


def answer_key(quiz_id: str) -> dict[str, int]:
    with sync_session() as db:
        rows = db.scalars(select(Question).where(Question.quiz_id == uuid.UUID(quiz_id)))
        return {str(q.id): q.answer_index for q in rows}


async def test_lecture_reports_lesson_counts(client_a: AsyncClient, lecture_id: uuid.UUID) -> None:
    body = (await client_a.get(f"/api/lectures/{lecture_id}")).json()
    assert body["status"] == "completed"
    assert body["lessons"] == {"total": 6, "completed": 1, "processing": 0, "failed": 0}
    assert body["needs_regenerate"] is False


async def test_outline(client_a: AsyncClient, lecture_id: uuid.UUID) -> None:
    res = await client_a.get(f"/api/lectures/{lecture_id}/outline")
    chapters = res.json()["chapters"]
    assert [c["title"] for c in chapters][0] == "Chương 1. Tổng quan về cơ sở dữ liệu"
    first = chapters[0]["lessons"][0]
    assert first["number"] == "1.1"
    assert first["status"] == "completed"
    assert first["available"] == {"summary": True, "slides": True, "pptx": True, "quiz": True}
    assert first["sections"] and {"title", "page_start", "page_end"} <= set(first["sections"][0])
    second = chapters[0]["lessons"][1]
    assert second["status"] == "pending" and second["sections"] == []


async def test_generate_selected_lessons(
    client_a: AsyncClient, lecture_id: uuid.UUID, jobs: dict[str, list[object]]
) -> None:
    lessons = await outline(client_a, lecture_id)
    ids = [lessons[0]["id"], lessons[1]["id"], lessons[2]["id"]]
    res = await client_a.post(
        f"/api/lectures/{lecture_id}/lessons/generate", json={"lesson_ids": ids}
    )
    assert res.status_code == 202
    statuses = {ls["id"]: ls["status"] for ch in res.json()["chapters"] for ls in ch["lessons"]}
    # Bài đã xong bỏ qua; chỉ 2 bài mới được xếp hàng
    assert statuses[ids[0]] == "completed"
    assert statuses[ids[1]] == statuses[ids[2]] == "queued"
    assert [str(x) for x in jobs["lesson"]] == ids[1:]
    # Gửi lại không xếp hàng trùng
    await client_a.post(f"/api/lectures/{lecture_id}/lessons/generate", json={"lesson_ids": ids})
    assert len(jobs["lesson"]) == 2


async def test_generate_rejects_foreign_lesson(
    client_a: AsyncClient, lecture_id: uuid.UUID
) -> None:
    res = await client_a.post(
        f"/api/lectures/{lecture_id}/lessons/generate",
        json={"lesson_ids": [str(uuid.uuid4())]},
    )
    assert res.status_code == 422
    res = await client_a.post(
        f"/api/lectures/{lecture_id}/lessons/generate", json={"lesson_ids": []}
    )
    assert res.status_code == 422


async def test_lesson_content(client_a: AsyncClient, lecture_id: uuid.UUID) -> None:
    lessons = await outline(client_a, lecture_id)
    lid = lessons[0]["id"]
    summary = (await client_a.get(f"/api/lessons/{lid}/summary")).json()
    assert summary["number"] == "1.1"
    assert summary["sections"]
    assert "giao-trinh-csdl-final" not in summary["content_md"]
    slides = (await client_a.get(f"/api/lessons/{lid}/slides")).json()
    assert slides["pptx_available"] is True
    assert slides["deck"]["slides"][0]["layout"] == "title"
    res = await client_a.get(f"/api/lessons/{lid}/slides.pptx")
    assert res.status_code == 200 and res.content[:2] == b"PK"
    assert "filename*=UTF-8''1.1" in res.headers["content-disposition"]
    # Bài chưa tạo → 409
    pending = lessons[1]["id"]
    for path in ("summary", "slides", "slides.pptx"):
        res = await client_a.get(f"/api/lessons/{pending}/{path}")
        assert res.status_code == 409
        assert res.json()["code"] == "LESSON_NOT_READY"


async def test_other_users_lesson_and_lecture_are_404(
    client_a: AsyncClient, client_b: AsyncClient, lecture_id: uuid.UUID
) -> None:
    lessons = await outline(client_a, lecture_id)
    lid = lessons[0]["id"]
    for method, path in [
        ("GET", f"/api/lessons/{lid}/summary"),
        ("GET", f"/api/lessons/{lid}/slides"),
        ("GET", f"/api/lessons/{lid}/slides.pptx"),
        ("GET", f"/api/lessons/{lid}/quizzes"),
        ("POST", f"/api/lessons/{lid}/quizzes"),
    ]:
        res = await client_b.request(method, path)
        assert res.status_code == 404, (method, path)
        assert res.json()["code"] == "LESSON_NOT_FOUND"
    for method, path, body in [
        ("GET", f"/api/lectures/{lecture_id}/outline", None),
        ("POST", f"/api/lectures/{lecture_id}/lessons/generate", {"lesson_ids": [lid]}),
        ("POST", f"/api/lectures/{lecture_id}/regenerate", None),
        ("GET", f"/api/lectures/{lecture_id}/quizzes", None),
        ("POST", f"/api/lectures/{lecture_id}/quizzes", {"lesson_ids": [lid]}),
    ]:
        res = await client_b.request(method, path, json=body)
        assert res.status_code == 404, (method, path)
        assert res.json()["code"] == "LECTURE_NOT_FOUND"
    assert (await client_b.get("/api/lessons/not-a-uuid/summary")).status_code == 404


async def test_get_quiz_hides_answers(client_a: AsyncClient, lecture_id: uuid.UUID) -> None:
    lessons = await outline(client_a, lecture_id)
    quiz = await lesson_quiz(client_a, lessons[0]["id"])
    assert quiz["lesson_id"] == lessons[0]["id"] and quiz["is_default"]
    res = await client_a.get(f"/api/quizzes/{quiz['id']}")
    assert res.status_code == 200
    assert "answer_index" not in res.text
    assert "explanation" not in res.text
    body = res.json()
    assert body["scope_title"] == "Bài 1.1: 1.1 Khái niệm cơ sở dữ liệu"
    assert len(body["questions"]) == 5
    assert set(body["questions"][0]) == {"id", "position", "question", "options", "page_ref"}


async def test_grading_counts_blank_and_missing_as_wrong(
    client_a: AsyncClient, lecture_id: uuid.UUID
) -> None:
    lessons = await outline(client_a, lecture_id)
    quiz = await lesson_quiz(client_a, lessons[0]["id"])
    key = answer_key(quiz["id"])
    ids = list(key)
    answers: dict[str, int | None] = {ids[0]: key[ids[0]], ids[1]: key[ids[1]]}
    answers[ids[2]] = (key[ids[2]] + 1) % 4  # sai
    answers[ids[3]] = None  # bỏ trống; câu 5 không gửi
    res = await client_a.post(f"/api/quizzes/{quiz['id']}/attempts", json={"answers": answers})
    assert res.status_code == 201, res.text
    result = res.json()
    assert result["score"] == 2
    assert result["total"] == 5
    by_id = {r["question_id"]: r for r in result["results"]}
    assert by_id[ids[0]]["is_correct"] is True
    assert by_id[ids[2]]["is_correct"] is False
    assert by_id[ids[3]]["selected_index"] is None and by_id[ids[3]]["is_correct"] is False
    assert by_id[ids[4]]["selected_index"] is None
    assert result["by_chapter"] == [
        {"chapter_idx": 0, "title": "1.1 1.1 Khái niệm cơ sở dữ liệu", "correct": 2, "total": 5}
    ]
    assert result["lesson_id"] == lessons[0]["id"]

    history = (await client_a.get(f"/api/quizzes/{quiz['id']}/attempts")).json()
    assert history["total"] == 1
    again = (await client_a.get(f"/api/attempts/{result['id']}")).json()
    assert again["score"] == 2
    summary = await lesson_quiz(client_a, lessons[0]["id"])
    assert summary["attempt_count"] == 1 and summary["best_score"] == 2


async def test_foreign_question_id_is_422(client_a: AsyncClient, lecture_id: uuid.UUID) -> None:
    lessons = await outline(client_a, lecture_id)
    quiz = await lesson_quiz(client_a, lessons[0]["id"])
    res = await client_a.post(
        f"/api/quizzes/{quiz['id']}/attempts", json={"answers": {str(uuid.uuid4()): 1}}
    )
    assert res.status_code == 422
    qid = next(iter(answer_key(quiz["id"])))
    res = await client_a.post(f"/api/quizzes/{quiz['id']}/attempts", json={"answers": {qid: 7}})
    assert res.status_code == 422


async def test_quiz_and_attempt_of_other_user_is_404(
    client_a: AsyncClient, client_b: AsyncClient, lecture_id: uuid.UUID
) -> None:
    lessons = await outline(client_a, lecture_id)
    quiz = await lesson_quiz(client_a, lessons[0]["id"])
    attempt = (
        await client_a.post(f"/api/quizzes/{quiz['id']}/attempts", json={"answers": {}})
    ).json()
    for method, path in [
        ("GET", f"/api/quizzes/{quiz['id']}"),
        ("DELETE", f"/api/quizzes/{quiz['id']}"),
        ("POST", f"/api/quizzes/{quiz['id']}/attempts"),
        ("GET", f"/api/quizzes/{quiz['id']}/attempts"),
    ]:
        kwargs = {"json": {"answers": {}}} if method == "POST" else {}
        res = await client_b.request(method, path, **kwargs)
        assert res.status_code == 404, (method, path)
        assert res.json()["code"] == "QUIZ_NOT_FOUND"
    res = await client_b.get(f"/api/attempts/{attempt['id']}")
    assert res.status_code == 404
    assert res.json()["code"] == "ATTEMPT_NOT_FOUND"


async def test_extra_lesson_quiz(
    client_a: AsyncClient,
    lecture_id: uuid.UUID,
    jobs: dict[str, list[object]],
    memory_storage: MemoryStorage,
) -> None:
    lessons = await outline(client_a, lecture_id)
    res = await client_a.post(
        f"/api/lessons/{lessons[0]['id']}/quizzes", json={"num_questions": 10}
    )
    assert res.status_code == 202
    quiz = res.json()
    assert quiz["status"] == "queued" and len(jobs["quiz"]) == 1
    assert (await client_a.get(f"/api/quizzes/{quiz['id']}")).json()["code"] == "QUIZ_NOT_READY"
    res = await client_a.post(f"/api/lessons/{lessons[0]['id']}/quizzes", json={"num_questions": 3})
    assert res.status_code == 422
    res = await client_a.post(f"/api/lessons/{lessons[1]['id']}/quizzes", json={})
    assert res.status_code == 409

    llm = FakeLLMClient()
    with sync_session() as db:
        LecturePipeline(db, llm, memory_storage).run_quiz(uuid.UUID(quiz["id"]))
    assert all("Không lặp lại các câu hỏi đã có" in user for _, user in llm.calls)
    detail = (await client_a.get(f"/api/quizzes/{quiz['id']}")).json()
    assert len(detail["questions"]) == 10
    assert (await client_a.delete(f"/api/quizzes/{quiz['id']}")).status_code == 204


async def test_scope_quiz_over_selected_lessons(
    client_a: AsyncClient, lecture_id: uuid.UUID, memory_storage: MemoryStorage
) -> None:
    lessons = await outline(client_a, lecture_id)
    with sync_session() as db:
        LecturePipeline(db, FakeLLMClient(), memory_storage).run_lesson(uuid.UUID(lessons[1]["id"]))
    ids = [lessons[0]["id"], lessons[1]["id"]]
    res = await client_a.post(
        f"/api/lectures/{lecture_id}/quizzes", json={"num_questions": 10, "lesson_ids": ids}
    )
    assert res.status_code == 202, res.text
    quiz = res.json()
    assert quiz["lesson_id"] is None and quiz["lesson_ids"] == ids
    with sync_session() as db:
        LecturePipeline(db, FakeLLMClient(), memory_storage).run_quiz(uuid.UUID(quiz["id"]))
    detail = (await client_a.get(f"/api/quizzes/{quiz['id']}")).json()
    assert detail["scope_title"] == "Quiz tổng hợp 2 bài"
    assert len(detail["questions"]) == 10
    result = (
        await client_a.post(f"/api/quizzes/{quiz['id']}/attempts", json={"answers": {}})
    ).json()
    assert [c["total"] for c in result["by_chapter"]] == [5, 5]
    # Bài chưa tạo học liệu không chọn được
    res = await client_a.post(
        f"/api/lectures/{lecture_id}/quizzes",
        json={"num_questions": 10, "lesson_ids": [lessons[2]["id"]]},
    )
    assert res.status_code == 409


async def test_regenerate_resets_outline(
    client_a: AsyncClient,
    lecture_id: uuid.UUID,
    jobs: dict[str, list[object]],
    memory_storage: MemoryStorage,
) -> None:
    assert any("/lessons/" in k for k in memory_storage.objects)
    res = await client_a.post(f"/api/lectures/{lecture_id}/regenerate")
    assert res.status_code == 202
    assert res.json()["status"] == "queued"
    assert jobs["lecture"] == [lecture_id]
    assert (await client_a.get(f"/api/lectures/{lecture_id}/outline")).json()["chapters"] == []
    assert not any("/lessons/" in k for k in memory_storage.objects)
    assert any(k.endswith("source.pdf") for k in memory_storage.objects)
    # Đang chờ xử lý → không tạo lại được
    assert (await client_a.post(f"/api/lectures/{lecture_id}/regenerate")).status_code == 409


async def test_old_format_lecture_needs_regenerate(
    client_a: AsyncClient, user_a: tuple[User, str]
) -> None:
    with sync_session() as db:
        lecture = Lecture(
            user_id=user_a[0].id,
            title="cũ",
            original_filename="x.pdf",
            pdf_key="k",
            file_size=1,
            page_count=1,
            status="completed",
        )
        db.add(lecture)
        db.commit()
        lid = lecture.id
    body = (await client_a.get(f"/api/lectures/{lid}")).json()
    assert body["needs_regenerate"] is True
    res = await client_a.post(
        f"/api/lectures/{lid}/lessons/generate", json={"lesson_ids": [str(uuid.uuid4())]}
    )
    assert res.status_code == 422


# ---------- Sửa quiz (ADR-0018) ----------


def as_input(q: dict) -> dict:
    keys = ("id", "question", "options", "answer_index", "explanation", "page_ref", "lesson_id")
    return {k: q[k] for k in keys}


def manual(text: str, **extra: object) -> dict:
    return {
        "question": text,
        "options": ["Một", "Hai", "Ba", "Bốn"],
        "answer_index": 2,
        "explanation": "",
        **extra,
    }


async def test_edit_quiz_replaces_questions_and_clears_history(
    client_a: AsyncClient, lecture_id: uuid.UUID
) -> None:
    lessons = await outline(client_a, lecture_id)
    quiz = await lesson_quiz(client_a, lessons[0]["id"])
    qid = quiz["id"]
    await client_a.post(f"/api/quizzes/{qid}/attempts", json={"answers": {}})

    res = await client_a.get(f"/api/quizzes/{qid}/edit")
    assert res.status_code == 200, res.text
    editable = res.json()
    assert editable["attempt_count"] == 1 and editable["edited_at"] is None
    assert [ls["id"] for ls in editable["lessons"]] == [lessons[0]["id"]]
    questions = editable["questions"]
    assert len(questions) == 5
    assert all(q["source"] == "ai" and q["lesson_id"] == lessons[0]["id"] for q in questions)
    assert "answer_index" in questions[0] and "explanation" in questions[0]

    first, second, third = (as_input(q) for q in questions[:3])
    first = {
        **first,
        "question": "  Câu đã sửa?  ",
        "answer_index": (first["answer_index"] + 1) % 4,
    }
    body = {"questions": [third, manual("Câu nhập tay?"), first, second]}  # bỏ câu 4, 5
    res = await client_a.put(f"/api/quizzes/{qid}/questions", json=body)
    assert res.status_code == 200, res.text
    saved = res.json()
    assert saved["num_questions"] == 4 and saved["edited_at"] is not None
    assert saved["attempt_count"] == 0
    assert [q["position"] for q in saved["questions"]] == [1, 2, 3, 4]
    assert [q["source"] for q in saved["questions"]] == ["ai", "manual", "edited", "ai"]
    assert saved["questions"][2]["question"] == "Câu đã sửa?"
    assert saved["questions"][1]["page_ref"] is None
    assert saved["questions"][1]["options"] == ["Một", "Hai", "Ba", "Bốn"]  # không xáo trộn

    # Lịch sử làm bài đã bị xoá; danh sách quiz có edited_at
    assert (await client_a.get(f"/api/quizzes/{qid}/attempts")).json()["total"] == 0
    summary = await lesson_quiz(client_a, lessons[0]["id"])
    assert summary["num_questions"] == 4 and summary["edited_at"] is not None

    # Trang làm bài vẫn không lộ đáp án
    res = await client_a.get(f"/api/quizzes/{qid}")
    assert "answer_index" not in res.text and "explanation" not in res.text
    assert res.json()["questions"][1]["page_ref"] is None

    # Chấm theo đáp án mới, câu nhập tay tính vào điểm theo bài
    key = answer_key(qid)
    result = (await client_a.post(f"/api/quizzes/{qid}/attempts", json={"answers": key})).json()
    assert result["score"] == 4 and result["total"] == 4
    assert result["by_chapter"][0]["total"] == 4


async def test_edit_quiz_validation(client_a: AsyncClient, lecture_id: uuid.UUID) -> None:
    lessons = await outline(client_a, lecture_id)
    quiz = await lesson_quiz(client_a, lessons[0]["id"])
    qid = quiz["id"]
    editable = (await client_a.get(f"/api/quizzes/{qid}/edit")).json()
    first = as_input(editable["questions"][0])
    page_end = editable["lessons"][0]["page_end"]

    async def put(questions: list[dict]) -> dict:
        res = await client_a.put(f"/api/quizzes/{qid}/questions", json={"questions": questions})
        assert res.status_code == 422, res.text
        return res.json()

    body = await put([{**first, "id": str(uuid.uuid4())}])
    assert body["errors"][0]["field"] == "questions.0.id"
    body = await put([first, first])
    assert body["errors"][0]["field"] == "questions.1.id"
    body = await put([manual("Trùng?", options=["A", "a", "B", "C"])])
    assert body["errors"][0] == {
        "field": "questions.0.options",
        "message": "Các lựa chọn không được trùng nhau.",
    }
    body = await put([manual("Trang?", page_ref=page_end + 1)])
    assert body["errors"][0]["field"] == "questions.0.page_ref"
    await put([manual("   ")])
    await put([])
    await put([manual(f"Câu {i}?") for i in range(31)])
    # Không lưu gì khi lỗi
    assert len(answer_key(qid)) == 5


async def test_edit_quiz_of_other_user_is_404(
    client_a: AsyncClient, client_b: AsyncClient, lecture_id: uuid.UUID
) -> None:
    lessons = await outline(client_a, lecture_id)
    quiz = await lesson_quiz(client_a, lessons[0]["id"])
    res = await client_b.get(f"/api/quizzes/{quiz['id']}/edit")
    assert res.status_code == 404 and res.json()["code"] == "QUIZ_NOT_FOUND"
    res = await client_b.put(
        f"/api/quizzes/{quiz['id']}/questions", json={"questions": [manual("Câu?")]}
    )
    assert res.status_code == 404 and res.json()["code"] == "QUIZ_NOT_FOUND"
    assert len(answer_key(quiz["id"])) == 5


async def test_edit_quiz_not_ready_or_old_format_is_409(
    client_a: AsyncClient, lecture_id: uuid.UUID
) -> None:
    lessons = await outline(client_a, lecture_id)
    queued = (await client_a.post(f"/api/lessons/{lessons[0]['id']}/quizzes", json={})).json()
    res = await client_a.get(f"/api/quizzes/{queued['id']}/edit")
    assert res.status_code == 409 and res.json()["code"] == "QUIZ_NOT_READY"

    with sync_session() as db:
        old = Quiz(lecture_id=lecture_id, status="completed", num_questions=1)
        db.add(old)
        db.flush()
        db.add(
            Question(
                quiz_id=old.id,
                position=1,
                question="Câu cũ?",
                options=["A", "B", "C", "D"],
                answer_index=0,
                explanation="",
                page_ref=1,
                chapter_idx=0,
            )
        )
        db.commit()
        old_id = old.id
    res = await client_a.put(
        f"/api/quizzes/{old_id}/questions", json={"questions": [manual("Câu?")]}
    )
    assert res.status_code == 409 and res.json()["code"] == "QUIZ_NOT_EDITABLE"


async def test_edit_scope_quiz_assigns_lessons(
    client_a: AsyncClient, lecture_id: uuid.UUID, memory_storage: MemoryStorage
) -> None:
    lessons = await outline(client_a, lecture_id)
    with sync_session() as db:
        LecturePipeline(db, FakeLLMClient(), memory_storage).run_lesson(uuid.UUID(lessons[1]["id"]))
    ids = [lessons[0]["id"], lessons[1]["id"]]
    quiz = (
        await client_a.post(
            f"/api/lectures/{lecture_id}/quizzes", json={"num_questions": 5, "lesson_ids": ids}
        )
    ).json()
    with sync_session() as db:
        LecturePipeline(db, FakeLLMClient(), memory_storage).run_quiz(uuid.UUID(quiz["id"]))
    editable = (await client_a.get(f"/api/quizzes/{quiz['id']}/edit")).json()
    assert [ls["id"] for ls in editable["lessons"]] == ids
    kept = [as_input(q) for q in editable["questions"]]
    second = editable["lessons"][1]

    res = await client_a.put(
        f"/api/quizzes/{quiz['id']}/questions", json={"questions": [*kept, manual("Thiếu bài?")]}
    )
    assert res.status_code == 422
    assert res.json()["errors"][0]["field"] == f"questions.{len(kept)}.lesson_id"

    extra = manual("Câu bài 2?", lesson_id=second["id"], page_ref=second["page_start"])
    res = await client_a.put(
        f"/api/quizzes/{quiz['id']}/questions", json={"questions": [*kept, extra]}
    )
    assert res.status_code == 200, res.text
    assert res.json()["questions"][-1]["lesson_id"] == second["id"]
    with sync_session() as db:
        added = db.scalar(select(Question).where(Question.question == "Câu bài 2?"))
        assert added is not None and added.chapter_idx == lessons_of(lecture_id)[1].idx
    result = (
        await client_a.post(f"/api/quizzes/{quiz['id']}/attempts", json={"answers": {}})
    ).json()
    assert sum(c["total"] for c in result["by_chapter"]) == len(kept) + 1
    assert result["by_chapter"][1]["total"] >= 1
