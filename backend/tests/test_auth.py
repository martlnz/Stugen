from httpx import AsyncClient

from app.core.security import safe_next_path


async def test_health(anon_client: AsyncClient) -> None:
    res = await anon_client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["db"] == "ok"


async def test_me_without_cookie_is_401(anon_client: AsyncClient) -> None:
    res = await anon_client.get("/api/me")
    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"


async def test_me_with_invalid_cookie_is_401(anon_client: AsyncClient) -> None:
    anon_client.cookies.set("sid", "not-a-real-token")
    res = await anon_client.get("/api/me")
    assert res.status_code == 401


async def test_me_returns_current_user(client_a: AsyncClient) -> None:
    res = await client_a.get("/api/me")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "alice"
    assert set(body) == {"id", "email", "name", "avatar_url", "created_at"}


async def test_unsafe_request_without_csrf_header_is_403(client_a: AsyncClient) -> None:
    res = await client_a.post("/api/auth/logout", headers={"X-Requested-With": ""})
    assert res.status_code == 403
    assert res.json()["code"] == "CSRF_REJECTED"


async def test_logout_deletes_session(client_a: AsyncClient) -> None:
    assert (await client_a.post("/api/auth/logout")).status_code == 204
    assert (await client_a.get("/api/me")).status_code == 401


async def test_logout_without_session_is_204(anon_client: AsyncClient) -> None:
    assert (await anon_client.post("/api/auth/logout")).status_code == 204


def test_safe_next_path_blocks_open_redirect() -> None:
    assert safe_next_path("/lectures/1") == "/lectures/1"
    assert safe_next_path("https://evil.com") == "/library"
    assert safe_next_path("//evil.com") == "/library"
    assert safe_next_path(None) == "/library"
