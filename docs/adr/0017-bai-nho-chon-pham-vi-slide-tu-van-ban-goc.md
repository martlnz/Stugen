# ADR-0017: Chia giáo trình thành bài nhỏ, người dùng chọn bài để tạo học liệu, slide sinh từ văn bản gốc

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-19
- **Sửa đổi một phần:** ADR-0008 (task), ADR-0010 (pipeline, quy tắc prompt cho slide), ADR-0011 (bộ slide, schema), ADR-0012 (quiz mặc định), ADR-0015 (quyết định 2, 3, 5)

## Bối cảnh
Phản hồi đầu tiên của chủ dự án với v0.1.0:
- Tải cả giáo trình lên thì hệ thống tóm tắt và tạo quiz cho toàn bộ một lần. Người dùng muốn **chọn phạm vi** và muốn giáo trình được **tách thành các bài nhỏ, mỗi bài có quiz riêng** để phủ trọn kiến thức.
- Tóm tắt in tên file gốc; tiêu đề slide lấy tên file hoặc tên máy móc ("Phần 1 (trang 1–15)").
- Mục lục chỉ có cấp chương, cần thấy các mục nhỏ kèm khoảng trang.
- Slide chỉ chép lại tóm tắt; cần trình bày lại chi tiết, dễ hiểu, có ví dụ.

Nguyên nhân gốc:
1. Đơn vị xử lý là **chương** (tới ~36.000 ký tự), mỗi chương chỉ 1–8 ý, quiz mặc định 10 câu cho cả giáo trình, quiz còn cắt văn bản dài → bỏ sót nội dung, không chọn được phạm vi.
2. ADR-0015 quyết định 2 cho LLM sinh slide **từ bản tóm tắt**, 1–3 slide/chương → không có chất liệu để giải thích hay ví dụ. ADR-0010 cấm mọi kiến thức ngoài tài liệu, kể cả ví dụ minh hoạ.
3. Tiêu đề lấy từ metadata/tên file.

## Yếu tố quyết định
- Người dùng chỉ trả chi phí AI (thời gian, token) cho phần muốn học.
- Mỗi đơn vị đủ nhỏ để tóm tắt và hỏi phủ hết nội dung.
- Slide là phiên bản dễ hiểu của tài liệu, không phải bản tóm tắt thứ hai.
- Không bịa kiến thức trong tóm tắt và quiz.

## Các phương án
1. **Giữ xử lý toàn bộ, chỉ tăng số ý/câu hỏi** – đơn giản nhưng không chọn được phạm vi, chi phí tăng theo cả giáo trình.
2. **Tạo hết tự động nhưng hiển thị theo bài** – vẫn tốn chi phí cho phần không học.
3. **Tách mục lục ngay khi tải lên, người dùng chọn bài rồi mới tạo học liệu theo từng bài** – đúng yêu cầu, rẻ, mỗi bài nhỏ.

## Quyết định
Chọn **phương án 3**.

### Đơn vị "bài" (lesson)
- Cấu trúc: giáo trình → chương (`chapters`, như ADR-0009) → **bài** (`lessons`, 2–8 trang).
- Tách bài: bookmark cấp 2 → tiêu đề phụ (cỡ chữ lớn hơn thân bài, nhỏ hơn tiêu đề chương, hoặc đánh số `1.2`) → chương ≤ 6 trang là một bài → chương dài không có tiêu đề phụ thì **LLM (mô hình nhanh) đề xuất ranh giới bài và tên**, code kiểm tra số trang; lỗi thì chia đều ~4 trang.
- Chương có tên máy móc (chia đều theo trang) được đổi tên theo nội dung do LLM đề xuất.

### Luồng
1. `process_lecture` chỉ còn bước `extracting`: ghi `chapters` + `lessons`, bài giảng `completed` = **mục lục đã sẵn sàng** (vài giây).
2. Người dùng chọn bài → `generate_lesson(lesson_id)` cho từng bài: tóm tắt → slide (+ PPTX) → quiz mặc định. Mỗi bước bỏ qua nếu đã có (idempotent như ADR-0015).
3. Lỗi LLM làm **bài** `failed` (không phải cả bài giảng); tạo lại bằng cách chọn lại bài đó.

### Tóm tắt bài
- LLM trả `overview`, `sections[{title, page_start, page_end, key_points}]`, `terms`. Số trang mục nhỏ do LLM đọc từ `[[trang N]]` (thay cho "Để sau" của ADR-0015); **code kẹp vào khoảng trang của bài và sắp xếp**, không coi là lỗi.
- Markdown lắp bằng code, không có tên file/tên giáo trình.

### Slide bài
- LLM nhận **văn bản gốc của bài + danh sách mục nhỏ** (thay quyết định 2 của ADR-0015), sinh 3–10 slide tuỳ độ dài; mỗi slide có tiêu đề nêu đúng kiến thức chính, gạch đầu dòng, đoạn giải thích dễ hiểu (`explanation`), ví dụ (`example`) và ghi chú.
- **Ngoại lệ với ADR-0010:** riêng slide, AI được tự tạo ví dụ minh hoạ khi giáo trình không có, phải ghi rõ "Ví dụ minh hoạ" và không mâu thuẫn tài liệu. Tóm tắt và quiz vẫn chỉ dùng thông tin trong giáo trình.
- Code ghép slide tiêu đề (tên bài), mục lục (mục nhỏ kèm trang), slide "Ghi nhớ" (từ `takeaways` của LLM).

### Quiz
- Mỗi bài có quiz mặc định, số câu = clamp(round(số trang × 1,5), 5, 15), rải đều các mục nhỏ. Bỏ ràng buộc số câu 10/20/30 (thay bằng 1–30).
- Quiz tổng hợp: người dùng chọn các bài làm phạm vi và số câu; phân bổ theo độ dài như ADR-0012.

### Dữ liệu cũ
- `summaries`, `slide_decks`, `chapters.summary/slides` không còn được sinh. Bài giảng định dạng cũ có nút "Tạo lại nội dung" (`POST /lectures/{id}/regenerate`) xoá nội dung đã sinh và tách mục lục lại.

## Hệ quả
- **Tích cực:** chọn được phạm vi, chi phí theo phần học; nội dung phủ trọn từng bài; mục lục chi tiết có trang; slide giàu giải thích và ví dụ; lỗi cô lập theo bài.
- **Tiêu cực:** văn bản gốc được gửi cho LLM 3 lần mỗi bài (tóm tắt, slide, quiz) → nhiều token hơn trên mỗi trang đã chọn; không còn tổng quan toàn giáo trình; ví dụ do AI tạo có thể chưa chính xác (đã gắn nhãn và cảnh báo "Nội dung do AI tạo").

## Ghi chú triển khai
- Bảng `lessons`, cột `quizzes.lesson_id`, `quizzes.lesson_ids`: xem [data-model.md](../design/data-model.md) 1.3.
- Endpoint: `GET /lectures/{id}/outline`, `POST /lectures/{id}/lessons/generate`, `/lessons/{id}/summary|slides|slides.pptx|quizzes`, `POST /lectures/{id}/regenerate`: xem [api.md](../design/api.md) 2.0.
- Prompt mới: `outline_v1.j2`, `lesson_summary_v1.j2`, `lesson_slides_v1.j2`, `lesson_quiz_v1.j2`.
