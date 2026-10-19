# Tài liệu API

> Phiên bản 2.0 · Dựa trên [PRD v2.4](../product/PRD.md), [ADR](../adr/README.md) 0004, 0005, 0007, 0012, 0013, 0017 và [data-model.md](data-model.md) · Cập nhật 19/10/2026 (khớp code v0.2.0)

## 1. Quy ước chung

### 1.1 Địa chỉ
- Base URL: `https://<domain>/api` (dev: `http://localhost/api`).
- Frontend và API **cùng domain** qua Caddy (ADR-0014), không cần CORS.
- Tài liệu tương tác (OpenAPI do FastAPI sinh): `/api/docs`, schema: `/api/openapi.json`.

### 1.2 Xác thực
- Phiên đăng nhập bằng cookie `sid` (`HttpOnly`, `Secure`, `SameSite=Lax`), xem ADR-0005. Trình duyệt chấp nhận cookie `Secure` trên `http://localhost` nên dev không cần HTTPS.
- Luồng OAuth dùng thêm cookie ký `oauth_state` (sống 10 phút) để giữ `state`, PKCE verifier và `next`.
- Trình duyệt tự gửi cookie; frontend gọi `fetch` với `credentials: "include"`.
- Mọi endpoint, trừ nhóm `auth` và `health`, yêu cầu đăng nhập; thiếu hoặc hết hạn phiên → `401 UNAUTHENTICATED`.

### 1.3 Chống CSRF
Mọi request `POST`, `PATCH`, `DELETE` phải có header:
```
X-Requested-With: fetch
```
Thiếu header → `403 CSRF_REJECTED`.

### 1.4 Định dạng
- Request và response dùng JSON (`Content-Type: application/json`), trừ upload (`multipart/form-data`) và tải file.
- ID dạng UUID; thời gian dạng ISO 8601 UTC, ví dụ `2026-10-18T09:30:00Z`.
- Tên trường dạng `snake_case`.

### 1.5 Phân trang
Endpoint danh sách nhận `page` (mặc định 1) và `page_size` (mặc định 20, tối đa 100), trả về:
```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 42
}
```

### 1.6 Lỗi
Mọi lỗi có dạng:
```json
{
  "code": "LECTURE_NOT_FOUND",
  "detail": "Không tìm thấy bài giảng."
}
```
Lỗi validate (422) có thêm `errors`:
```json
{
  "code": "VALIDATION_ERROR",
  "detail": "Dữ liệu không hợp lệ.",
  "errors": [{ "field": "title", "message": "Tối đa 200 ký tự." }]
}
```

| HTTP | `code` | Khi nào |
|---|---|---|
| 400 | `INVALID_FILE_TYPE` | File không phải PDF |
| 400 | `PDF_ENCRYPTED` | PDF có mật khẩu |
| 400 | `PDF_TOO_MANY_PAGES` | Quá 200 trang |
| 400 | `PDF_CORRUPTED` | Không mở được PDF |
| 401 | `UNAUTHENTICATED` | Chưa đăng nhập / phiên hết hạn |
| 403 | `CSRF_REJECTED` | Thiếu header `X-Requested-With` |
| 404 | `LECTURE_NOT_FOUND` · `LESSON_NOT_FOUND` · `QUIZ_NOT_FOUND` · `ATTEMPT_NOT_FOUND` | Không tồn tại **hoặc không thuộc người dùng** |
| 409 | `LECTURE_NOT_READY` | Mục lục chưa sẵn sàng / bài giảng đang xử lý |
| 409 | `LESSON_NOT_READY` | Bài học chưa được tạo học liệu |
| 409 | `LECTURE_NOT_FAILED` | Thử lại bài giảng không ở trạng thái `failed` |
| 409 | `QUIZ_NOT_READY` | Quiz chưa `completed` |
| 413 | `FILE_TOO_LARGE` | File > 20 MB |
| 422 | `VALIDATION_ERROR` | Dữ liệu không hợp lệ |
| 429 | `RATE_LIMITED` | Vượt giới hạn tần suất |
| 500 | `INTERNAL` | Lỗi máy chủ |

> Tài nguyên của người khác luôn trả **404**, không phải 403, để không lộ sự tồn tại.

