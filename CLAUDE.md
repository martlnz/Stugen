# CLAUDE.md

Hướng dẫn cho Claude Code khi làm việc trong repository này.

## Dự án

**Stugen** – website phi thương mại: đăng nhập bằng Google, tải giáo trình PDF, sinh **tóm tắt**, **slide**, **quiz**; lưu bài giảng theo tài khoản.

**Bắt đầu mỗi phiên: đọc `docs/progress.md`** – trạng thái hiện tại, việc tiếp theo, vấn đề mở.

Tài liệu nguồn (đọc trước khi làm tính năng liên quan):
- `docs/product/PRD.md` – yêu cầu và phạm vi
- `docs/adr/` – quyết định kiến trúc (0001–0017)
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
                     (beat: thêm khi làm cleanup_orphans – ADR-0014)
Caddyfile
justfile             lệnh phát triển (just, ADR-0016)
```

## Lệnh

```bash
just up          # docker compose up -d --build
just down
just logs        # docker compose logs -f api worker
just migrate     # alembic upgrade head
just revision "mô tả"    # alembic revision --autogenerate
just test        # pytest backend (trong container api)
just lint        # ruff check + ruff format --check (trong container api) + (frontend) eslint, tsc
just fmt         # ruff format + prettier
just gen-api     # = cd frontend && npm run gen:api → openapi-typescript http://localhost/api/openapi.json
                 #   -o src/lib/api-types.ts (FastAPI: openapi_url=/api/openapi.json, docs_url=/api/docs)
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
- Đầu ra LLM luôn validate bằng Pydantic trước khi ghi DB; sai định dạng → sửa 1 lần kèm thông báo lỗi (ADR-0015).
- Lỗi tạm thời của LLM (timeout, 429, 5xx) → thử lại 2 lần có backoff ngay trong `LLMClient`; Celery chỉ retry task cho lỗi hạ tầng (DB, Redis, MinIO).
- Học liệu sinh theo **bài nhỏ** người dùng chọn (ADR-0017): tải lên chỉ tách mục lục chương → bài; `generate_lesson` tạo tóm tắt → slide → quiz cho từng bài.
- Code sinh slide `title`, `agenda`, `summary` (Ghi nhớ); LLM sinh slide nội dung từ văn bản gốc của bài (có `explanation`, `example`). LLM không trả số trang chương/bài; số trang mục nhỏ do code kẹp vào khoảng bài.
- Prompt nằm trong `app/ai/prompts/*.j2`, không viết prompt dài inline trong code.
- LLM mặc định là DeepSeek qua provider `openai_compatible` (ADR-0016). Provider có cờ `supports_json_schema`; khi cờ tắt thì dùng `response_format={"type": "json_object"}`, prompt chứa chữ "json" và ví dụ JSON sinh từ schema. `content` rỗng tính là đầu ra sai định dạng. Tắt thinking (`extra_body={"thinking": {"type": "disabled"}}`), `max_tokens` 4–8K, timeout ~120 giây.
- Task worker phải idempotent: kiểm tra kết quả đã có trước khi chạy lại bước. Kết quả LLM từng bài ghi ngay vào `lessons.summary` / `lessons.slides`; bài đã có giá trị thì bỏ qua bước đó.
- Prompt sinh nội dung theo `CONTENT_LANGUAGE` (mặc định `vi`: tiếng Việt, thuật ngữ giữ nguyên gốc kèm giải nghĩa). Tóm tắt và quiz chỉ dùng thông tin giáo trình; riêng slide được tạo ví dụ minh hoạ có nhãn.
- Giới hạn hiển thị (độ dài, số phần tử) do schema cắt gọn bằng code, không bắt LLM đếm ký tự.
- Thay đổi lược đồ → tạo migration Alembic, không sửa migration đã có.

**Tài liệu**
- Xong một việc (hoặc trước khi kết thúc phiên) → cập nhật `docs/progress.md`: nhật ký, việc tiếp theo, vấn đề mở, commit gần nhất.
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
- Bắt buộc có test cho: kiểm tra quyền sở hữu (404, cả bài giảng và bài học), ẩn đáp án quiz, chấm điểm, validate upload PDF.
- Kiểm tra giao diện: Playwright + Chromium headless cài tạm ngoài repo, cookie `sid` lấy từ `just session`.
- File PDF mẫu trong `backend/tests/fixtures/`.

## Hoàn thành một việc khi

1. `just lint` và `just test` đều qua.
2. Đã chạy thử luồng liên quan trên `http://localhost`.
3. Tài liệu trong `docs/` đã cập nhật nếu API hoặc lược đồ thay đổi; `docs/progress.md` đã ghi lại việc vừa làm.
4. Commit theo Conventional Commits: `feat(api): ...`, `fix(worker): ...`, `docs: ...`.
