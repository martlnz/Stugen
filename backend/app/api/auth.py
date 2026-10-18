import logging

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import SESSION_COOKIE
from app.core.security import safe_next_path
from app.db.session import get_db
from app.services.auth import create_session, delete_session, upsert_google_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
)


def _login_error(code: str) -> RedirectResponse:
    return RedirectResponse(f"/?login_error={code}", status_code=302)


@router.get("/google/login", status_code=302, response_class=RedirectResponse)
async def google_login(request: Request, next: str | None = None) -> RedirectResponse:
    request.session.clear()
    request.session["next"] = safe_next_path(next)
    return await oauth.google.authorize_redirect(request, settings.oauth_redirect_uri)


@router.get("/google/callback", status_code=302, response_class=RedirectResponse)
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    if request.query_params.get("error"):
        code = (
            "access_denied" if request.query_params["error"] == "access_denied" else "google_error"
        )
        return _login_error(code)
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as exc:
        logger.warning("Google OAuth failed: %s", exc.error)
        return _login_error("invalid_state" if "state" in (exc.error or "") else "google_error")
    except Exception:
        logger.exception("Google OAuth unexpected error")
        return _login_error("google_error")

    claims = token.get("userinfo") or {}
    if not claims.get("sub") or not claims.get("email"):
        return _login_error("google_error")
    if not claims.get("email_verified"):
        return _login_error("email_not_verified")

    user = await upsert_google_user(db, dict(claims))
    sid = await create_session(db, user)
    await db.commit()

    next_path = safe_next_path(request.session.pop("next", None))
    request.session.clear()
    response = RedirectResponse(next_path, status_code=302)
    response.set_cookie(
        SESSION_COOKIE,
        sid,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout", status_code=204)
async def logout(
    sid: str | None = Cookie(default=None, include_in_schema=False),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if sid:
        await delete_session(db, sid)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=True, samesite="lax")
    return response
