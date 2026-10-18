# ADR-0009: Trích xuất và chia chương PDF bằng PyMuPDF

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-18

## Bối cảnh
Chất lượng tóm tắt/slide/quiz phụ thuộc vào việc trích xuất văn bản đúng và chia thành các phần có nghĩa. PRD giới hạn ở PDF có lớp văn bản, chưa hỗ trợ OCR. Mỗi đoạn nội dung cần giữ số trang để tham chiếu.

## Các phương án
1. **PyMuPDF (fitz)** – rất nhanh, đọc được mục lục (bookmark), thông tin font/cỡ chữ, xử lý tiếng Việt tốt.
2. **pdfplumber / pdfminer.six** – chi tiết về bố cục nhưng chậm hơn nhiều.
3. **Unstructured / Docling / Marker** – hiểu bố cục tốt hơn nhưng nặng (mô hình ML), quá mức cho MVP.

## Quyết định
Chọn **PyMuPDF**. (Lưu ý giấy phép AGPL — phù hợp với dự án phi thương mại mã nguồn mở.)

### Trích xuất
- Lấy văn bản từng trang bằng `page.get_text("text", sort=True)`, chuẩn hoá Unicode NFC (quan trọng với tiếng Việt), bỏ header/footer lặp lại (dòng xuất hiện giống nhau ở ≥ 50% số trang).
- Nếu tổng ký tự < 100 × số trang → coi là PDF scan, báo lỗi: *"Giáo trình có vẻ là bản scan, hiện chưa được hỗ trợ."*

### Chia chương (theo thứ tự ưu tiên)
1. **Bookmark** (`doc.get_toc()`): dùng các mục cấp 1 (nếu chỉ có 1–2 mục cấp 1 thì dùng cấp 2).
2. **Heuristic tiêu đề**: dòng có cỡ chữ lớn hơn hẳn trung vị, hoặc khớp mẫu `^(Chương|CHƯƠNG|Chapter|Bài|Phần)\s+\w+`.
3. **Chia đều**: mỗi phần ~15 trang.

### Chuẩn hoá kích thước
- Chương quá dài (> ~12.000 token ước tính) → chia nhỏ theo trang thành nhiều phần con.
- Chương quá ngắn (< 1 trang) → gộp với chương kế tiếp.
- Tối đa 20 chương; vượt quá thì gộp các chương liền kề.

Kết quả lưu vào bảng `chapters` (idx, title, page_start, page_end, text). Văn bản giữ đánh dấu `[[trang N]]` ở đầu mỗi trang để LLM trích số trang tham chiếu.

## Hệ quả
- **Tích cực:** Nhanh (vài giây cho 200 trang), không cần GPU, tham chiếu trang chính xác.
- **Tiêu cực:** Bảng biểu, công thức dạng ảnh, PDF hai cột phức tạp có thể trích xuất kém; không hỗ trợ scan. Có thể thêm OCR (Tesseract `vie`) hoặc Docling trong ADR sau.
