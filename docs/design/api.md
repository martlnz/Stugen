# Tài liệu API

> Dựa trên [PRD v2.1](../product/PRD.md), [ADR](../adr/README.md) 0004, 0005, 0007, 0012, 0013 và [data-model.md](data-model.md) · Cập nhật 18/10/2026

## 1. Quy ước chung

### 1.1 Địa chỉ
- Base URL: `https://<domain>/api` (dev: `http://localhost/api`).
- Frontend và API **cùng domain** qua Caddy (ADR-0014), không cần CORS.
- Tài liệu tương tác (OpenAPI do FastAPI sinh): `/api/docs`, schema: `/api/openapi.json`.

### 1.2 Xác thực
- Phiên đăng nhập bằng cookie `sid` (`HttpOnly`, `Secure`, `SameSite=Lax`), xem ADR-0005.
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
| 404 | `LECTURE_NOT_FOUND` · `QUIZ_NOT_FOUND` · `ATTEMPT_NOT_FOUND` | Không tồn tại **hoặc không thuộc người dùng** |
| 409 | `LECTURE_NOT_READY` | Nội dung yêu cầu chưa được tạo xong |
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
| GET | `/lectures/{id}/summary` | Tóm tắt |
| GET | `/lectures/{id}/slides` | Slide (JSON) |
| GET | `/lectures/{id}/slides.pptx` | Tải PPTX |
| GET | `/lectures/{id}/quizzes` | Danh sách quiz của bài giảng |
| POST | `/lectures/{id}/quizzes` | Sinh quiz mới |
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
  "status": "processing",
  "progress_step": "summarizing",
  "error": null,
  "available": {
    "summary": false,
    "slides": false,
    "pptx": false,
    "quiz": false
  },
  "created_at": "2026-10-18T09:30:00Z",
  "updated_at": "2026-10-18T09:31:12Z",
  "completed_at": null
}
```

| Trường | Mô tả |
|---|---|
| `status` | `queued` · `processing` · `completed` · `failed` |
| `progress_step` | `extracting` · `summarizing` · `slides` · `quiz` · `null` |
| `error` | `null` hoặc `{ "code": "PDF_NO_TEXT", "message": "Giáo trình có vẻ là bản scan, hiện chưa được hỗ trợ." }` |
| `available` | Phần nào đã sẵn sàng; frontend dùng để bật tab tương ứng mà không cần chờ hoàn tất |

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
| `q` | – | Tìm theo tên (không phân biệt hoa thường, gần đúng) |
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

## 7. Tóm tắt

### `GET /lectures/{id}/summary`

**200**
```json
{
  "lecture_id": "5d2c8a40-...",
  "overview": "Giáo trình giới thiệu các khái niệm nền tảng về cơ sở dữ liệu...",
  "learning_objectives": [
    "Hiểu vai trò của hệ quản trị cơ sở dữ liệu",
    "Thiết kế được lược đồ quan hệ ở dạng chuẩn 3NF"
  ],
  "chapters": [
    {
      "idx": 0,
      "title": "Chương 1. Tổng quan về cơ sở dữ liệu",
      "key_points": ["..."],
      "terms": [{ "term": "DBMS", "definition": "..." }],
      "page_start": 1,
      "page_end": 18
    }
  ],
  "content_md": "# Nhập môn Cơ sở dữ liệu\n\n## Tổng quan\n...",
  "created_at": "2026-10-18T09:32:40Z"
}
```

Frontend hiển thị `content_md` (react-markdown + KaTeX), dùng `chapters` để dựng mục lục bên cạnh và liên kết số trang sang tab PDF gốc.

**409** `LECTURE_NOT_READY` nếu chưa có tóm tắt.

---

## 8. Slide

### `GET /lectures/{id}/slides`

**200**
```json
{
  "lecture_id": "5d2c8a40-...",
  "deck": {
    "version": 1,
    "title": "Nhập môn Cơ sở dữ liệu",
    "slides": [
      { "layout": "title", "title": "Nhập môn Cơ sở dữ liệu", "subtitle": "Tóm lược giáo trình" },
      {
        "layout": "bullets",
        "title": "Hệ quản trị CSDL",
        "bullets": ["Lưu trữ và truy xuất dữ liệu", "Đảm bảo toàn vẹn và bảo mật"],
        "notes": "Nhấn mạnh vai trò trung gian.",
        "page_refs": [5, 6]
      }
    ]
  },
  "pptx_available": true,
  "created_at": "2026-10-18T09:33:30Z"
}
```
Cấu trúc `deck` xem [data-model.md](data-model.md#42-slide_decksdeck--slidedeck). **409** `LECTURE_NOT_READY`.

### `GET /lectures/{id}/slides.pptx`
**200** – `Content-Type: application/vnd.openxmlformats-officedocument.presentationml.presentation`, `Content-Disposition: attachment; filename="<title>.pptx"` (tên file mã hoá theo RFC 5987 để giữ tiếng Việt).

**409** `LECTURE_NOT_READY` nếu chưa có slide hoặc xuất PPTX thất bại.

---

## 9. Quiz

### Đối tượng `QuizSummary`
```json
{
  "id": "a41f9e22-...",
  "lecture_id": "5d2c8a40-...",
  "status": "completed",
  "num_questions": 10,
  "is_default": true,
  "error": null,
  "attempt_count": 2,
  "best_score": 8,
  "last_attempt_at": "2026-10-18T10:05:00Z",
  "created_at": "2026-10-18T09:34:10Z"
}
```

### `GET /lectures/{id}/quizzes`
Danh sách quiz của bài giảng, mới nhất trước (không phân trang).

**200**
```json
{ "items": [ { "...": "QuizSummary" } ] }
```

### `POST /lectures/{id}/quizzes`
Sinh quiz mới (bất đồng bộ). Bài giảng phải có `chapters` (đã qua bước trích xuất).

**Request**
```json
{ "num_questions": 20 }
```
| Trường | Giá trị |
|---|---|
| `num_questions` | `10` · `20` · `30` (mặc định 10) |

**202** – `QuizSummary` với `status: "queued"`. Frontend polling `GET /lectures/{id}/quizzes` tới khi `completed`/`failed`.

**409** `LECTURE_NOT_READY`, **429** `RATE_LIMITED`.

### `GET /quizzes/{id}`
Lấy câu hỏi để làm bài. **Không** chứa `answer_index` và `explanation`.

**200**
```json
{
  "id": "a41f9e22-...",
  "lecture_id": "5d2c8a40-...",
  "lecture_title": "Nhập môn Cơ sở dữ liệu",
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
`by_chapter` giúp người dùng biết chương nào cần ôn lại.

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
5. GET  /api/lectures/{id}  (mỗi 3 giây) → processing/summarizing ... → completed
6. GET  /api/lectures/{id}/summary       → tab Tóm tắt
7. GET  /api/lectures/{id}/slides        → tab Slide
8. GET  /api/lectures/{id}/quizzes       → quiz mặc định
9. GET  /api/quizzes/{qid}               → làm bài
10. POST /api/quizzes/{qid}/attempts     → kết quả, giải thích
```

## 11. Kiểu TypeScript cho frontend

Không viết tay. Sinh từ OpenAPI (ADR-0003):
```bash
npx openapi-typescript http://localhost/api/openapi.json -o src/lib/api-types.ts
```
