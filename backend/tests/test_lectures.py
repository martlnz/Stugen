from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services import lectures as lecture_service
from tests.fakes import MemoryStorage

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def no_enqueue(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    calls: list[object] = []
    monkeypatch.setattr(lecture_service, "enqueue_process_lecture", calls.append)
    return calls


async def upload(client: AsyncClient, name: str = "sample.pdf", **data: str) -> dict:
    content = (FIXTURES / name).read_bytes()
    res = await client.post(
        "/api/lectures", files={"file": (name, content, "application/pdf")}, data=data
    )
    assert res.status_code == 201, res.text
    return res.json()


async def test_upload_creates_queued_lecture(
    client_a: AsyncClient, memory_storage: MemoryStorage, no_enqueue: list[object]
) -> None:
    body = await upload(client_a)
    assert body["status"] == "queued"
    assert body["title"] == "Nhập môn Cơ sở dữ liệu"  # lấy từ metadata PDF
    assert body["page_count"] == 14
    assert body["lessons"] == {"total": 0, "completed": 0, "processing": 0, "failed": 0}
    assert body["needs_regenerate"] is False
    assert len(memory_storage.objects) == 1
    assert len(no_enqueue) == 1


async def test_upload_uses_given_title(client_a: AsyncClient) -> None:
    body = await upload(client_a, title="CSDL – HK1")
    assert body["title"] == "CSDL – HK1"


async def test_upload_scan_pdf_is_accepted(client_a: AsyncClient) -> None:
    body = await upload(client_a, "scan.pdf")
    assert body["title"] == "scan"


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"hello world, not a pdf", "INVALID_FILE_TYPE"),
        (b"%PDF-1.7\nbroken", "PDF_CORRUPTED"),
        ((FIXTURES / "encrypted.pdf").read_bytes(), "PDF_ENCRYPTED"),
    ],
)
async def test_upload_rejects_invalid_files(
    client_a: AsyncClient, content: bytes, code: str
) -> None:
    res = await client_a.post(
        "/api/lectures", files={"file": ("x.pdf", content, "application/pdf")}
    )
    assert res.status_code == 400
    assert res.json()["code"] == code


async def test_upload_rejects_too_large(
    client_a: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lecture_service.settings, "max_upload_mb", 0)
    res = await client_a.post(
        "/api/lectures", files={"file": ("x.pdf", b"%PDF-" + b"0" * 10, "application/pdf")}
    )
    assert res.status_code == 413
    assert res.json()["code"] == "FILE_TOO_LARGE"


async def test_upload_rejects_too_many_pages(
    client_a: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lecture_service.settings, "max_pages", 3)
    res = await client_a.post(
        "/api/lectures",
        files={"file": ("x.pdf", (FIXTURES / "sample.pdf").read_bytes(), "application/pdf")},
    )
    assert res.status_code == 400
    assert res.json()["code"] == "PDF_TOO_MANY_PAGES"


async def test_upload_requires_login(anon_client: AsyncClient) -> None:
    res = await anon_client.post(
        "/api/lectures", files={"file": ("x.pdf", b"%PDF-", "application/pdf")}
    )
    assert res.status_code == 401


async def test_list_only_own_lectures(client_a: AsyncClient, client_b: AsyncClient) -> None:
    await upload(client_a)
    await upload(client_a, title="Thứ hai")
    await upload(client_b)
    body = (await client_a.get("/api/lectures")).json()
    assert body["total"] == 2
    assert [i["title"] for i in body["items"]] == ["Thứ hai", "Nhập môn Cơ sở dữ liệu"]
    res = await client_a.get("/api/lectures", params={"q": "thứ", "page_size": 1})
    assert res.json()["total"] == 1


async def test_other_users_lecture_is_404(client_a: AsyncClient, client_b: AsyncClient) -> None:
    lid = (await upload(client_a))["id"]
    for method, path in [
        ("GET", f"/api/lectures/{lid}"),
        ("PATCH", f"/api/lectures/{lid}"),
        ("DELETE", f"/api/lectures/{lid}"),
        ("POST", f"/api/lectures/{lid}/retry"),
        ("GET", f"/api/lectures/{lid}/pdf"),
        ("GET", f"/api/lectures/{lid}/outline"),
        ("GET", f"/api/lectures/{lid}/quizzes"),
    ]:
        kwargs = {"json": {"title": "x"}} if method == "PATCH" else {}
        res = await client_b.request(method, path, **kwargs)
        assert res.status_code == 404, (method, path, res.status_code)
        assert res.json()["code"] == "LECTURE_NOT_FOUND"
    assert (await client_a.get(f"/api/lectures/{lid}")).status_code == 200


async def test_invalid_lecture_id_is_404(client_a: AsyncClient) -> None:
    res = await client_a.get("/api/lectures/not-a-uuid")
    assert res.status_code == 404


async def test_rename_lecture(client_a: AsyncClient) -> None:
    lid = (await upload(client_a))["id"]
    res = await client_a.patch(f"/api/lectures/{lid}", json={"title": "  Tên mới  "})
    assert res.status_code == 200
    assert res.json()["title"] == "Tên mới"
    res = await client_a.patch(f"/api/lectures/{lid}", json={"title": "x" * 201})
    assert res.status_code == 422
    assert res.json()["errors"][0] == {"field": "title", "message": "Tối đa 200 ký tự."}
    res = await client_a.patch(f"/api/lectures/{lid}", json={"title": "   "})
    assert res.status_code == 422


async def test_delete_lecture_removes_files(
    client_a: AsyncClient, memory_storage: MemoryStorage
) -> None:
    lid = (await upload(client_a))["id"]
    assert (await client_a.delete(f"/api/lectures/{lid}")).status_code == 204
    assert memory_storage.objects == {}
    assert (await client_a.get(f"/api/lectures/{lid}")).status_code == 404


async def test_download_pdf_with_range(client_a: AsyncClient) -> None:
    lid = (await upload(client_a))["id"]
    full = (FIXTURES / "sample.pdf").read_bytes()
    res = await client_a.get(f"/api/lectures/{lid}/pdf")
    assert res.status_code == 200
    assert res.content == full
    assert res.headers["content-disposition"].startswith("inline")
    res = await client_a.get(f"/api/lectures/{lid}/pdf", headers={"Range": "bytes=0-9"})
    assert res.status_code == 206
    assert res.content == full[:10]
    res = await client_a.get(f"/api/lectures/{lid}/pdf", params={"download": "true"})
    assert res.headers["content-disposition"].startswith("attachment")


async def test_retry_requires_failed_status(client_a: AsyncClient) -> None:
    lid = (await upload(client_a))["id"]
    res = await client_a.post(f"/api/lectures/{lid}/retry")
    assert res.status_code == 409
    assert res.json()["code"] == "LECTURE_NOT_FAILED"
