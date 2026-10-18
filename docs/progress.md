# Tiến độ dự án Stugen

> **Đọc file này đầu tiên khi mở phiên mới.** Cập nhật ngay sau mỗi việc hoàn thành (mục 2, 3, 6) và trước khi kết thúc phiên.
> Cập nhật lần cuối: 19/10/2026 · Commit gần nhất: xem `git log --oneline -5`

## 1. Trạng thái hiện tại

| Hạng mục | Trạng thái |
|---|---|
| Tài liệu thiết kế (PRD, ADR, data model, API) | ✅ Xong, đã thống nhất (ADR-0015, ADR-0016) |
| Chuẩn bị môi trường (`.env`, Google OAuth, LLM key, PDF mẫu, image Docker) | ✅ Xong (kiểm tra lại 19/10) |
| Code (Khối 1–8 trong [kế hoạch](plans/plan-1-ngay.md)) | ⏳ Chưa bắt đầu – **việc tiếp theo: Khối 1** |

- Repo: `D:\Stugen` · GitHub: https://github.com/martlnz/Stugen (**public**, AGPL-3.0), nhánh `main`.
- Mở phiên Claude Code mới **trong thư mục `D:\Stugen`**.

## 2. Nhật ký công việc

### 18–19/10/2026 · Phiên 1 – Dựng repo, chốt tài liệu, chuẩn bị môi trường
- Tạo repo `Stugen` từ bộ tài liệu gốc; sắp xếp lại `docs/` thành `product/`, `design/`, `adr/`, `plans/`; sửa toàn bộ link; viết README. (`10e07ee`)
- Rà soát tài liệu, chốt 8 điểm lệch → **ADR-0015**; PRD lên 2.2, data-model lên 1.1. (`a493baa`) Tóm tắt quyết định:
  1. Lỗi LLM tạm thời (timeout/429/5xx) → thử lại 2 lần trong `LLMClient`; đầu ra sai schema → sửa 1 lần kèm lỗi Pydantic; Celery chỉ retry lỗi hạ tầng.
  2. Code sinh slide `title`, `agenda`, `section`, `summary`; LLM chỉ sinh slide `bullets` từng chương.
  3. `data-model.md` là nguồn chuẩn lược đồ (bảng "Nguồn chuẩn" trong `docs/adr/README.md`).
  4. LLM không trả số trang chương; code ghép `page_start/page_end`.
  5. `CONTENT_LANGUAGE=vi`: tiếng Việt, thuật ngữ giữ gốc kèm giải nghĩa.
  6. `beat` chưa chạy ở v0.1.
  7. Kết quả từng chương lưu `chapters.summary` / `chapters.slides` (idempotent).
  8. Lệnh sinh kiểu TS thống nhất: `make gen-api`.
- Tạo `.env` (không commit). Đã kiểm tra đủ biến – xem mục 4.
- Tạo Google OAuth Client (Testing mode, redirect `http://localhost/api/auth/google/callback`).
- Chọn LLM **DeepSeek** qua provider `openai_compatible`.
- Viết `scripts/make_sample_pdfs.py`, sinh 3 PDF mẫu vào `samples/` (git-ignored). (`bc4df4e`)

### 19/10/2026 · Phiên 2 – Chốt quyết định còn chờ → ADR-0016
- Chạy lệnh bằng **`just`** thay `make`; `just test`/`just lint` backend chạy trong container `api` nên máy không cần Python 3.12.
- Đổi tên user/database PostgreSQL và bucket MinIO thành **`stugen`**.
- DeepSeek là LLM mặc định; đã xác minh trên api-docs.deepseek.com: model `deepseek-v4-pro` và `deepseek-flash` (`deepseek-v4-flash` đã ngừng); chỉ có `json_object`; tắt thinking bằng `extra_body={"thinking": {"type": "disabled"}}`.
- Cập nhật `CLAUDE.md`, README, `.env.example`, PRD 2.3 (lưu ý dịch vụ AI bên thứ ba), data-model 1.2 (bucket), api.md, plan, ADR README; trạng thái ADR-0003/0007/0010.
- Thêm `LICENSE` (AGPL-3.0); repo GitHub chuyển public. (`132d369`)
- Kiểm tra `.env` trong container (chỉ in đúng/sai): mọi biến đạt, trừ đuôi DB trong `DATABASE_URL*` vẫn là `/app`.
- DeepSeek: key hoạt động, số dư ~4.94 USD; `/models` có `deepseek-flash`, `deepseek-v4-pro`. Gọi thử `json_object` + `thinking: disabled` trả JSON hợp lệ ở cả 2 model, nhưng **trả tiếng Anh dù system prompt tiếng Việt** → prompt phải ghi rõ "trả lời bằng tiếng Việt".
- **MinIO đã ngừng phát hành image miễn phí** (`minio/minio` trên Docker Hub và Quay không còn kéo được). Dùng `cgr.dev/chainguard/minio` và `cgr.dev/chainguard/minio-client` (miễn phí, bản RELEASE.2026-09-22; chỉ có tag `latest`; chạy với user 65532, entrypoint `/usr/bin/minio`). Vẫn là MinIO nên không trái ADR-0007.
- Kéo sẵn image: `postgres:16-alpine`, `redis:7-alpine`, `caddy:2-alpine`, `python:3.12-slim`, `node:22-alpine`, MinIO Chainguard. Cổng 80, 5432, 6379, 9000, 9001 trống.
- Không có Claude in Chrome: kiểm thử luồng cần đăng nhập bằng cách tạo user + session trong DB local qua script dev (`docker exec`); chủ dự án tự đăng nhập Google thật một lần để xác nhận OAuth.

