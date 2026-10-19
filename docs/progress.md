# Tiến độ dự án Stugen

> **Đọc file này đầu tiên khi mở phiên mới.** Cập nhật ngay sau mỗi việc hoàn thành (mục 2, 3, 6) và trước khi kết thúc phiên.
> Cập nhật lần cuối: 19/10/2026 (v0.2.0) · Commit gần nhất: xem `git log --oneline -5`

## 1. Trạng thái hiện tại

| Hạng mục | Trạng thái |
|---|---|
| Tài liệu thiết kế (PRD, ADR, data model, API) | ✅ PRD 2.4, ADR 0001–0017, data-model 1.3, api.md 2.0 |
| Chuẩn bị môi trường (`.env`, Google OAuth, LLM key, PDF mẫu, image Docker) | ✅ Xong (kiểm tra lại 19/10) |
| Code | ✅ v0.2.0 – giáo trình tách thành bài nhỏ, chọn bài để tạo học liệu (ADR-0017); hạn chế: [known-issues.md](known-issues.md) |
| Đăng nhập Google thật | ⏳ Chờ chủ dự án bấm thử một lần (mục 3) |

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

### 19/10/2026 · Phiên 3 – Code Khối 1–8, phát hành v0.1.0
- **Khối 1:** `docker-compose.yml` (+ `override` dev mount source, uvicorn `--reload`), `Caddyfile` HTTP, `justfile`; FastAPI skeleton (`AppError`, CSRF `X-Requested-With`, `/api/health`), models + migration đầu tiên (có `pg_trgm`), Celery `ping`; Next.js **16.4** + shadcn/ui (bản **Base UI**, dùng prop `render` thay `asChild`), `src/lib/api.ts`.
- **Khối 2:** Authlib + PKCE, bảng `sessions` (SHA-256, sliding 7 ngày), cookie `sid`, `/me`, logout; state OAuth trong cookie ký `oauth_state`.
- **Khối 3:** `Storage` (boto3 → MinIO, tự tạo bucket), upload kiểm tra kích thước/`%PDF-`/mã hoá/số trang, thư viện, đổi tên, xoá, `/pdf` có `Range`.
- **Khối 4–6:** `ai/pdf.py` (NFC, bỏ NBSP, lọc header/footer thay chữ số bằng ký tự đại diện, chia chương bookmark → heuristic tiêu đề → chia đều; cắt theo **dòng** khi hai chương cùng trang), `LLMClient` `openai_compatible` (json_object + ví dụ JSON sinh từ schema, tắt thinking, sửa 1 lần), `FakeLLMClient`, prompt `*_v1.j2`, pipeline idempotent theo chương, PPTX, quiz (phân bổ theo độ dài, xáo đáp án), API summary/slides/quiz/attempts.
- **Khối 7:** UI thư viện, tải lên (cảnh báo dịch vụ AI bên thứ ba), trang bài giảng (tiến trình, thử lại, tab Tóm tắt/Slide/Quiz/PDF), làm quiz, kết quả; trạng thái rỗng, skeleton, cảnh báo "Nội dung do AI tạo".
- **Khối 8:** 43 test pytest qua; `just lint` sạch; chạy trọn luồng với 3 PDF mẫu bằng DeepSeek thật và Chromium headless (Playwright cài tạm ngoài repo) – xem [known-issues.md](known-issues.md). Cập nhật README, api.md 1.1, data-model (ghi chú `llm_calls`), `.env.example`.
- **Quyết định trong phiên (không trái ADR):**
  - DeepSeek vượt giới hạn độ dài (bullet 120 ký tự, ≤ 10 thuật ngữ) và sửa lại vẫn sai → schema LLM **cắt gọn bằng code** thay vì báo lỗi; lỗi cấu trúc/trang vẫn sửa 1 lần (ADR-0015).
  - `AttemptResult` thêm `lecture_id`, `lecture_title`; `QuizSummary.error.code = QUIZ_FAILED` (api.md 1.1).
  - Dev chạy uvicorn `--reload` (override); `Dockerfile` backend vẫn dùng gunicorn cho production.
  - `.gitattributes` ép LF (file chạy trong container).
  - Script dev `backend/scripts/dev_session.py` / `just session` tạo phiên đăng nhập local (không thêm endpoint đăng nhập giả).

