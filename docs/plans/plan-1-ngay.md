# Kế hoạch phát triển trong 1 ngày

> Mục tiêu: cuối ngày chạy được trọn luồng **đăng nhập Google → tải PDF → xem tóm tắt, slide, làm quiz → thấy trong thư viện**, bằng `docker compose up` trên máy local.
> Cách làm: một người + Claude Code, khoảng 11 giờ làm việc.

## Nguyên tắc

- **Chạy được trước, đẹp sau.** Mỗi khối kết thúc bằng một thứ chạy thử được trên trình duyệt hoặc `/api/docs`.
- **Commit sau mỗi khối.** Nếu khối sau hỏng, quay lại được ngay.
- **Hết giờ thì cắt phạm vi, không kéo dài.** Xem mục "Cắt bớt khi trễ".
- Mỗi khối mở phiên Claude Code mới (`/clear`), giao việc kèm tài liệu liên quan để giữ ngữ cảnh gọn.

## Phạm vi trong ngày

| Làm hôm nay | Để sau |
|---|---|
| Docker Compose: postgres, redis, minio, api, worker, web | Caddy HTTPS cho production (dev dùng Caddy HTTP) |
| Đăng nhập Google, cookie phiên, `/me`, đăng xuất | Rate limiting |
| Upload PDF, thư viện, đổi tên, xoá | Tìm kiếm `pg_trgm`, sắp xếp, lọc |
| Trích xuất PDF, chia chương | Heuristic tiêu đề nâng cao, gộp/chia chương tinh vi |
| Tóm tắt, slide (web + PPTX), quiz mặc định 10 câu | Sinh thêm quiz 20/30 câu, `by_chapter` |
| Polling trạng thái, hiển thị lỗi | Thử lại (`/retry`), Celery beat dọn dẹp, bảng `llm_calls` |
| Test cho quyền sở hữu và chấm quiz | Test đầy đủ, CI |

## Chuẩn bị trước (tối hôm trước hoặc 30 phút đầu)

- [ ] Cài Docker Desktop, Node 22, Python 3.12, `uv` (hoặc pip), Claude Code.
- [ ] Tạo OAuth Client trên Google Cloud Console (loại *Web application*), thêm redirect URI `http://localhost/api/auth/google/callback`, thêm email của bạn vào *Test users*.
- [ ] Có API key LLM.
- [ ] Giải nén `project-docs.zip` vào thư mục repo, `git init`, `cp .env.example .env`, điền giá trị.
- [ ] Chuẩn bị 3 PDF mẫu: một PDF ngắn (~10 trang), một PDF có mục lục (~50 trang), một PDF scan (để thử lỗi).

## Lịch chi tiết

### Khối 1 · 08:00–09:30 · Nền tảng

- Docker Compose đủ các service, Caddyfile (HTTP, `localhost`), Makefile theo `CLAUDE.md`.
- Backend: FastAPI skeleton, `pydantic-settings`, handler lỗi chung, `GET /api/health`.
- Models SQLAlchemy cho tất cả bảng trong `docs/design/data-model.md` (trừ `llm_calls`), migration Alembic đầu tiên.
- Celery app rỗng + task `ping`.
- Frontend: Next.js + Tailwind + shadcn/ui, `src/lib/api.ts`, trang chủ tĩnh.

**Xong khi:** `make up` → `http://localhost` hiện trang chủ, `http://localhost/api/health` trả `ok`, `make migrate` tạo đủ bảng.

> Gợi ý giao việc: *"Đọc CLAUDE.md, docs/adr/0002, 0006, 0014 và docs/design/data-model.md. Dựng skeleton theo Khối 1 trong docs/plans/plan-1-ngay.md."*

### Khối 2 · 09:30–10:30 · Đăng nhập Google

- Authlib: `/auth/google/login`, `/auth/google/callback`, `/auth/logout`; bảng `sessions`, cookie `sid`.
- Dependency `get_current_user`, middleware kiểm tra header CSRF.
- `GET /me`.
- Frontend: nút đăng nhập, layout có avatar + đăng xuất, chặn trang khi `/me` trả 401.
- Test: `/me` không cookie → 401.

**Xong khi:** đăng nhập bằng Gmail thật, về `/library`, F5 vẫn còn đăng nhập, đăng xuất được.

### Khối 3 · 10:30–12:00 · Upload và thư viện

- Lớp `Storage` (boto3 → MinIO), tự tạo bucket khi khởi động.
- `POST /lectures` (kiểm tra kích thước, `%PDF-`, số trang, mã hoá), `GET /lectures`, `GET/PATCH/DELETE /lectures/{id}`, `GET /lectures/{id}/pdf`.
- Dependency `get_owned_lecture` → 404 nếu không phải chủ.
- Upload xong đẩy task `process_lecture` (tạm thời chỉ đổi trạng thái).
- Frontend: `/library` (lưới thẻ, trạng thái, đổi tên, xoá có xác nhận), `/upload` (react-dropzone).
- Test: người dùng B truy cập bài giảng của A → 404.

**Xong khi:** tải PDF lên, thấy trong thư viện, đổi tên, xoá được; file xuất hiện/biến mất trong MinIO console (`http://localhost:9001`).

### 12:00–12:45 · Nghỉ trưa