### 1.7 Giới hạn tần suất
| Nhóm | Giới hạn |
|---|---|
| `POST /lectures` | 10 lần / giờ / người dùng |
| `POST /lectures/{id}/quizzes` | 20 lần / giờ / người dùng |
| Còn lại | 120 request / phút / người dùng |

Khi vượt giới hạn, response có header `Retry-After` (giây).

> **v0.1.0 chưa triển khai giới hạn tần suất** (để sau theo kế hoạch); mã `429 RATE_LIMITED` chưa được trả.

## 2. Danh sách endpoint

| Method | Đường dẫn | Mô tả |
|---|---|---|
| GET | `/health` | Kiểm tra hệ thống |
| GET | `/auth/google/login` | Bắt đầu đăng nhập Google |
| GET | `/auth/google/callback` | Google redirect về |
| POST | `/auth/logout` | Đăng xuất |
| GET | `/me` | Người dùng hiện tại |
| POST | `/lectures` | Tải PDF, tạo bài giảng |
| GET | `/lectures` | Danh sách bài giảng |
| GET | `/lectures/{id}` | Chi tiết, trạng thái bài giảng |
| PATCH | `/lectures/{id}` | Đổi tên |
| DELETE | `/lectures/{id}` | Xoá |
| POST | `/lectures/{id}/retry` | Xử lý lại bài giảng lỗi |
| GET | `/lectures/{id}/pdf` | Tải PDF gốc |
| POST | `/lectures/{id}/regenerate` | Tạo lại nội dung (bài giảng định dạng cũ) |
| GET | `/lectures/{id}/outline` | Mục lục chương → bài → mục nhỏ |
| POST | `/lectures/{id}/lessons/generate` | Tạo học liệu cho các bài đã chọn |
| GET | `/lessons/{id}/summary` | Tóm tắt một bài |
| GET | `/lessons/{id}/slides` | Slide một bài (JSON) |
| GET | `/lessons/{id}/slides.pptx` | Tải PPTX một bài |
| GET | `/lessons/{id}/quizzes` | Quiz của một bài |
| POST | `/lessons/{id}/quizzes` | Sinh thêm quiz cho một bài |
| GET | `/lectures/{id}/quizzes` | Mọi quiz của bài giảng |
| POST | `/lectures/{id}/quizzes` | Sinh quiz tổng hợp trên các bài đã chọn |
| GET | `/quizzes/{id}` | Câu hỏi của quiz (không có đáp án) |
| DELETE | `/quizzes/{id}` | Xoá quiz |
| POST | `/quizzes/{id}/attempts` | Nộp bài, chấm điểm |
| GET | `/quizzes/{id}/attempts` | Lịch sử làm bài |
| GET | `/attempts/{id}` | Chi tiết một lần làm |

---

## 3. Hệ thống

### `GET /health`
Không cần đăng nhập. Dùng cho Docker healthcheck.

**200**
```json
{ "status": "ok", "db": "ok", "redis": "ok" }
```
**503** nếu DB hoặc Redis lỗi, cùng cấu trúc với giá trị `"error"` ở thành phần lỗi.

---

## 4. Xác thực

### `GET /auth/google/login`
Chuyển hướng trình duyệt tới trang đăng nhập Google (OAuth Authorization Code + PKCE).

| Query | Bắt buộc | Mô tả |
|---|---|---|
| `next` | Không | Đường dẫn nội bộ quay về sau đăng nhập, mặc định `/library`. Chỉ chấp nhận đường dẫn bắt đầu bằng `/` (chống open redirect). |

**302** → `https://accounts.google.com/o/oauth2/v2/auth?...`

Frontend dùng thẻ `<a href="/api/auth/google/login">`, không gọi bằng `fetch`.

### `GET /auth/google/callback`
Google gọi về, không dùng trực tiếp từ frontend.

Backend kiểm tra `state`, đổi `code` lấy token, xác minh `id_token`, yêu cầu `email_verified = true`, tạo/cập nhật `users`, tạo `sessions`, đặt cookie `sid`.

| Kết quả | Response |
|---|---|
| Thành công | **302** → `next` (mặc định `/library`), kèm `Set-Cookie: sid=...` |
| Người dùng huỷ / lỗi | **302** → `/?login_error=<code>` (`access_denied`, `invalid_state`, `email_not_verified`, `google_error`) |

