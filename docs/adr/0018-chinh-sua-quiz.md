# ADR-0018: Chỉnh sửa quiz sau khi AI sinh

- **Trạng thái:** Chấp nhận · Sửa đổi một phần [ADR-0012](0012-thiet-ke-quiz.md)
- **Ngày:** 2026-10-20

## Bối cảnh
Quiz do AI sinh có thể có câu sai, mơ hồ hoặc thiếu ý người học cần. Trước đây (PRD 2.4) "chỉnh sửa nội dung đã sinh" nằm ngoài phạm vi: người dùng chỉ xoá được quiz hoặc sinh quiz mới. Chủ dự án muốn có chế độ sửa: sửa từng câu, từng lựa chọn, đáp án đúng, giải thích; xoá, đổi thứ tự, thêm câu nhập tay; bấm **Lưu** một lần để ghi lại.

Ràng buộc:
- ADR-0012: `GET /quizzes/{id}` không lộ `answer_index`, `explanation`.
- `quiz_attempts` được chấm lại từ bảng `questions` mỗi khi xem chi tiết lần làm.
- Câu nhập tay có thể không gắn với trang nào cụ thể.

## Yếu tố quyết định
- Thao tác đơn giản: một nút Lưu, không lưu từng câu.
- Lịch sử làm bài không được hiển thị sai sau khi câu hỏi thay đổi.
- Không mở rộng phạm vi sang tóm tắt và slide.

## Các phương án
1. **Thay toàn bộ danh sách câu (`PUT`), xoá lịch sử làm bài khi lưu** – đơn giản, lịch sử không bao giờ lệch với câu hỏi; nhược điểm là mất điểm cũ (có cảnh báo trước).
2. **Chụp lại câu hỏi vào mỗi lần làm** – giữ lịch sử, nhưng cần migration backfill và hai nguồn dữ liệu khi hiển thị kết quả.
3. **Lưu thành quiz mới** – không mất gì, nhưng danh sách quiz phình ra và khó hiểu.

## Quyết định
Chọn **phương án 1**.

- `GET /quizzes/{id}/edit` trả câu hỏi **kèm** `answer_index` và `explanation` cho chủ sở hữu (không thuộc người dùng → 404). `GET /quizzes/{id}` giữ nguyên, không có đáp án. Chủ quiz xem được đáp án trước khi làm bài là chấp nhận được: quiz là của chính họ.
- `PUT /quizzes/{id}/questions` thay toàn bộ danh sách câu (1–30 câu) trong một transaction: câu có `id` được cập nhật, câu không `id` được thêm, câu vắng mặt bị xoá; thứ tự gửi lên là `position`. Lưu thành công thì **xoá mọi `quiz_attempts` của quiz** và đặt `quizzes.edited_at`.
- Chỉ sửa được quiz `completed` theo định dạng bài (ADR-0017); quiz cũ theo chương → 409 `QUIZ_NOT_EDITABLE`.
- `questions.page_ref` thành **không bắt buộc**; nếu có phải nằm trong khoảng trang của bài. Mỗi câu thuộc một bài trong phạm vi quiz (`chapter_idx` = `lessons.idx`) để điểm theo bài vẫn đúng.
- `questions.source`: `ai` · `edited` · `manual`. Lựa chọn do người dùng nhập **không xáo trộn**.
- Các quy tắc của ADR-0012 về chấm điểm phía server và câu bỏ trống tính sai vẫn giữ nguyên.

## Hệ quả
- **Tích cực:** Người dùng sửa được quiz sai; lịch sử luôn khớp câu hỏi; ít thay đổi lược đồ.
- **Tiêu cực:** Mất lịch sử làm bài khi lưu; "Tạo lại nội dung" bài giảng vẫn xoá cả quiz đã sửa.

## Ghi chú triển khai
- Migration thêm `questions.source`, `quizzes.edited_at`, bỏ NOT NULL của `questions.page_ref`.
- Ghi `position` mới qua giá trị tạm âm để không đụng ràng buộc `UNIQUE (quiz_id, position)`.
- Câu do sinh quiz mới vẫn tránh trùng với câu đã sửa (danh sách `avoid` đọc từ bảng `questions`).
