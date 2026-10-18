# ADR-0013: Cập nhật trạng thái xử lý bằng polling

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-18

## Bối cảnh
Sau khi tải PDF, người dùng cần thấy tiến trình (đang trích xuất, đang tóm tắt…) và biết khi nào hoàn tất. Thời gian xử lý từ 30 giây tới vài phút.

## Các phương án
1. **Polling** – frontend gọi `GET /api/lectures/{id}` định kỳ.
2. **Server-Sent Events (SSE)** – backend đẩy sự kiện; cần Redis pub/sub để chuyển sự kiện từ worker sang API, cấu hình proxy không buffer.
3. **WebSocket** – hai chiều, quá mức cần thiết.

## Quyết định
Chọn **polling** bằng TanStack Query.

- Khi `status ∈ {queued, processing}`: `refetchInterval = 3000ms`; dừng khi `completed` hoặc `failed`.
- Trang Thư viện cũng polling (5 giây) chỉ khi có bài giảng đang xử lý.
- Phản hồi gồm `status`, `progress_step`, `error`; frontend hiển thị các bước:
  `Đang trích xuất → Đang tóm tắt → Đang tạo slide → Đang tạo quiz → Hoàn tất`.
- Tóm tắt có thể hiển thị ngay khi bước tóm tắt xong, không cần chờ slide/quiz.

## Hệ quả
- **Tích cực:** Đơn giản, không cần hạ tầng thêm, hoạt động qua mọi proxy.
- **Tiêu cực:** Độ trễ tối đa ~3 giây; tải thêm vài request/phút — không đáng kể với quy mô dự án. Có thể chuyển sang SSE trong ADR sau nếu cần stream nội dung.
