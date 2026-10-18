# PRD – Stugen: Website tạo học liệu từ giáo trình PDF

> Dự án phi thương mại · Phiên bản 2.3 · 19/10/2026
>
> Tài liệu liên quan: [Mô hình dữ liệu](../design/data-model.md) · [Tài liệu API](../design/api.md) · [ADR](../adr/README.md)

## 1. Mô tả

Website cho phép người dùng đăng nhập bằng Gmail, tải lên giáo trình PDF và nhận về:

- **Tóm tắt** nội dung theo chương.
- **Slide** trình chiếu.
- **Quiz** trắc nghiệm để ôn tập.

Mọi bài giảng đã tạo được lưu theo tài khoản để xem lại sau.

## 2. Phạm vi

**Có:**
- Đăng nhập bằng Google.
- Tải lên PDF có lớp văn bản (text-based).
- Sinh tóm tắt, slide, quiz.
- Thư viện bài giảng cá nhân: xem, đổi tên, xoá.

**Không có (có thể bổ sung sau):**
- Đăng nhập bằng phương thức khác.
- PDF dạng ảnh scan (OCR), file Word/PowerPoint.
- Chia sẻ, lớp học, chỉnh sửa nội dung đã sinh.

## 3. Chức năng

### 3.1 Đăng nhập
- Đăng nhập bằng tài khoản Google (OAuth 2.0), chỉ lấy `email`, `name`, `avatar`.
- Lần đầu đăng nhập tự tạo tài khoản.
- Các trang ngoài trang chủ đều yêu cầu đăng nhập.

### 3.2 Tải lên PDF
- Kéo-thả hoặc chọn file `.pdf`, tối đa **20 MB / 200 trang**.
- Xử lý chạy nền; giao diện hiển thị trạng thái: `Đang xử lý` → `Hoàn tất` / `Lỗi`.
- Báo lỗi rõ ràng nếu PDF không trích xuất được văn bản.

### 3.3 Tóm tắt
- Một đoạn tổng quan cho toàn tài liệu.
- Mỗi chương: các ý chính và thuật ngữ quan trọng kèm định nghĩa.
- Có ghi số trang tham chiếu tới PDF gốc.
- Hiển thị dạng Markdown (hỗ trợ công thức toán bằng KaTeX).
- Nội dung sinh ra bằng tiếng Việt (mặc định); thuật ngữ chuyên ngành giữ nguyên gốc kèm giải nghĩa, ví dụ "Primary key (khoá chính)". Áp dụng cho cả slide và quiz.

### 3.4 Slide
- Gồm: slide tiêu đề, mục lục, các slide nội dung theo chương, slide tổng kết.
- Mỗi slide tối đa 6 gạch đầu dòng.
- Xem trực tuyến ở chế độ trình chiếu và tải về dạng **PPTX**.

### 3.5 Quiz
- Câu hỏi trắc nghiệm 4 lựa chọn, mặc định 10 câu (có thể chọn 10 / 20 / 30).
- Mỗi câu có đáp án đúng, giải thích ngắn và số trang tham chiếu.
- Làm bài, nộp bài, xem điểm và danh sách câu sai kèm giải thích.
- Lưu lịch sử điểm các lần làm.

### 3.6 Thư viện bài giảng
- Danh sách bài giảng của tài khoản: tên, ngày tạo, số trang, trạng thái.
- Mỗi bài giảng có các tab: **PDF gốc · Tóm tắt · Slide · Quiz**.
- Đổi tên, xoá (xoá cả file PDF và nội dung đã sinh).
- Người dùng chỉ truy cập được bài giảng của chính mình.

## 4. Yêu cầu phi chức năng

- PDF ~50 trang xử lý xong trong khoảng 2–3 phút.
- Giao diện tiếng Việt, dùng tốt trên cả máy tính và điện thoại.
- File PDF lưu riêng tư; API luôn kiểm tra quyền sở hữu.
- Hiển thị lưu ý: nội dung do AI tạo, nên đối chiếu với giáo trình.
- Hiển thị lưu ý ở trang tải lên: nội dung giáo trình được gửi tới dịch vụ AI bên thứ ba (mặc định DeepSeek, [ADR-0016](../adr/0016-cong-cu-ten-tai-nguyen-deepseek-giay-phep.md)) để xử lý.

## 5. Kiến trúc

```
┌──────────────┐   REST    ┌────────────────┐   Job queue   ┌────────────────┐
│   Frontend   │ ────────► │  Backend API   │ ────────────► │   AI Service   │
│  (Next.js)   │ ◄──────── │   (FastAPI)    │   (Redis)     │ (Python worker)│
└──────────────┘           └───────┬────────┘               └───────┬────────┘
                                   │                                │
                           ┌───────▼────────┐               ┌───────▼────────┐
                           │  PostgreSQL    │◄──────────────│   LLM API      │
                           │  + File storage│               └────────────────┘
                           └────────────────┘
```

### 5.1 Công nghệ

