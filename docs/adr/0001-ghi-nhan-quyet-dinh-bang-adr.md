# ADR-0001: Ghi nhận quyết định kiến trúc bằng ADR

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-18

## Bối cảnh
Dự án phi thương mại, có thể có nhiều người đóng góp theo thời gian. Lý do của các lựa chọn công nghệ dễ bị quên nếu chỉ nằm trong trao đổi miệng hoặc chat.

## Quyết định
Mỗi quyết định ảnh hưởng tới cấu trúc hệ thống, công nghệ, định dạng dữ liệu hoặc giao tiếp giữa các thành phần được ghi thành một ADR theo mẫu `template.md` (biến thể của mẫu Michael Nygard), lưu trong `docs/adr/` của repository.

- ADR đã chấp nhận **không sửa nội dung**; nếu thay đổi quyết định thì tạo ADR mới và đánh dấu ADR cũ là "Bị thay thế".
- Đánh số tăng dần 4 chữ số, tên file dạng `NNNN-tieu-de-ngan.md`.

## Hệ quả
- **Tích cực:** Người mới hiểu nhanh vì sao hệ thống được thiết kế như vậy; tránh tranh luận lại các quyết định cũ.
- **Tiêu cực:** Tốn thêm chút thời gian ghi chép.