## 3. Việc tiếp theo

**Khối 1 · Nền tảng** (xem [plan-1-ngay.md](plans/plan-1-ngay.md)). Trước khi làm, chủ dự án sửa `.env` (mục 5.1).

- [ ] `justfile` (PowerShell trên Windows; `test`/`lint` backend chạy trong container `api`)
- [ ] `docker-compose.yml` (proxy, web, api, worker, postgres, redis, minio), `Caddyfile` HTTP `localhost`
- [ ] Backend: FastAPI skeleton, `pydantic-settings` (đọc cả `CONTENT_LANGUAGE`), handler lỗi `AppError`, `GET /api/health`; `openapi_url=/api/openapi.json`, `docs_url=/api/docs`
- [ ] Models SQLAlchemy theo `docs/design/data-model.md` v1.2 (trừ `llm_calls`; nhớ 2 cột `chapters.summary`, `chapters.slides`), migration Alembic đầu tiên
- [ ] Celery app + task `ping`
- [ ] Frontend: Next.js + Tailwind + shadcn/ui, `src/lib/api.ts`, trang chủ tĩnh
- [ ] Kiểm tra: `http://localhost` ra trang chủ, `/api/health` trả `ok`, migrate tạo đủ bảng

## 4. Môi trường

| Thành phần | Trạng thái |
|---|---|
| `.env` | ✅ Đủ. `SESSION_SECRET`, mật khẩu Postgres/MinIO sinh ngẫu nhiên; `DATABASE_URL*` khớp mật khẩu; Google ID/secret và `LLM_API_KEY` đúng định dạng |
| LLM | `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL=https://api.deepseek.com`, `LLM_MODEL=deepseek-v4-pro`, `LLM_MODEL_FAST=deepseek-flash` (cần sửa trong `.env`, mục 5.1) |
| Google OAuth | Client "Stugen local", Testing mode, email chủ dự án trong Test users |
| Docker | 29.8.2, Compose v5.6.0 ✅ |
| Node | 24.21.0 (Dockerfile frontend vẫn dùng Node 22 theo ADR-0014) |
| uv | 0.12.5 ✅ |
| Python | Máy có 3.13, 3.14; không cần 3.12 (test chạy trong container, ADR-0016) |
| just | ✅ Đã cài (winget `Casey.Just`) |

**Quy tắc với `.env`:** không đọc/in giá trị (chỉ kiểm tra đúng/sai). Sửa bằng `notepad D:/Stugen/.env` rồi **Ctrl+S** – Notepad Windows 11 giữ nội dung trong tab mà không ghi file nếu chưa lưu; tab mở từ trước có thể ghi đè bản mới. Nếu mật khẩu bị ghi đè về `change-me`: sinh lại bằng script tạm (đã mất khi đổi phiên) hoặc nhờ Claude viết lại script ghi thẳng vào `.env` không in ra.

**PDF mẫu** (`samples/`, tạo lại bằng `pip install pymupdf` rồi `python scripts/make_sample_pdfs.py`):

| File | Đặc điểm | Thử |
|---|---|---|
| `short-10p.pdf` | 10 trang, không bookmark, tiêu đề "Chương N." cỡ lớn, có LaTeX inline | Chia chương theo heuristic tiêu đề, KaTeX |
| `toc-50p.pdf` | 51 trang, 7 chương, 9 bookmark, header + footer "Trang N" | Chia theo bookmark, lọc header/footer |
| `scan.pdf` | 10 trang ảnh, 0 ký tự | Lỗi `PDF_NO_TEXT` |

## 5. Vấn đề mở

### 5.1 Sửa `.env` theo ADR-0016 (chủ dự án tự làm, Claude không đọc `.env`)
Mở `notepad D:/Stugen/.env`, sửa rồi **Ctrl+S**:
- `POSTGRES_USER=stugen`, `POSTGRES_DB=stugen`; trong `DATABASE_URL` và `DATABASE_URL_SYNC` đổi `app:` → `stugen:` và `/app` cuối → `/stugen` (giữ nguyên mật khẩu).
- `S3_BUCKET=stugen`
- `LLM_MODEL_FAST=deepseek-flash`

Trạng thái 19/10: ✅ đã sửa xong và kiểm tra lại trong container.

Chưa có volume Postgres nên đổi tên lúc này không mất dữ liệu.

### 5.2 Lưu ý khi làm Khối 4 (trích xuất PDF + LLM)
- Văn bản trích từ PDF mẫu **không ở dạng NFC** → bắt buộc chuẩn hoá NFC (ADR-0009).
- Header trích ra chứa **NBSP (`\xa0`)** → đổi về dấu cách trước khi so khớp dòng lặp.
- Footer "Trang N" khác nhau mỗi trang → quy tắc "dòng giống nhau ≥ 50% trang" không bắt được; **thay chữ số bằng ký tự đại diện** trước khi đếm.
- **DeepSeek:** quy tắc đã chốt trong ADR-0016 (ghi chú triển khai) và `CLAUDE.md`.

## 6. Quyết định đang chờ chủ dự án

- [x] Repo public, giấy phép AGPL-3.0 (ADR-0016)
- [x] Cập nhật tài liệu cho DeepSeek (ADR-0016)
- [x] Dùng `just` thay `make` (ADR-0016)
- [x] Đổi tên DB/bucket thành `stugen` (ADR-0016)
- [ ] Domain/VPS triển khai thật; có thêm người đóng góp không
