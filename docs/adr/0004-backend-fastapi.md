# ADR-0004: Backend API dùng FastAPI

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-18

## Bối cảnh
Backend bắt buộc dùng Python. Cần REST API cho frontend, nhận upload file, xác thực, chia sẻ code với AI worker.

## Các phương án
1. **FastAPI** – async, dùng Pydantic, tự sinh OpenAPI, nhẹ.
2. **Django + DRF** – đầy đủ (admin, ORM, auth) nhưng nặng, nhiều thứ không dùng tới.
3. **Flask** – đơn giản nhưng phải tự ghép validation, OpenAPI.

## Quyết định
Chọn **FastAPI** vì:
- Pydantic dùng chung cho cả schema API lẫn kiểm tra đầu ra JSON của LLM (ADR-0010).
- OpenAPI tự động → frontend sinh kiểu TypeScript (ADR-0003).
- Hỗ trợ upload streaming và dependency injection gọn cho xác thực/phân quyền.

## Quy ước
- Prefix `/api`; router chia theo tài nguyên: `auth`, `me`, `lectures`, `quizzes`, `attempts`.
- Dependency `get_current_user` cho mọi route cần đăng nhập.
- Dependency `get_owned_lecture(id)` trả **404** (không phải 403) nếu bài giảng không thuộc người dùng, tránh lộ sự tồn tại.
- Lỗi trả theo dạng `{"detail": "...", "code": "LECTURE_NOT_FOUND"}`.
- Cấu hình bằng `pydantic-settings`, đọc từ biến môi trường.
- Chạy bằng `uvicorn` (dev) / `gunicorn -k uvicorn.workers.UvicornWorker` (prod).
- Kiểm thử bằng `pytest` + `httpx.AsyncClient`.

## Hệ quả
- **Tích cực:** Nhẹ, nhanh, tài liệu API sẵn tại `/api/docs`.
- **Tiêu cực:** Không có trang admin như Django; nếu cần quản trị dùng `sqladmin` sau.