| Thành phần | Công nghệ |
|---|---|
| **Frontend** | Next.js (App Router) + TypeScript, Tailwind CSS + shadcn/ui, TanStack Query, react-markdown + KaTeX, Reveal.js (trình chiếu slide), react-pdf |
| **Backend API** | Python, FastAPI, SQLAlchemy 2.0 + Alembic, Pydantic, Authlib (Google OAuth) |
| **AI Service** | Python worker chạy Celery với Redis; PyMuPDF trích xuất PDF; gọi LLM API; Pydantic để kiểm tra đầu ra JSON; `python-pptx` xuất slide |
| **Cơ sở dữ liệu** | PostgreSQL |
| **Lưu file** | MinIO (tương thích S3) |
| **Triển khai** | Docker Compose + Caddy (reverse proxy, HTTPS) |

### 5.2 Luồng đăng nhập
1. Người dùng bấm "Đăng nhập với Google" → trình duyệt tới `/api/auth/google/login`.
2. Backend (Authlib) thực hiện OAuth Authorization Code + PKCE với Google.
3. Tại callback, backend xác minh `id_token`, tạo hoặc cập nhật `user` theo `google_id`.
4. Backend tạo phiên, đặt cookie `sid` (HttpOnly, Secure, SameSite=Lax), chuyển về `/library`.

Frontend và API chạy cùng domain qua Caddy. Chi tiết: [ADR-0005](../adr/0005-xac-thuc-google-oauth.md).

### 5.3 Pipeline AI
1. Backend lưu PDF, tạo bản ghi `lecture` (`processing`), đẩy job vào hàng đợi.
2. Worker trích xuất văn bản theo trang bằng PyMuPDF, tách chương theo mục lục (bookmark) hoặc tiêu đề; nếu không có thì chia theo số trang.
3. Sinh tóm tắt từng chương (lưu ngay sau mỗi chương) → tổng hợp tóm tắt toàn bài.
4. Từ tóm tắt sinh slide nội dung từng chương (JSON); slide tiêu đề, mục lục, mở chương, tổng kết do code tạo → tạo file PPTX.
5. Sinh câu hỏi quiz theo từng chương (JSON).
6. Đầu ra LLM luôn được kiểm tra bằng Pydantic; chính sách thử lại khi lỗi mạng hoặc sai định dạng xem [ADR-0015](../adr/0015-lam-ro-pipeline-llm.md).
7. Lưu kết quả, cập nhật `lecture` thành `completed` hoặc `failed`.

Chạy lại một bài giảng lỗi không gọi lại LLM cho các chương đã xong.

## 6. Dữ liệu

Các thực thể chính: `users`, `sessions`, `lectures`, `chapters`, `summaries`, `slide_decks`, `quizzes`, `questions`, `quiz_attempts`.

Chi tiết lược đồ, ràng buộc, cấu trúc JSONB và DDL: [data-model.md](../design/data-model.md).

## 7. API

REST API dưới tiền tố `/api`, xác thực bằng cookie phiên. Nhóm endpoint chính:

| Nhóm | Endpoint |
|---|---|
| Xác thực | `/auth/google/login`, `/auth/google/callback`, `/auth/logout`, `/me` |
| Bài giảng | `/lectures`, `/lectures/{id}`, `/lectures/{id}/retry`, `/lectures/{id}/pdf` |
| Nội dung | `/lectures/{id}/summary`, `/lectures/{id}/slides`, `/lectures/{id}/slides.pptx` |
| Quiz | `/lectures/{id}/quizzes`, `/quizzes/{id}`, `/quizzes/{id}/attempts`, `/attempts/{id}` |

Chi tiết request/response và mã lỗi: [api.md](../design/api.md).

## 8. Màn hình

1. **Trang chủ** – giới thiệu ngắn, nút "Đăng nhập với Google".
2. **Thư viện** – danh sách bài giảng, nút "Tải giáo trình mới".
3. **Tải lên** – vùng kéo-thả PDF, trạng thái xử lý.
4. **Bài giảng** – các tab PDF gốc / Tóm tắt / Slide / Quiz.
5. **Làm quiz** – từng câu hỏi, nút nộp bài.
6. **Kết quả** – điểm, câu sai kèm giải thích.

## 9. Kế hoạch thực hiện

| Bước | Nội dung |
|---|---|
| 1 | Dựng Docker Compose, FastAPI, PostgreSQL, đăng nhập Google |
| 2 | Tải PDF, trích xuất văn bản, hàng đợi xử lý |
| 3 | Sinh tóm tắt + giao diện xem tóm tắt |
| 4 | Sinh slide + trình chiếu + xuất PPTX |
| 5 | Sinh quiz + làm bài + lịch sử điểm |
| 6 | Hoàn thiện thư viện, xử lý lỗi, kiểm thử |

## 10. Tiêu chí hoàn thành

- [ ] Đăng nhập bằng Google hoạt động.
- [ ] Tải PDF lên và nhận đủ tóm tắt, slide, quiz.
- [ ] Xem slide trình chiếu và tải được PPTX.
- [ ] Làm quiz, chấm điểm đúng, có giải thích.
- [ ] Thư viện chỉ hiển thị bài giảng của đúng tài khoản.
- [ ] Xoá bài giảng xoá toàn bộ dữ liệu liên quan.
