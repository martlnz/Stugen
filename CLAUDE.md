# CLAUDE.md

Hướng dẫn cho Claude Code khi làm việc trong repository này.

## Dự án

**Stugen** – website phi thương mại: đăng nhập bằng Google, tải giáo trình PDF, sinh **tóm tắt**, **slide**, **quiz**; lưu bài giảng theo tài khoản.

Tài liệu nguồn (đọc trước khi làm tính năng liên quan):
- `docs/product/PRD.md` – yêu cầu và phạm vi
- `docs/adr/` – quyết định kiến trúc (0001–0014)
- `docs/design/data-model.md` – lược đồ CSDL, cấu trúc JSONB
- `docs/design/api.md` – hợp đồng API (nguồn chuẩn cho request/response)
- `docs/plans/plan-1-ngay.md` – kế hoạch hiện tại

## Cấu trúc

```
frontend/            Next.js (App Router) + TypeScript
backend/app/
  api/               FastAPI routers: auth, me, lectures, quizzes, attempts
  core/              config (pydantic-settings), security, deps
  db/                SQLAlchemy models, session (async cho API, sync cho worker)
  schemas/           Pydantic: schema API + schema đầu ra LLM
  services/          logic nghiệp vụ dùng chung
  ai/                pdf.py, llm/ (client + providers), prompts/*.j2, generators/
  worker/            Celery app + tasks
backend/alembic/     migrations
docs/                product/ (PRD), design/ (API, data model), adr/, plans/
docker-compose.yml   proxy, web, api, worker, postgres, redis, minio
Caddyfile
```

## Lệnh

```bash
make up          # docker compose up -d --build
make down
make logs        # docker compose logs -f api worker
make migrate     # alembic upgrade head
make revision m="mô tả"   # alembic revision --autogenerate
make test        # pytest backend
make lint        # ruff check + ruff format --check + (frontend) eslint, tsc
make fmt         # ruff format + prettier
make gen-api     # sinh frontend/src/lib/api-types.ts từ /api/openapi.json
```

Ứng dụng chạy tại `http://localhost`, tài liệu API tại `http://localhost/api/docs`.

## Quy tắc bắt buộc

**Bảo mật**
- Không bao giờ đọc, in, ghi log hoặc commit nội dung `.env`. Chỉ sửa `.env.example` (giá trị giả).
- Không đặt secret vào biến `NEXT_PUBLIC_*` hoặc bất kỳ code frontend nào. Frontend không gọi LLM.
- Xác thực bằng cookie `sid` do backend cấp (ADR-0005). Không lưu token trong localStorage.
- Mọi request `POST/PATCH/DELETE` từ frontend gửi header `X-Requested-With: fetch`.
- Truy cập tài nguyên luôn qua dependency kiểm tra chủ sở hữu; không thuộc người dùng → **404**, không phải 403.
- `answer_index` và `explanation` không bao giờ xuất hiện trong `GET /quizzes/{id}`.

**Kiến trúc**
- Frontend chỉ nói chuyện với FastAPI; không truy cập DB, MinIO trực tiếp.
- Tác vụ chậm (PDF, LLM, PPTX) chạy trong Celery worker, không chạy trong request.
- Mọi lời gọi LLM đi qua `LLMClient` trong `app/ai/llm/`; không import SDK nhà cung cấp ở nơi khác.
- Đầu ra LLM luôn validate bằng Pydantic trước khi ghi DB; lỗi → thử lại 1 lần kèm thông báo lỗi.
- Prompt nằm trong `app/ai/prompts/*.j2`, không viết prompt dài inline trong code.
- Task worker phải idempotent: kiểm tra kết quả đã có trước khi chạy lại bước.
- Thay đổi lược đồ → tạo migration Alembic, không sửa migration đã có.

**Tài liệu**
- Thay đổi endpoint → cập nhật `docs/design/api.md`. Thay đổi bảng → cập nhật `docs/design/data-model.md`.
- Quyết định đi ngược một ADR → dừng lại hỏi người dùng; nếu đồng ý thì viết ADR mới theo `docs/adr/template.md`.

## Quy ước code

**Python (3.12)**
- Ruff (lint + format), dòng tối đa 100 ký tự, type hint đầy đủ.
- SQLAlchemy 2.0 style (`Mapped[...]`, `select()`), không dùng API cũ `session.query`.
- Router mỏng, logic trong `services/`.
- Lỗi nghiệp vụ ném `AppError(code, detail, status)`; handler chung trả `{"code", "detail"}` như `docs/design/api.md` mục 1.6.
- Thông điệp lỗi cho người dùng bằng tiếng Việt; log và tên biến bằng tiếng Anh.

**TypeScript**
- `strict: true`, không dùng `any`. Kiểu API lấy từ `src/lib/api-types.ts` (sinh tự động, không sửa tay).
- Gọi API qua `src/lib/api.ts` (fetch wrapper: `credentials: "include"`, header CSRF, parse lỗi).
- Dữ liệu server dùng TanStack Query; không tự viết cache.
- Component UI dùng shadcn/ui + Tailwind; văn bản giao diện tiếng Việt.

## Kiểm thử

- Backend: `pytest` + `httpx.AsyncClient`, DB test riêng. Dùng `FakeLLMClient` – **không gọi LLM thật trong test**.
- Bắt buộc có test cho: kiểm tra quyền sở hữu (404), ẩn đáp án quiz, chấm điểm, validate upload PDF.
- File PDF mẫu trong `backend/tests/fixtures/`.

## Hoàn thành một việc khi

1. `make lint` và `make test` đều qua.
2. Đã chạy thử luồng liên quan trên `http://localhost`.
3. Tài liệu trong `docs/` đã cập nhật nếu API hoặc lược đồ thay đổi.
4. Commit theo Conventional Commits: `feat(api): ...`, `fix(worker): ...`, `docs: ...`.