### `POST /auth/logout`
Xoá phiên hiện tại và cookie.

**204** – không có nội dung. Gọi khi chưa đăng nhập cũng trả 204.

---

## 5. Người dùng

### `GET /me`

**200**
```json
{
  "id": "0b6f3c1e-7f0a-4b0b-9d6a-2e1f6c9a1d11",
  "email": "nguyenvana@gmail.com",
  "name": "Nguyễn Văn A",
  "avatar_url": "https://lh3.googleusercontent.com/a/...",
  "created_at": "2026-10-01T02:15:00Z"
}
```
**401** nếu chưa đăng nhập. Frontend dùng endpoint này để kiểm tra trạng thái đăng nhập.

---

## 6. Bài giảng

### Đối tượng `Lecture`
```json
{
  "id": "5d2c8a40-1e4b-4c3a-9a0f-8b7e6d5c4b3a",
  "title": "Nhập môn Cơ sở dữ liệu",
  "original_filename": "nhap-mon-csdl.pdf",
  "file_size": 4823011,
  "page_count": 142,
  "status": "completed",
  "progress_step": "extracting",
  "error": null,
  "lessons": { "total": 30, "completed": 4, "processing": 1, "failed": 0 },
  "needs_regenerate": false,
  "created_at": "2026-10-18T09:30:00Z",
  "updated_at": "2026-10-18T09:31:12Z",
  "completed_at": null
}
```

| Trường | Mô tả |
|---|---|
| `status` | `queued` · `processing` · `completed` (= mục lục đã sẵn sàng, ADR-0017) · `failed` |
| `progress_step` | `extracting` · `null` (giá trị `summarizing`/`slides`/`quiz` chỉ còn ở dữ liệu cũ) |
| `error` | `null` hoặc `{ "code": "PDF_NO_TEXT", "message": "Giáo trình có vẻ là bản scan, hiện chưa được hỗ trợ." }` |
| `lessons` | Số bài theo trạng thái tạo học liệu |
| `needs_regenerate` | `true` nếu bài giảng tạo theo luồng cũ (hoàn tất nhưng không có bài) → hiện nút "Tạo lại nội dung" |

### `POST /lectures`
Tải PDF lên và bắt đầu xử lý.

**Request:** `multipart/form-data`

| Trường | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| `file` | file | Có | PDF, ≤ 20 MB, ≤ 200 trang, không mã hoá |
| `title` | string | Không | 1–200 ký tự; mặc định lấy từ metadata PDF hoặc tên file |

```bash
curl -X POST https://<domain>/api/lectures \
  -H "X-Requested-With: fetch" \
  -b "sid=..." \
  -F "file=@nhap-mon-csdl.pdf" \
  -F "title=Nhập môn Cơ sở dữ liệu"
```

**201** – đối tượng `Lecture` với `status: "queued"`; header `Location: /api/lectures/{id}`.

**Lỗi:** `400 INVALID_FILE_TYPE · PDF_ENCRYPTED · PDF_TOO_MANY_PAGES · PDF_CORRUPTED`, `413 FILE_TOO_LARGE`, `429 RATE_LIMITED`.

> PDF dạng scan vẫn được nhận (201); lỗi `PDF_NO_TEXT` được phát hiện trong worker và trả qua trường `error` khi polling.

### `GET /lectures`
Danh sách bài giảng của người dùng.

| Query | Mặc định | Mô tả |
|---|---|---|
| `q` | – | Tìm theo tên (không phân biệt hoa thường, chứa chuỗi – `ILIKE`) |
| `status` | – | Lọc theo trạng thái |
| `sort` | `-created_at` | `-created_at` · `created_at` · `title` · `-title` |
| `page`, `page_size` | 1, 20 | Xem 1.5 |

**200**
```json
{
  "items": [ { "...": "Lecture" } ],
  "page": 1,
  "page_size": 20,
  "total": 3
}
```

### `GET /lectures/{id}`
**200** – `Lecture`. **404** `LECTURE_NOT_FOUND`.

Frontend polling 3 giây/lần khi `status` là `queued` hoặc `processing` (ADR-0013).

### `PATCH /lectures/{id}`
Đổi tên.

