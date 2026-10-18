# ADR-0006: PostgreSQL + SQLAlchemy 2.0 + Alembic

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-18
- **Ghi chú:** Lược đồ dưới đây là bản phác thảo tại thời điểm quyết định. Lược đồ chi tiết, cập nhật: [data-model.md](../design/data-model.md).

## Bối cảnh
Dữ liệu có quan hệ rõ ràng (user → lecture → summary/slides/quiz → question/attempt), kèm một số dữ liệu bán cấu trúc (danh sách slide, lựa chọn đáp án).

## Các phương án
1. **PostgreSQL** – quan hệ mạnh, có `JSONB` cho dữ liệu bán cấu trúc.
2. **SQLite** – không cần server, nhưng ghi đồng thời từ API và nhiều worker dễ bị khoá.
3. **MongoDB** – linh hoạt nhưng dữ liệu vốn có quan hệ; mất ràng buộc khoá ngoại.

## Quyết định
- **PostgreSQL 16**, truy cập bằng **SQLAlchemy 2.0** (API kiểu mới, typed `Mapped[...]`).
- API dùng driver async `asyncpg`; worker Celery (đồng bộ) dùng `psycopg` — cùng model, khác engine.
- Migration bằng **Alembic**, chạy tự động khi container `api` khởi động.
- Khoá chính dạng **UUID** (tránh đoán được ID trong URL).
- Dữ liệu bán cấu trúc lưu `JSONB` nhưng luôn được kiểm tra bằng Pydantic trước khi ghi.

## Lược đồ
```
users
  id UUID PK, google_id TEXT UNIQUE, email TEXT, name TEXT,
  avatar_url TEXT, created_at TIMESTAMPTZ

sessions
  id UUID PK, user_id FK→users ON DELETE CASCADE,
  token_hash TEXT UNIQUE, expires_at TIMESTAMPTZ, created_at

lectures
  id UUID PK, user_id FK→users ON DELETE CASCADE, title TEXT,
  pdf_key TEXT, page_count INT,
  status TEXT CHECK IN ('queued','processing','completed','failed'),
  progress_step TEXT NULL,          -- 'extracting' | 'summarizing' | 'slides' | 'quiz'
  error TEXT NULL, created_at, updated_at
  INDEX (user_id, created_at DESC)

chapters
  id UUID PK, lecture_id FK ON DELETE CASCADE,
  idx INT, title TEXT, page_start INT, page_end INT, text TEXT

summaries
  id UUID PK, lecture_id FK UNIQUE ON DELETE CASCADE, content_md TEXT

slide_decks
  id UUID PK, lecture_id FK UNIQUE ON DELETE CASCADE,
  slides JSONB, pptx_key TEXT

quizzes
  id UUID PK, lecture_id FK ON DELETE CASCADE,
  status TEXT, num_questions INT, created_at

questions
  id UUID PK, quiz_id FK ON DELETE CASCADE, position INT,
  question TEXT, options JSONB, answer_index SMALLINT,
  explanation TEXT, page_ref INT, chapter_idx INT

quiz_attempts
  id UUID PK, quiz_id FK ON DELETE CASCADE, user_id FK,
  answers JSONB, score INT, total INT, created_at
```

So với PRD: thêm bảng `sessions` (ADR-0005), `chapters` (lưu kết quả trích xuất để sinh quiz mới không phải đọc lại PDF), cột `progress_step` (ADR-0013), `status` cho `quizzes` (quiz sinh bất đồng bộ).

## Hệ quả
- **Tích cực:** Ràng buộc toàn vẹn, xoá dây chuyền tự động khi xoá bài giảng/tài khoản; JSONB linh hoạt khi đổi cấu trúc slide.
- **Tiêu cực:** Thêm một container; hai engine (async/sync) cần cấu hình cẩn thận.