### Khối 4 · 12:45–14:15 · Trích xuất PDF + LLM + Tóm tắt

- `ai/pdf.py`: PyMuPDF, chuẩn hoá NFC, đánh dấu `[[trang N]]`, chia chương theo bookmark → fallback chia đều 15 trang; phát hiện PDF scan.
- `ai/llm/`: `LLMClient` + một provider (theo key bạn có) + `FakeLLMClient`.
- Prompt `chapter_summary_v1.j2`, `overview_v1.j2`; generator tóm tắt (song song tối đa `LLM_MAX_CONCURRENCY`), lắp `content_md`.
- `process_lecture`: cập nhật `progress_step`, ghi `chapters`; mỗi chương tóm tắt xong ghi ngay `chapters.summary` (bỏ qua chương đã có), rồi lắp ráp `summaries`; lỗi → `failed` + `error_code`.
- `LLMClient`: thử lại lỗi tạm thời 2 lần (SDK `max_retries`), sửa đầu ra sai 1 lần (ADR-0015).
- `GET /lectures/{id}/summary`; trường `available` trong `Lecture`.
- Frontend: `/lectures/[id]` với tab, polling 3 giây, thanh tiến trình các bước, tab Tóm tắt (react-markdown + KaTeX) và tab PDF gốc.

**Xong khi:** PDF 10 trang ra tóm tắt có tham chiếu trang; PDF scan báo lỗi tiếng Việt.

> Đây là khối rủi ro nhất. Thử với PDF ngắn trước để tiết kiệm thời gian và chi phí gọi LLM.

### Khối 5 · 14:15–15:30 · Slide

- Schema `SlideDeck` (ADR-0011), prompt `slides_v1.j2`. Code sinh slide `title`, `agenda`, `section` và `summary` (từ `learning_objectives`); LLM chỉ sinh 1–3 slide `bullets` mỗi chương từ `chapters.summary`, ghi ngay vào `chapters.slides` (ADR-0015).
- python-pptx: template đơn giản, ghi speaker notes, lưu `slides.pptx` lên MinIO.
- `GET /lectures/{id}/slides`, `GET /lectures/{id}/slides.pptx`.
- Frontend: tab Slide với Reveal.js, nút toàn màn hình, nút tải PPTX.

**Xong khi:** trình chiếu được trên web, mở được file PPTX bằng PowerPoint/LibreOffice/Google Slides.

### Khối 6 · 15:30–17:00 · Quiz

- Schema `Question`, prompt `quiz_v1.j2`, phân bổ câu theo độ dài chương, xáo trộn đáp án.
- Quiz mặc định 10 câu ở cuối `process_lecture`.
- `GET /lectures/{id}/quizzes`, `GET /quizzes/{id}` (ẩn đáp án), `POST /quizzes/{id}/attempts`, `GET /quizzes/{id}/attempts`, `GET /attempts/{id}`.
- Frontend: tab Quiz (danh sách lần làm), trang làm bài (từng câu, thanh tiến độ), trang kết quả (điểm, câu sai, giải thích, số trang).
- Test: response `GET /quizzes/{id}` không chứa `answer_index`; chấm điểm đúng với câu bỏ trống.

**Xong khi:** làm quiz, nộp, thấy điểm và giải thích; lịch sử lưu lại.

### Khối 7 · 17:00–18:00 · Hoàn thiện luồng

- Thông báo lỗi thân thiện ở mọi trang (upload sai file, quá cỡ, xử lý thất bại).
- Trạng thái rỗng (thư viện chưa có bài), skeleton loading.
- Kiểm tra giao diện trên mobile (DevTools).
- Cảnh báo "Nội dung do AI tạo" ở tab Tóm tắt và Quiz.

### Khối 8 · 18:00–19:00 · Kiểm thử tổng và đóng ngày

- Chạy trọn luồng với cả 3 PDF mẫu; ghi lại lỗi vào `docs/known-issues.md`.
- `make lint`, `make test` qua.
- Cập nhật `docs/design/api.md`, `docs/design/data-model.md` nếu có lệch so với code.
- README: cách chạy dự án từ đầu.
- Commit, tag `v0.1.0`.

## Mốc kiểm tra

| Giờ | Phải đạt được | Nếu chưa đạt |
|---|---|---|
| 10:30 | Đăng nhập Google chạy | Tạm dùng đăng nhập giả (`DEV_LOGIN=true`) để không chặn các khối sau, quay lại sửa cuối ngày |
| 12:00 | Upload + thư viện chạy | Bỏ đổi tên, chỉ giữ tạo/xoá |
| 14:15 | Có tóm tắt | Bỏ bước `overview`, chỉ tóm tắt từng chương |
| 15:30 | Có slide | Bỏ xuất PPTX, chỉ xem trên web |
| 17:00 | Có quiz | Bỏ lịch sử làm bài, chỉ chấm điểm và hiện kết quả |

## Cắt bớt khi trễ (theo thứ tự)

1. Khối 7 (hoàn thiện giao diện).
2. Xuất PPTX.
3. Lịch sử làm quiz.
4. Tab PDF gốc.
5. Đổi tên bài giảng.

Không cắt: đăng nhập, kiểm tra quyền sở hữu, ẩn đáp án quiz, validate đầu ra LLM.
