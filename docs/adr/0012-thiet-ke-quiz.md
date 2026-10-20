# ADR-0012: Quiz chấm điểm phía server, không lộ đáp án

- **Trạng thái:** Chấp nhận · Sửa đổi một phần bởi [ADR-0017](0017-bai-nho-chon-pham-vi-slide-tu-van-ban-goc.md), [ADR-0018](0018-chinh-sua-quiz.md)
- **Ngày:** 2026-10-18

## Bối cảnh
PRD: câu hỏi trắc nghiệm 4 lựa chọn, 10/20/30 câu, có giải thích và số trang, lưu lịch sử điểm. Người dùng có thể sinh thêm quiz mới cho cùng một bài giảng.

## Quyết định

### Sinh câu hỏi
- Khi xử lý bài giảng: tự sinh **một quiz mặc định 10 câu**.
- `POST /api/lectures/{id}/quizzes {num_questions: 10|20|30}` tạo quiz mới với `status='queued'` và đẩy task `generate_quiz` (ADR-0008); sinh từ bảng `chapters`, không đọc lại PDF.
- Phân bổ số câu cho các chương tỉ lệ theo độ dài văn bản (tối thiểu 1 câu/chương nếu đủ số câu).
- Khi sinh quiz mới, truyền danh sách câu hỏi đã có của bài giảng vào prompt để tránh trùng lặp.

### Schema đầu ra LLM
```python
class Question(BaseModel):
    question: str
    options: list[str] = Field(min_length=4, max_length=4)
    answer_index: int = Field(ge=0, le=3)
    explanation: str
    page_ref: int
```
Validate bổ sung: 4 lựa chọn khác nhau; `page_ref` nằm trong khoảng trang của chương.

### Trộn đáp án
LLM có xu hướng đặt đáp án đúng ở cùng vị trí. Sau khi sinh, server **xáo trộn lựa chọn** và cập nhật `answer_index` trước khi lưu.

### Không lộ đáp án
- `GET /api/quizzes/{id}` chỉ trả `id, position, question, options, page_ref`; **không** trả `answer_index` và `explanation`.
- `POST /api/quizzes/{id}/attempts {answers: {question_id: option_index}}`: server chấm điểm, lưu `quiz_attempts`, trả về kết quả từng câu kèm đáp án đúng và giải thích.
- Câu bỏ trống tính sai.

### Lịch sử
- `GET /api/quizzes/{id}/attempts` trả danh sách lần làm (điểm, thời gian).
- `GET /api/attempts/{id}` trả chi tiết một lần làm để xem lại.

## Hệ quả
- **Tích cực:** Không thể xem đáp án bằng DevTools; điểm số đáng tin; tránh lệch vị trí đáp án.
- **Tiêu cực:** Chế độ "hiện đáp án ngay sau mỗi câu" cần thêm endpoint kiểm tra từng câu — để sau MVP.
