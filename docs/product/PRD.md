# PRD – Stugen: Website tạo học liệu từ giáo trình PDF

> Dự án phi thương mại · Phiên bản 2.5 · 20/10/2026
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
- Chia sẻ, lớp học, chỉnh sửa tóm tắt và slide đã sinh.

## 3. Chức năng

### 3.1 Đăng nhập
- Đăng nhập bằng tài khoản Google (OAuth 2.0), chỉ lấy `email`, `name`, `avatar`.
- Lần đầu đăng nhập tự tạo tài khoản.
- Các trang ngoài trang chủ đều yêu cầu đăng nhập.

### 3.2 Tải lên PDF và chọn bài
- Kéo-thả hoặc chọn file `.pdf`, tối đa **20 MB / 200 trang**.
- Sau vài giây, giáo trình được tách thành **chương → bài nhỏ** (mỗi bài khoảng 2–8 trang) kèm khoảng trang, theo mục lục (bookmark), tiêu đề trong PDF hoặc do AI đề xuất ([ADR-0017](../adr/0017-bai-nho-chon-pham-vi-slide-tu-van-ban-goc.md)).
- Người dùng **chọn các bài cần học** (cả chương hoặc từng bài) rồi bấm "Tạo học liệu"; AI chỉ xử lý các bài đã chọn. Có thể tạo thêm bài khác sau.
- Giao diện hiển thị trạng thái từng bài: `Chưa tạo` → `Đang tạo` (tóm tắt / slide / quiz) → `Đã tạo` / `Lỗi` (chọn lại để tạo lại).
- Báo lỗi rõ ràng nếu PDF không trích xuất được văn bản.

### 3.3 Tóm tắt (theo bài)
- Tổng quan ngắn của bài, **không nhắc tên file hay tên giáo trình**.
- Các **mục nhỏ** phủ toàn bộ nội dung bài, mỗi mục có ý chính và **khoảng trang** tham chiếu tới PDF gốc.
- Thuật ngữ quan trọng kèm định nghĩa.
- Hiển thị công thức toán bằng KaTeX.
- Nội dung sinh ra bằng tiếng Việt (mặc định); thuật ngữ chuyên ngành giữ nguyên gốc kèm giải nghĩa, ví dụ "Primary key (khoá chính)". Áp dụng cho cả slide và quiz.

### 3.4 Slide (theo bài)
- Slide là **phiên bản dễ hiểu** của giáo trình, AI soạn từ văn bản gốc: slide tiêu đề (tên bài), mục lục bài (các mục kèm trang), 3–10 slide nội dung, slide "Ghi nhớ".
- Tiêu đề mỗi slide nêu đúng kiến thức chính của slide.
- Mỗi slide nội dung: tối đa 5 gạch đầu dòng, đoạn giải thích dễ hiểu và **ví dụ** (ưu tiên ví dụ trong giáo trình; ví dụ do AI tạo ghi rõ "Ví dụ minh hoạ").
- Xem trực tuyến ở chế độ trình chiếu và tải về dạng **PPTX**.

### 3.5 Quiz
- Mỗi bài có quiz riêng, số câu theo độ dài bài (khoảng 1,5 câu/trang, 5–15 câu), rải đều các mục để phủ trọn kiến thức; có thể tạo thêm quiz cho bài.
- **Quiz tổng hợp:** người dùng chọn phạm vi là các bài đã tạo, chọn 10 / 20 / 30 câu.
- Câu hỏi trắc nghiệm 4 lựa chọn; mỗi câu có đáp án đúng, giải thích ngắn và số trang tham chiếu.
- Làm bài, nộp bài, xem điểm theo từng bài và danh sách câu sai kèm giải thích.
- Lưu lịch sử điểm các lần làm.
- **Sửa quiz** (ADR-0018): sửa câu hỏi, lựa chọn, đáp án đúng, giải thích, trang tham chiếu; xoá, đổi thứ tự, thêm câu nhập tay (trang không bắt buộc); bấm Lưu một lần. Lưu chỉnh sửa xoá lịch sử làm bài của quiz đó (có cảnh báo).

### 3.6 Thư viện bài giảng
- Danh sách bài giảng của tài khoản: tên, ngày tạo, số trang, trạng thái, số bài đã tạo học liệu.
- Trang bài giảng: **mục lục** chương → bài → mục nhỏ (kèm trang) bên trái; bài đang chọn với các tab **Tóm tắt · Slide · Quiz · PDF gốc**, cùng tab **Quiz tổng hợp**.
- Bài giảng tạo theo cách cũ (trước v0.2) có nút "Tạo lại nội dung".
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
2. Worker trích xuất văn bản theo trang bằng PyMuPDF, tách chương theo mục lục (bookmark) hoặc tiêu đề (nếu không có thì chia theo số trang), rồi tách mỗi chương thành **bài nhỏ** (bookmark cấp 2, tiêu đề phụ, hoặc AI đề xuất). Bài giảng `completed` = mục lục sẵn sàng.
3. Người dùng chọn bài; với mỗi bài, worker: sinh tóm tắt theo mục nhỏ → sinh slide từ văn bản gốc (JSON; slide tiêu đề, mục lục, ghi nhớ do code ghép) → tạo file PPTX → sinh quiz mặc định.
4. Đầu ra LLM luôn được kiểm tra bằng Pydantic; chính sách thử lại khi lỗi mạng hoặc sai định dạng xem [ADR-0015](../adr/0015-lam-ro-pipeline-llm.md).
5. Kết quả mỗi bước lưu ngay; bài lỗi được tạo lại mà không gọi lại LLM cho bước đã xong.

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
| Quiz | `/lectures/{id}/quizzes`, `/quizzes/{id}`, `/quizzes/{id}/edit`, `/quizzes/{id}/questions`, `/quizzes/{id}/attempts`, `/attempts/{id}` |

Chi tiết request/response và mã lỗi: [api.md](../design/api.md).

## 8. Màn hình

1. **Trang chủ** – giới thiệu ngắn, nút "Đăng nhập với Google".
2. **Thư viện** – danh sách bài giảng, nút "Tải giáo trình mới".
3. **Tải lên** – vùng kéo-thả PDF, trạng thái xử lý.
4. **Bài giảng** – mục lục chương → bài (chọn bài để tạo học liệu); bài đang chọn có các tab Tóm tắt / Slide / Quiz / PDF gốc; tab Quiz tổng hợp.
5. **Làm quiz** – từng câu hỏi, nút nộp bài.
6. **Sửa quiz** – danh sách câu hỏi dạng form, thêm câu, nút Lưu.
7. **Kết quả** – điểm, câu sai kèm giải thích.

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
