import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Lỗi nghiệp vụ; handler chung trả {"code", "detail"} (api.md mục 1.6)."""

    def __init__(
        self,
        code: str,
        detail: str,
        status: int = 400,
        headers: dict[str, str] | None = None,
        errors: list[dict[str, str]] | None = None,
    ):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status
        self.headers = headers
        self.errors = errors


LECTURE_NOT_FOUND = ("LECTURE_NOT_FOUND", "Không tìm thấy bài giảng.")
QUIZ_NOT_FOUND = ("QUIZ_NOT_FOUND", "Không tìm thấy quiz.")
ATTEMPT_NOT_FOUND = ("ATTEMPT_NOT_FOUND", "Không tìm thấy lần làm bài.")
LESSON_NOT_FOUND = ("LESSON_NOT_FOUND", "Không tìm thấy bài học.")

_HTTP_CODES = {
    401: ("UNAUTHENTICATED", "Bạn cần đăng nhập."),
    403: ("FORBIDDEN", "Không có quyền truy cập."),
    404: ("NOT_FOUND", "Không tìm thấy."),
    405: ("METHOD_NOT_ALLOWED", "Phương thức không được hỗ trợ."),
    413: ("FILE_TOO_LARGE", "File vượt quá dung lượng cho phép."),
}


def _field_name(loc: tuple[Any, ...]) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "form")]
    return ".".join(parts) or "body"


def _vi_message(err: dict[str, Any]) -> str:
    """Thông điệp lỗi validate bằng tiếng Việt cho các lỗi thường gặp."""
    ctx = err.get("ctx") or {}
    match err.get("type"):
        case "missing":
            return "Bắt buộc."
        case "string_too_long":
            return f"Tối đa {ctx.get('max_length')} ký tự."
        case "string_too_short":
            return (
                "Không được để trống."
                if ctx.get("min_length") == 1
                else (f"Tối thiểu {ctx.get('min_length')} ký tự.")
            )
        case "literal_error" | "enum":
            return f"Giá trị phải là một trong: {ctx.get('expected')}."
        case "int_parsing" | "int_type":
            return "Phải là số nguyên."
        case "greater_than_equal" | "less_than_equal" | "greater_than" | "less_than":
            return "Giá trị nằm ngoài khoảng cho phép."
        case _:
            return "Giá trị không hợp lệ."


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        body: dict[str, Any] = {"code": exc.code, "detail": exc.detail}
        if exc.errors:
            body["errors"] = exc.errors
        return JSONResponse(body, status_code=exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"field": _field_name(e["loc"]), "message": _vi_message(e)} for e in exc.errors()]
        return JSONResponse(
            {"code": "VALIDATION_ERROR", "detail": "Dữ liệu không hợp lệ.", "errors": errors},
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, detail = _HTTP_CODES.get(exc.status_code, ("HTTP_ERROR", str(exc.detail)))
        return JSONResponse({"code": code, "detail": detail}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            {"code": "INTERNAL", "detail": "Đã xảy ra lỗi, vui lòng thử lại."}, status_code=500
        )