**Request**
```json
{ "title": "CSDL – Học kỳ 1" }
```
**200** – `Lecture` đã cập nhật. **422** nếu tên rỗng hoặc > 200 ký tự.

### `DELETE /lectures/{id}`
Xoá bài giảng, mọi dữ liệu liên quan và file trên MinIO. Nếu đang xử lý, job sẽ tự dừng ở bước kế tiếp khi phát hiện bài giảng không còn.

**204**. **404** `LECTURE_NOT_FOUND`.

### `POST /lectures/{id}/retry`
Xử lý lại bài giảng `failed`. Các bước đã hoàn thành được giữ nguyên (ADR-0008).

**202** – `Lecture` với `status: "queued"`. **409** `LECTURE_NOT_FAILED`.

### `GET /lectures/{id}/pdf`
Tải PDF gốc.

| Query | Mặc định | Mô tả |
|---|---|---|
| `download` | `false` | `true` → `Content-Disposition: attachment`; `false` → `inline` để xem trong trình duyệt |

**200** – `Content-Type: application/pdf`, dữ liệu streaming. Hỗ trợ header `Range` để pdf.js tải từng phần.

---

## 7. Mục lục và bài học (ADR-0017)

### `POST /lectures/{id}/regenerate`
Xoá chương, bài, tóm tắt, slide, quiz (kèm lịch sử làm bài) và file PPTX; giữ PDF; tách mục lục lại.

**202** – `Lecture` với `status: "queued"`. **409** `LECTURE_NOT_READY` nếu đang xử lý.

### `GET /lectures/{id}/outline`
Mục lục chương → bài. Frontend polling 3 giây khi có bài `queued`/`processing`.

**200**
```json
{
  "lecture_id": "5d2c8a40-...",
  "chapters": [
    {
      "id": "c1...",
      "idx": 1,
      "title": "Chương 2. Thuật toán",
      "page_start": 10,
      "page_end": 16,
      "lessons": [
        {
          "id": "b43092d1-...",
          "idx": 6,
          "number": "2.3",
          "title": "Hình thức hóa thuật toán và các phương pháp biểu diễn",
          "page_start": 11,
          "page_end": 13,
          "status": "completed",
          "progress_step": "quiz",
          "error": null,
          "available": { "summary": true, "slides": true, "pptx": true, "quiz": true },
          "sections": [
            { "title": "Định nghĩa thuật toán và luận điểm Turing", "page_start": 11, "page_end": 12 }
          ]
        }
      ]
    }
  ]
}
```

| Trường bài | Mô tả |
|---|---|
| `status` | `pending` (chưa chọn) · `queued` · `processing` · `completed` · `failed` |
| `progress_step` | `summarizing` · `slides` · `quiz` · `null` |
| `sections` | Mục nhỏ kèm trang, có sau khi tóm tắt (rỗng nếu chưa) |

### `POST /lectures/{id}/lessons/generate`
Xếp hàng tạo tóm tắt + slide + quiz mặc định cho các bài đã chọn. Bài `queued`/`processing`/`completed` được bỏ qua; bài `failed` được tạo lại (bước đã xong không chạy lại).

**Request**
```json
{ "lesson_ids": ["b43092d1-...", "4a8146a5-..."] }
```

**202** – `Outline` mới. **409** `LECTURE_NOT_READY` nếu mục lục chưa sẵn sàng. **422** nếu danh sách rỗng hoặc có bài không thuộc bài giảng.

## 8. Nội dung một bài

### `GET /lessons/{id}/summary`
**200**
```json
{
  "lesson_id": "b43092d1-...",
  "number": "2.3",
  "title": "Hình thức hóa thuật toán và các phương pháp biểu diễn",
  "page_start": 11,
  "page_end": 13,
  "overview": "Bài học trình bày...",
  "sections": [
    {
      "title": "Định nghĩa thuật toán và luận điểm Turing",
      "page_start": 11,
      "page_end": 12,
      "key_points": ["..."]
    }
  ],
  "terms": [{ "term": "Máy Turing", "definition": "..." }],
  "content_md": "## Tổng quan\n\n...\n\n### Định nghĩa thuật toán... *(tr. 11–12)*\n..."
}
```
Không chứa tên file hay tên giáo trình. **409** `LESSON_NOT_READY`, **404** `LESSON_NOT_FOUND`.

