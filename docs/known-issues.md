# Hạn chế đã biết – v0.2.0

> Cập nhật sau khi chạy luồng v0.2 (ADR-0017) với PDF mẫu ngày 19/10/2026.

## Kết quả chạy thử

| PDF | Kết quả |
|---|---|
| `toc-50p.pdf` (51 trang, bookmark cấp 1) | Mục lục sẵn sàng sau ~4 giây: 7 chương, 30 bài (tách theo tiêu đề phụ cỡ chữ lớn, bỏ "Mục lục", "Nguồn nội dung"). Mỗi bài 3–4 trang tạo xong tóm tắt + slide + quiz trong ~40 giây (DeepSeek). |
| `short-10p.pdf` (10 trang, không bookmark) | 5 chương theo tiêu đề "Chương N", 6 bài; chương 4 và 5 cùng trang 9 được cắt đúng dòng tiêu đề. |
| `scan.pdf` | `failed`, mã `PDF_NO_TEXT`, thông điệp tiếng Việt. |
| Bài giảng tạo ở v0.1 | Hiện banner "Tạo lại nội dung"; tạo lại giữ PDF, xoá nội dung cũ, tách mục lục mới. |

Giao diện kiểm tra bằng Chromium headless (1366px và 390px): thư viện, mục lục + chọn bài, tạo học liệu (polling), tóm tắt theo mục, slide có giải thích + ví dụ, quiz bài, quiz tổng hợp, kết quả theo bài, bài giảng định dạng cũ – không có lỗi console.

## Hạn chế

### Tách bài
- Tiêu đề phụ nhận theo **cỡ chữ** (≥ 1,1 × cỡ thân bài) hoặc đánh số `1.2`; PDF dùng chữ đậm cùng cỡ cho tiêu đề phụ sẽ không nhận ra → chương ≤ 6 trang thành một bài, chương dài hơn nhờ LLM tách (mô hình nhanh, chỉ gửi vài dòng đầu mỗi trang).
- Mục quá ngắn (< ~1.500 ký tự) được gộp với mục kế tiếp; tên bài gộp có dạng "A; B" và được thay bằng tên LLM đề xuất sau khi tạo học liệu (cũng áp dụng cho tên ngắn < 20 ký tự như "Lịch sử"). Trước khi tạo học liệu, người dùng vẫn thấy tên gốc.
- Ranh giới bài tính theo dòng/trang; PDF hai cột, bảng biểu, công thức dạng ảnh có thể trích xuất kém.

### Nội dung AI
- Văn bản gốc của bài được gửi cho LLM 3 lần (tóm tắt, slide, quiz) → chi phí token mỗi trang cao hơn v0.1, đổi lại chỉ trả cho bài được chọn.
- Ví dụ minh hoạ trong slide có thể do AI tự tạo (đã gắn nhãn "Ví dụ minh hoạ" và cảnh báo "Nội dung do AI tạo").
- Giới hạn độ dài hiển thị (bullet 120 ký tự, giải thích 300, ví dụ 400…) do code cắt gọn kèm "…"; lỗi cấu trúc/số trang vẫn sửa 1 lần (ADR-0015).
- Số trang mục nhỏ do LLM đọc từ `[[trang N]]`, code chỉ kẹp vào khoảng trang của bài, không kiểm chứng nội dung.
- Không còn đoạn tổng quan toàn giáo trình (chỉ có tổng quan từng bài).

### Chức năng chưa làm (để sau)
- Giới hạn tần suất (api.md 1.7), Celery beat / `cleanup_orphans`, bảng `llm_calls`, provider `anthropic`.
- Ô tìm kiếm/lọc ở thư viện (API đã hỗ trợ `q`, `status`, `sort`).
- HTTPS production (`Caddyfile` đang cố định `http://`).
- Huỷ bài đang tạo; chọn ngôn ngữ theo bài giảng.

### Giao diện
- Slide web theme Reveal `white`; ghi chú thuyết trình chỉ có trong PPTX.
- PPTX dùng template mặc định của python-pptx; LaTeX hiển thị dạng văn bản thô (ADR-0011).
- Thư viện tải tối đa 100 bài giảng.

### Môi trường dev (Windows)
- `docker compose build web` có lúc làm Docker Desktop (WSL) dừng; đã giới hạn `NODE_OPTIONS=--max-old-space-size=2048`. Nếu gặp lại: thoát Docker Desktop, `wsl --shutdown`, mở lại rồi `just up`.
