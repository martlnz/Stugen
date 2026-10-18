"""Quiz: ẩn đáp án, chấm điểm, quyền sở hữu, nội dung bài giảng (summary/slides/pptx)."""

import uuid

import pytest
from httpx import AsyncClient

from app.ai.llm.fake import FakeLLMClient
from app.db.models import Question, User
from app.db.session import sync_session
from app.services import quizzes as quiz_service
from app.worker.pipeline import LecturePipeline
from tests.fakes import MemoryStorage
from tests.test_pipeline import FIXTURES


@pytest.fixture(autouse=True)
def no_enqueue(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    calls: list[object] = []
    monkeypatch.setattr(quiz_service, "enqueue_generate_quiz", calls.append)
    return calls


@pytest.fixture
def processed_lecture(user_a: tuple[User, str], memory_storage: MemoryStorage) -> uuid.UUID:
    """Bài giảng của alice đã xử lý xong bằng FakeLLMClient."""
    from app.db.models import Lecture

    user = user_a[0]
    with sync_session() as db:
        lecture = Lecture(
            user_id=user.id,
            title="Nhập môn CSDL",
            original_filename="sample.pdf",
            pdf_key=f"users/{user.id}/lectures/l/source.pdf",
            file_size=1,
            page_count=6,
        )
        db.add(lecture)
        db.commit()
        memory_storage.put(lecture.pdf_key, (FIXTURES / "sample.pdf").read_bytes(), "x")
        LecturePipeline(db, FakeLLMClient(), memory_storage).run(lecture.id)
        return lecture.id


async def default_quiz(client: AsyncClient, lecture_id: uuid.UUID) -> dict:
    res = await client.get(f"/api/lectures/{lecture_id}/quizzes")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    return items[0]


def answer_key(quiz_id: str) -> dict[str, int]:
    with sync_session() as db:
        from sqlalchemy import select

        rows = db.scalars(select(Question).where(Question.quiz_id == uuid.UUID(quiz_id)))
        return {str(q.id): q.answer_index for q in rows}


async def test_lecture_content_available(
    client_a: AsyncClient, processed_lecture: uuid.UUID
) -> None:
    lid = processed_lecture
    lecture = (await client_a.get(f"/api/lectures/{lid}")).json()
    assert lecture["status"] == "completed"
    assert lecture["available"] == {"summary": True, "slides": True, "pptx": True, "quiz": True}

    summary = (await client_a.get(f"/api/lectures/{lid}/summary")).json()
    assert len(summary["chapters"]) == 3
    assert summary["content_md"].startswith("# Nhập môn CSDL")

    slides = (await client_a.get(f"/api/lectures/{lid}/slides")).json()
    assert slides["pptx_available"] is True
    assert slides["deck"]["slides"][0]["layout"] == "title"

    res = await client_a.get(f"/api/lectures/{lid}/slides.pptx")
    assert res.status_code == 200
    assert res.content[:2] == b"PK"
    assert "filename*=UTF-8''Nh%E1%BA%ADp" in res.headers["content-disposition"]


async def test_summary_not_ready_is_409(client_a: AsyncClient, user_a: tuple[User, str]) -> None:
    from app.db.models import Lecture

    with sync_session() as db:
        lecture = Lecture(
            user_id=user_a[0].id,
            title="x",
            original_filename="x.pdf",
            pdf_key="k",
            file_size=1,
            page_count=1,
        )
        db.add(lecture)
        db.commit()
        lid = lecture.id
    for path in ("summary", "slides", "slides.pptx"):
        res = await client_a.get(f"/api/lectures/{lid}/{path}")
        assert res.status_code == 409
        assert res.json()["code"] == "LECTURE_NOT_READY"
    res = await client_a.post(f"/api/lectures/{lid}/quizzes", json={"num_questions": 10})
    assert res.status_code == 409


async def test_get_quiz_hides_answers(client_a: AsyncClient, processed_lecture: uuid.UUID) -> None:
    quiz = await default_quiz(client_a, processed_lecture)
    res = await client_a.get(f"/api/quizzes/{quiz['id']}")
    assert res.status_code == 200
    raw = res.text
    assert "answer_index" not in raw
    assert "explanation" not in raw
    body = res.json()
    assert len(body["questions"]) == 10
    assert set(body["questions"][0]) == {"id", "position", "question", "options", "page_ref"}


async def test_grading_counts_blank_and_missing_as_wrong(
    client_a: AsyncClient, processed_lecture: uuid.UUID
) -> None:
    quiz = await default_quiz(client_a, processed_lecture)
    key = answer_key(quiz["id"])
    ids = list(key)
    answers: dict[str, int | None] = {ids[0]: key[ids[0]], ids[1]: key[ids[1]]}
    answers[ids[2]] = (key[ids[2]] + 1) % 4  # sai
    answers[ids[3]] = None  # bỏ trống; các câu còn lại không gửi
    res = await client_a.post(f"/api/quizzes/{quiz['id']}/attempts", json={"answers": answers})
    assert res.status_code == 201, res.text
    result = res.json()
    assert result["score"] == 2
    assert result["total"] == 10
    by_id = {r["question_id"]: r for r in result["results"]}
    assert by_id[ids[0]]["is_correct"] is True
    assert by_id[ids[2]]["is_correct"] is False
    assert by_id[ids[3]]["selected_index"] is None
    assert by_id[ids[3]]["is_correct"] is False
    assert by_id[ids[5]]["selected_index"] is None
    assert by_id[ids[0]]["explanation"]
    assert sum(c["total"] for c in result["by_chapter"]) == 10
    assert sum(c["correct"] for c in result["by_chapter"]) == 2

    # Lịch sử và xem lại
    history = (await client_a.get(f"/api/quizzes/{quiz['id']}/attempts")).json()
    assert history["total"] == 1
    again = (await client_a.get(f"/api/attempts/{result['id']}")).json()
    assert again["score"] == 2
    summary = await default_quiz(client_a, processed_lecture)
    assert summary["attempt_count"] == 1
    assert summary["best_score"] == 2


async def test_all_correct(client_a: AsyncClient, processed_lecture: uuid.UUID) -> None:
    quiz = await default_quiz(client_a, processed_lecture)
    key = answer_key(quiz["id"])
    res = await client_a.post(f"/api/quizzes/{quiz['id']}/attempts", json={"answers": key})
    assert res.json()["score"] == 10


async def test_foreign_question_id_is_422(
    client_a: AsyncClient, processed_lecture: uuid.UUID
) -> None:
    quiz = await default_quiz(client_a, processed_lecture)
    res = await client_a.post(
        f"/api/quizzes/{quiz['id']}/attempts", json={"answers": {str(uuid.uuid4()): 1}}
    )
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION_ERROR"
    key = answer_key(quiz["id"])
    qid = next(iter(key))
    res = await client_a.post(f"/api/quizzes/{quiz['id']}/attempts", json={"answers": {qid: 7}})
    assert res.status_code == 422


async def test_quiz_and_attempt_of_other_user_is_404(
    client_a: AsyncClient, client_b: AsyncClient, processed_lecture: uuid.UUID
) -> None:
    quiz = await default_quiz(client_a, processed_lecture)
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


async def test_create_and_delete_quiz(
    client_a: AsyncClient, processed_lecture: uuid.UUID, no_enqueue: list[object]
) -> None:
    res = await client_a.post(
        f"/api/lectures/{processed_lecture}/quizzes", json={"num_questions": 20}
    )
    assert res.status_code == 202
    quiz = res.json()
    assert quiz["status"] == "queued"
    assert len(no_enqueue) == 1
    res = await client_a.get(f"/api/quizzes/{quiz['id']}")
    assert res.status_code == 409
    assert res.json()["code"] == "QUIZ_NOT_READY"
    res = await client_a.post(
        f"/api/lectures/{processed_lecture}/quizzes", json={"num_questions": 15}
    )
    assert res.status_code == 422
    assert (await client_a.delete(f"/api/quizzes/{quiz['id']}")).status_code == 204
    assert (await client_a.get(f"/api/quizzes/{quiz['id']}")).status_code == 404


async def test_generate_quiz_task_avoids_existing_questions(
    client_a: AsyncClient, processed_lecture: uuid.UUID, memory_storage: MemoryStorage
) -> None:
    res = await client_a.post(
        f"/api/lectures/{processed_lecture}/quizzes", json={"num_questions": 20}
    )
    qid = uuid.UUID(res.json()["id"])
    llm = FakeLLMClient()
    with sync_session() as db:
        LecturePipeline(db, llm, memory_storage).run_quiz(qid)
    assert all("Không lặp lại các câu hỏi đã có" in user for _, user in llm.calls)
    detail = (await client_a.get(f"/api/quizzes/{qid}")).json()
    assert len(detail["questions"]) == 20
