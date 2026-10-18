# ADR-0008: Xử lý bất đồng bộ bằng Celery + Redis

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-18

## Bối cảnh
Theo ADR-0002, việc xử lý PDF và gọi LLM chạy ở worker. Cần hàng đợi tin cậy, có retry, giới hạn đồng thời.

## Các phương án
1. **FastAPI BackgroundTasks** – chạy trong cùng tiến trình API; mất job khi restart, không retry.
2. **RQ** – đơn giản, ít tính năng (không có chain/group tiện lợi).
3. **Celery + Redis** – phổ biến, có retry, rate limit, chain, giới hạn concurrency, hẹn giờ.
4. **Dramatiq / arq** – tốt nhưng cộng đồng nhỏ hơn.

## Quyết định
Chọn **Celery 5 + Redis 7** làm broker. Không dùng result backend (kết quả ghi thẳng vào PostgreSQL).

### Task
| Task | Mô tả | Queue |
|---|---|---|
| `process_lecture(lecture_id)` | Điều phối: trích xuất → tóm tắt → slide → quiz mặc định | `ai` |
| `generate_quiz(quiz_id)` | Sinh quiz mới theo yêu cầu người dùng | `ai` |
| `cleanup_orphans()` | Dọn file mồ côi, phiên hết hạn (Celery beat, hằng ngày) | `default` |

`process_lecture` chạy tuần tự các bước trong một task (không tách chain) để đơn giản, cập nhật `progress_step` sau mỗi bước.

### Cấu hình
- `task_acks_late=True`, `worker_prefetch_multiplier=1`: job không mất nếu worker chết giữa chừng.
- `worker_concurrency=2` mặc định (giới hạn bởi rate limit LLM, chỉnh qua env).
- `task_time_limit=900s` (15 phút), `soft_time_limit=840s`.
- Retry tự động 2 lần với backoff cho lỗi tạm thời (mạng, 429/5xx từ LLM).

### Tính idempotent
Mỗi bước kiểm tra kết quả đã tồn tại trước khi chạy (ví dụ đã có `chapters` thì bỏ qua trích xuất), nên chạy lại task an toàn và tiết kiệm lượt gọi LLM.

### Xử lý lỗi
Lỗi không thể phục hồi (PDF không có văn bản, LLM trả sai định dạng sau khi thử lại) → `status='failed'`, `error` chứa thông điệp tiếng Việt thân thiện. Người dùng có nút "Thử lại" (`POST /api/lectures/{id}/retry`).

## Hệ quả
- **Tích cực:** Tin cậy, kiểm soát được tải lên LLM, dễ thêm worker.
- **Tiêu cực:** Celery cấu hình nhiều; cần thêm container `worker` và `beat`.
