# ADR-0007: Lưu trữ file bằng MinIO (S3-compatible)

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-18

## Bối cảnh
Cần lưu PDF gốc (tối đa 20 MB) và file PPTX sinh ra. API và worker chạy ở container khác nhau nhưng đều cần đọc/ghi file. File phải riêng tư theo tài khoản.

## Các phương án
1. **Thư mục cục bộ + Docker volume dùng chung** – đơn giản nhất; khó khi tách máy chủ, không có URL ký.
2. **MinIO** – tương thích S3, chạy trong Docker Compose, chuyển sang S3/R2 chỉ bằng đổi cấu hình.
3. **Lưu BLOB trong PostgreSQL** – một nơi lưu, nhưng làm phình DB và backup.

## Quyết định
Chọn **MinIO**, truy cập qua `boto3` sau một lớp trừu tượng `Storage` (`put`, `get`, `delete`, `delete_prefix`).

- Một bucket riêng tư `lectures`, key theo dạng `users/{user_id}/lectures/{lecture_id}/source.pdf` và `.../slides.pptx`.
- Bucket không bao giờ public. File được trả về qua API (`GET /api/lectures/{id}/pdf`, `/slides.pptx`) sau khi kiểm tra quyền sở hữu, phát dạng streaming.
- Xoá bài giảng: xoá bản ghi DB rồi `delete_prefix` của thư mục bài giảng. Nếu xoá file thất bại thì ghi log, không chặn người dùng (file mồ côi được dọn bằng script định kỳ).

## Upload
- Frontend gửi `multipart/form-data` tới `POST /api/lectures`; API kiểm tra:
  - Kích thước ≤ 20 MB (giới hạn cả ở Caddy).
  - Magic bytes bắt đầu bằng `%PDF-`.
  - Mở được bằng PyMuPDF, không mã hoá, ≤ 200 trang.
- Hợp lệ → ghi vào MinIO → tạo `lecture` (`queued`) → đẩy job.

Không dùng presigned upload trực tiếp từ trình duyệt vì file nhỏ và cần kiểm tra ngay khi nhận.

## Hệ quả
- **Tích cực:** API và worker dùng chung file dễ dàng; có thể chuyển lên cloud không đổi code.
- **Tiêu cực:** Thêm một container; file đi qua API (chấp nhận với 20 MB).