### 19/10/2026 · Phiên 4 – Phản hồi v0.1 → v0.2.0 (ADR-0017)
- **Phản hồi chủ dự án:** (1) muốn chọn phạm vi, tách giáo trình thành bài nhỏ, mỗi bài có quiz riêng; (2) tóm tắt không được có tên file; (3) tên slide theo nội dung kiến thức; (4) mục lục ghi rõ ý nhỏ kèm khoảng trang; (5) slide phải giải thích dễ hiểu, có ví dụ.
- **Nguyên nhân gốc:** đơn vị xử lý là chương lớn, chạy hết ngay khi tải lên, mỗi chương ≤ 8 ý, quiz 10 câu cho cả giáo trình (quiz còn cắt văn bản > 30.000 ký tự); slide sinh từ bản tóm tắt (ADR-0015) nên không có chất liệu giải thích/ví dụ; tên lấy từ metadata/tên file.
- **Chốt với chủ dự án:** luồng "chọn bài rồi mới tạo"; quiz mỗi bài theo độ dài (≈ 1,5 câu/trang, 5–15); slide được dùng ví dụ do AI tạo có nhãn; nút "Tạo lại nội dung" cho bài giảng cũ → **ADR-0017**.
- **Backend:** migration `lessons` + `quizzes.lesson_id/lesson_ids` (num_questions 1–30); `extract_outline` tách bài theo bookmark cấp 2 → tiêu đề phụ (cỡ chữ/đánh số) → LLM (`outline_v1.j2`, mô hình nhanh, chỉ gửi vài dòng đầu mỗi trang) → chia đều; `generate_lesson`: tóm tắt theo mục (code kẹp trang, đổi tên bài mơ hồ theo `title` LLM), slide từ văn bản gốc (`explanation`, `example`), PPTX theo bài, quiz mặc định rải đều mục; API outline / lessons/generate / lessons/{id}/* / quiz tổng hợp / regenerate. 51 test.
- **Frontend:** trang bài giảng 2 cột (mục lục chương → bài → mục nhỏ kèm trang, checkbox, nút tạo; bài đang chọn với tab Tóm tắt/Slide/Quiz/PDF + Quiz tổng hợp), slide có khung "Ví dụ minh hoạ", banner tạo lại, thư viện hiển thị số bài đã tạo.
- **Chạy thật:** `toc-50p.pdf` → 30 bài trong ~4 giây; mỗi bài 3–4 trang ~40 giây (DeepSeek); Playwright headless desktop + mobile không lỗi console.

## 3. Việc tiếp theo

**Chủ dự án**
- [ ] Mở <http://localhost>, bấm "Đăng nhập với Google" bằng Gmail trong *Test users* → về `/library`, F5 vẫn đăng nhập, đăng xuất được. Báo lại nếu lỗi (xem `just logs`).
- [ ] Thử luồng v0.2 với một giáo trình thật: tải lên → chọn vài bài → xem tóm tắt/slide/quiz; góp ý cách tách bài (bài quá dài/ngắn, tên bài).

**Sau v0.1.0** (theo "Để sau" trong [kế hoạch](plans/plan-1-ngay.md) và [known-issues.md](known-issues.md))
- [ ] Giới hạn tần suất (api.md 1.7).
- [ ] Celery beat + `cleanup_orphans` (ADR-0014): dọn phiên hết hạn, file MinIO mồ côi.
- [ ] Bảng `llm_calls` (migration mới) để theo dõi chi phí.
- [ ] Ô tìm kiếm/lọc/sắp xếp ở thư viện (API đã hỗ trợ).
- [ ] Nhận tiêu đề phụ in đậm cùng cỡ chữ; cho phép người dùng gộp/tách bài thủ công.
- [ ] CI (GitHub Actions: ruff, pytest, eslint, tsc).
- [ ] Triển khai thật: domain/VPS, Caddy HTTPS (`{$DOMAIN}`), sao lưu.

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

### 5.2 Ghi chú pipeline (đã áp dụng trong code v0.1.0)
- Văn bản trích từ PDF mẫu **không ở dạng NFC** → bắt buộc chuẩn hoá NFC (ADR-0009).
- Header trích ra chứa **NBSP (`\xa0`)** → đổi về dấu cách trước khi so khớp dòng lặp.
- Footer "Trang N" khác nhau mỗi trang → quy tắc "dòng giống nhau ≥ 50% trang" không bắt được; **thay chữ số bằng ký tự đại diện** trước khi đếm.
- **DeepSeek:** quy tắc đã chốt trong ADR-0016 (ghi chú triển khai) và `CLAUDE.md`. Giới hạn độ dài hiển thị do code cắt (xem nhật ký phiên 3).

### 5.3 Docker Desktop sập khi build frontend
`docker compose build web` hai lần làm WSL engine dừng (`exit status 0xc00000fd`). Đã giới hạn heap Node khi build. Nếu gặp lại: thoát Docker Desktop, `wsl --shutdown`, mở lại rồi `just up`.

## 6. Quyết định đang chờ chủ dự án

- [x] Repo public, giấy phép AGPL-3.0 (ADR-0016)
- [x] Cập nhật tài liệu cho DeepSeek (ADR-0016)
- [x] Dùng `just` thay `make` (ADR-0016)
- [x] Đổi tên DB/bucket thành `stugen` (ADR-0016)
- [ ] Domain/VPS triển khai thật; có thêm người đóng góp không