### `GET /lessons/{id}/slides`
**200** – `{ "lesson_id", "deck": SlideDeck, "pptx_available": true }`. Slide nội dung có thêm `explanation` và `example` (xem [data-model.md](data-model.md) 4.2a). **409** `LESSON_NOT_READY`.

### `GET /lessons/{id}/slides.pptx`
**200** – file PPTX, tên "số bài + tên bài".pptx (RFC 5987). **409** `LESSON_NOT_READY` nếu chưa có slide hoặc xuất PPTX thất bại.

---

## 9. Quiz

### Đối tượng `QuizSummary`
```json
{
  "id": "a41f9e22-...",
  "lecture_id": "5d2c8a40-...",
  "lesson_id": "b43092d1-...",
  "lesson_ids": null,
  "status": "completed",
  "num_questions": 5,
  "is_default": true,
  "error": null,
  "attempt_count": 2,
  "best_score": 8,
  "last_attempt_at": "2026-10-18T10:05:00Z",
  "created_at": "2026-10-18T09:34:10Z"
}
```

`lesson_id`: quiz của một bài (`null` với quiz tổng hợp hoặc quiz cũ). `lesson_ids`: phạm vi quiz tổng hợp. Quiz mặc định của bài có `num_questions` = clamp(round(số trang × 1,5), 5, 15).

`error`: `null` hoặc `{ "code": "QUIZ_FAILED", "message": "<thông điệp tiếng Việt>" }` khi `status = failed`. `attempt_count`, `best_score`, `last_attempt_at` chỉ tính các lần làm của người dùng hiện tại.

### `GET /lectures/{id}/quizzes` · `GET /lessons/{id}/quizzes`
Danh sách quiz của bài giảng (mọi loại) hoặc của một bài, mới nhất trước (không phân trang).

**200**
```json
{ "items": [ { "...": "QuizSummary" } ] }
```

### `POST /lessons/{id}/quizzes`
Sinh thêm quiz cho một bài (bất đồng bộ). Bài phải đã tạo học liệu.

**Request** – `{ "num_questions": 10 }` (5–30, mặc định 10).

**202** – `QuizSummary` với `status: "queued"`. Frontend polling danh sách quiz tới khi `completed`/`failed`. **409** `LESSON_NOT_READY`.

### `POST /lectures/{id}/quizzes`
Sinh **quiz tổng hợp** trên các bài người dùng chọn (đã tạo học liệu); câu hỏi phân bổ theo độ dài từng bài.

**Request**
```json
{ "num_questions": 20, "lesson_ids": ["b43092d1-...", "4a8146a5-..."] }
```
| Trường | Giá trị |
|---|---|
| `num_questions` | 5–30 (mặc định 20) |
| `lesson_ids` | ≥ 1 bài thuộc bài giảng |

**202** – `QuizSummary`. **409** `LESSON_NOT_READY` nếu có bài chưa tạo học liệu. **422** nếu có bài không thuộc bài giảng.

### `GET /quizzes/{id}`
Lấy câu hỏi để làm bài. **Không** chứa `answer_index` và `explanation`.

**200**
```json
{
  "id": "a41f9e22-...",
  "lecture_id": "5d2c8a40-...",
  "lecture_title": "Nhập môn Cơ sở dữ liệu",
  "lesson_id": "b43092d1-...",
  "scope_title": "Bài 2.3: Hình thức hóa thuật toán và các phương pháp biểu diễn",
  "num_questions": 10,
  "questions": [
    {
      "id": "7b1e0c55-...",
      "position": 1,
      "question": "Thuộc tính nào dùng để định danh duy nhất mỗi bộ trong một quan hệ?",
      "options": ["Khoá ngoại", "Khoá chính", "Chỉ mục", "Ràng buộc CHECK"],
      "page_ref": 34
    }
  ]
}
```
**409** `QUIZ_NOT_READY` nếu quiz chưa `completed`.

### `DELETE /quizzes/{id}`
Xoá quiz cùng câu hỏi và lịch sử làm bài. **204**.

### `POST /quizzes/{id}/attempts`
Nộp bài và chấm điểm.

