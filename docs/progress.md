# Tiến độ dự án Stugen

> **Đọc file này đầu tiên khi mở phiên mới.** Cập nhật ngay sau mỗi việc hoàn thành (mục 2, 3, 6) và trước khi kết thúc phiên.
> Cập nhật lần cuối: 19/10/2026 · Commit gần nhất: `bc4df4e`

## 1. Trạng thái hiện tại

| Hạng mục | Trạng thái |
|---|---|
| Tài liệu thiết kế (PRD, ADR, data model, API) | ✅ Xong, đã thống nhất (ADR-0015) |
| Chuẩn bị môi trường (`.env`, Google OAuth, LLM key, PDF mẫu) | ✅ Xong |
| Code (Khối 1–8 trong [kế hoạch](plans/plan-1-ngay.md)) | ⏳ Chưa bắt đầu – **việc tiếp theo: Khối 1** |

- Repo: `D:\Stugen` · GitHub: https://github.com/martlnz/Stugen (**private**), nhánh `main`.
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

## 3. Việc tiếp theo

**Khối 1 · Nền tảng** (xem [plan-1-ngay.md](plans/plan-1-ngay.md)). Trước khi làm, xử lý 2 vấn đề môi trường ở mục 5.

- [ ] Quyết định cách chạy lệnh thay `make` trên Windows (mục 5.1)
- [ ] `docker-compose.yml` (proxy, web, api, worker, postgres, redis, minio), `Caddyfile` HTTP `localhost`
- [ ] Backend: FastAPI skeleton, `pydantic-settings` (đọc cả `CONTENT_LANGUAGE`), handler lỗi `AppError`, `GET /api/health`; `openapi_url=/api/openapi.json`, `docs_url=/api/docs`
- [ ] Models SQLAlchemy theo `docs/design/data-model.md` v1.1 (trừ `llm_calls`; nhớ 2 cột `chapters.summary`, `chapters.slides`), migration Alembic đầu tiên
- [ ] Celery app + task `ping`
- [ ] Frontend: Next.js + Tailwind + shadcn/ui, `src/lib/api.ts`, trang chủ tĩnh
- [ ] Kiểm tra: `http://localhost` ra trang chủ, `/api/health` trả `ok`, migrate tạo đủ bảng

## 4. Môi trường

| Thành phần | Trạng thái |
|---|---|
| `.env` | ✅ Đủ. `SESSION_SECRET`, mật khẩu Postgres/MinIO sinh ngẫu nhiên; `DATABASE_URL*` khớp mật khẩu; Google ID/secret và `LLM_API_KEY` đúng định dạng |
| LLM | `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL=https://api.deepseek.com`, `LLM_MODEL=deepseek-v4-pro`, `LLM_MODEL_FAST=deepseek-v4-flash` |
| Google OAuth | Client "Stugen local", Testing mode, email chủ dự án trong Test users |
| Docker | 29.8.2, Compose v5.6.0 ✅ |
| Node | 24.21.0 (Dockerfile frontend vẫn dùng Node 22 theo ADR-0014) |
| uv | 0.12.5 ✅ |
| Python | Máy có 3.14; **chưa có 3.12** (mục 5.2) |
| make | ❌ **Chưa có** (mục 5.1) |

**Quy tắc với `.env`:** không đọc/in giá trị (chỉ kiểm tra đúng/sai). Sửa bằng `notepad D:/Stugen/.env` rồi **Ctrl+S** – Notepad Windows 11 giữ nội dung trong tab mà không ghi file nếu chưa lưu; tab mở từ trước có thể ghi đè bản mới. Nếu mật khẩu bị ghi đè về `change-me`: sinh lại bằng script tạm (đã mất khi đổi phiên) hoặc nhờ Claude viết lại script ghi thẳng vào `.env` không in ra.

**PDF mẫu** (`samples/`, tạo lại bằng `pip install pymupdf` rồi `python scripts/make_sample_pdfs.py`):

| File | Đặc điểm | Thử |
|---|---|---|
| `short-10p.pdf` | 10 trang, không bookmark, tiêu đề "Chương N." cỡ lớn, có LaTeX inline | Chia chương theo heuristic tiêu đề, KaTeX |
| `toc-50p.pdf` | 51 trang, 7 chương, 9 bookmark, header + footer "Trang N" | Chia theo bookmark, lọc header/footer |
| `scan.pdf` | 10 trang ảnh, 0 ký tự | Lỗi `PDF_NO_TEXT` |

## 5. Vấn đề mở

### 5.1 Không có `make` trên Windows
`CLAUDE.md` dùng `make up/test/lint/...`. Phương án (chưa chọn):
- Cài GNU Make: `winget install ezwinports.make` – giữ nguyên `CLAUDE.md`. **Đề xuất.**
- Hoặc dùng `just` / script `tasks.ps1` – phải sửa `CLAUDE.md` và README.

### 5.2 Chưa có Python 3.12
Backend chạy trong Docker nên không bắt buộc. Để chạy `pytest`/`ruff` ngoài container: `uv python install 3.12` rồi tạo venv `backend/.venv` bằng uv.

### 5.3 Lưu ý khi làm Khối 4 (trích xuất PDF + LLM)
- Văn bản trích từ PDF mẫu **không ở dạng NFC** → bắt buộc chuẩn hoá NFC (ADR-0009).
- Header trích ra chứa **NBSP (`\xa0`)** → đổi về dấu cách trước khi so khớp dòng lặp.
- Footer "Trang N" khác nhau mỗi trang → quy tắc "dòng giống nhau ≥ 50% trang" không bắt được; **thay chữ số bằng ký tự đại diện** trước khi đếm.
- **DeepSeek:** chỉ hỗ trợ `response_format={"type": "json_object"}` (không có `json_schema`) → prompt phải chứa chữ "json" + ví dụ JSON mẫu; có thể trả nội dung rỗng → coi là đầu ra sai (sửa 1 lần); đặt `max_tokens` 4–8K; tắt chế độ thinking; timeout ~120 giây. Thiết kế provider có cờ hỗ trợ `json_schema` hay không.
- Kiểm tra lại tên model DeepSeek trên api-docs.deepseek.com (thông tin `deepseek-v4-*` lấy từ nguồn thứ ba).

## 6. Quyết định đang chờ chủ dự án

- [ ] Repo private hay public? Giấy phép (gợi ý **AGPL-3.0** vì PyMuPDF là AGPL)
- [ ] Có cập nhật tài liệu cho DeepSeek không: ví dụ cấu hình trong `.env.example`, README, câu lưu ý "nội dung được xử lý bởi dịch vụ AI bên thứ ba" trong PRD mục 4, quy tắc `json_object` trong `CLAUDE.md`
- [ ] Cách thay `make` (mục 5.1)
- [ ] Đổi tên mặc định DB `app` / bucket `lectures` thành `stugen`?
- [ ] Domain/VPS triển khai thật; ngày bắt đầu chạy kế hoạch; có thêm người đóng góp không