**Request**
```json
{
  "answers": {
    "7b1e0c55-...": 1,
    "c09a3f10-...": null
  }
}
```
- Khoá là `question_id` của quiz này; giá trị `0–3` hoặc `null` (bỏ trống).
- Câu không có trong `answers` được tính là bỏ trống.
- `question_id` không thuộc quiz → **422**.

**201** – đối tượng `AttemptResult`
```json
{
  "id": "e8d7c6b5-...",
  "quiz_id": "a41f9e22-...",
  "lecture_id": "5d2c8a40-...",
  "lecture_title": "Nhập môn Cơ sở dữ liệu",
  "lesson_id": "b43092d1-...",
  "scope_title": "Bài 2.3: Hình thức hóa thuật toán và các phương pháp biểu diễn",
  "score": 7,
  "total": 10,
  "created_at": "2026-10-18T10:05:00Z",
  "results": [
    {
      "question_id": "7b1e0c55-...",
      "position": 1,
      "question": "Thuộc tính nào dùng để định danh duy nhất mỗi bộ trong một quan hệ?",
      "options": ["Khoá ngoại", "Khoá chính", "Chỉ mục", "Ràng buộc CHECK"],
      "selected_index": 1,
      "correct_index": 1,
      "is_correct": true,
      "explanation": "Khoá chính xác định duy nhất mỗi bộ, không được trùng và không NULL.",
      "page_ref": 34
    }
  ],
  "by_chapter": [
    { "chapter_idx": 0, "title": "Chương 1. Tổng quan", "correct": 3, "total": 3 },
    { "chapter_idx": 1, "title": "Chương 2. Mô hình quan hệ", "correct": 4, "total": 7 }
  ]
}
```
`by_chapter` giúp người dùng biết phần nào cần ôn lại: với quiz theo bài/quiz tổng hợp, mỗi phần tử là một **bài** (`chapter_idx` = `lessons.idx`, `title` = số bài + tên bài); với quiz cũ là chương. `scope_title`: "Bài 2.3: …", "Quiz tổng hợp N bài" hoặc "Toàn bài giảng". `lecture_id`, `lecture_title` để trang kết quả liên kết về bài giảng và tab PDF gốc.

Lỗi validate có `errors`, ví dụ `[{ "field": "answers.<question_id>", "message": "Câu hỏi không thuộc quiz này." }]`. **409** `QUIZ_NOT_READY` nếu quiz chưa `completed`.

### `GET /quizzes/{id}/attempts`
Lịch sử làm bài, mới nhất trước. Hỗ trợ phân trang.

**200**
```json
{
  "items": [
    { "id": "e8d7c6b5-...", "score": 7, "total": 10, "created_at": "2026-10-18T10:05:00Z" }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

### `GET /attempts/{id}`
Xem lại chi tiết một lần làm bài.

**200** – `AttemptResult` (giống response của `POST /quizzes/{id}/attempts`). **404** `ATTEMPT_NOT_FOUND`.

---

## 10. Luồng sử dụng tiêu biểu

```
1. GET  /api/me                          → 401 → hiện nút đăng nhập
2. (trình duyệt) /api/auth/google/login  → Google → callback → /library
3. GET  /api/lectures                    → hiển thị thư viện
4. POST /api/lectures (multipart)        → 201 {status: queued}
5. GET  /api/lectures/{id}  (mỗi 3 giây) → processing/extracting → completed (vài giây)
6. GET  /api/lectures/{id}/outline       → mục lục chương → bài
7. POST /api/lectures/{id}/lessons/generate {lesson_ids} → bài queued
8. GET  /api/lectures/{id}/outline (mỗi 3 giây) → bài completed
9. GET  /api/lessons/{lid}/summary | slides | quizzes → tab Tóm tắt, Slide, Quiz
10. GET  /api/quizzes/{qid}              → làm bài
11. POST /api/quizzes/{qid}/attempts     → kết quả, giải thích
```

## 11. Kiểu TypeScript cho frontend

Không viết tay. Sinh từ OpenAPI (ADR-0003) khi hệ thống đang chạy:
```bash
just gen-api
# = cd frontend && npm run gen:api
# = openapi-typescript http://localhost/api/openapi.json -o src/lib/api-types.ts
```
