# Hạn chế đã biết – v0.1.0

> Ghi lại sau khi chạy trọn luồng với 3 PDF mẫu (`samples/`) ngày 19/10/2026 (Khối 8, [kế hoạch](plans/plan-1-ngay.md)).

## Kết quả chạy thử

| PDF | Kết quả | Ghi chú |
|---|---|---|
| `short-10p.pdf` (10 trang, không bookmark) | ✅ Hoàn tất | Chia 5 chương theo heuristic tiêu đề; chương 4 và 5 cùng bắt đầu ở trang 9 được cắt đúng tại dòng tiêu đề. ~35 giây. |
| `toc-50p.pdf` (51 trang, bookmark) | ✅ Hoàn tất | 7 chương theo bookmark, bỏ "Mục lục" và "Nguồn nội dung"; header/footer "Trang N" được lọc. ~33 giây (yêu cầu PRD: 2–3 phút). |
| `scan.pdf` (ảnh) | ✅ Báo lỗi đúng | `failed` ở bước `extracting`, mã `PDF_NO_TEXT`, thông điệp tiếng Việt; không hiện nút "Thử lại". |
| File không phải PDF | ✅ | `400 INVALID_FILE_TYPE` ngay khi tải lên. |

Giao diện đã kiểm tra bằng Chromium headless (desktop 1280px và mobile 390px): thư viện, tải lên, tiến trình, tóm tắt + KaTeX, slide Reveal.js, PDF gốc, làm quiz, kết quả – không có lỗi console.

## Hạn chế

### Chức năng chưa làm (để sau theo kế hoạch)
- **Giới hạn tần suất** (api.md mục 1.7) chưa triển khai; chưa trả `429`.
- **Celery beat / `cleanup_orphans`** chưa chạy: phiên hết hạn và file MinIO mồ côi (khi xoá file lỗi) chưa được dọn tự động.
- **Bảng `llm_calls`** chưa tạo; token chỉ ghi trong log worker.
- **Provider `anthropic`** chưa có; dùng `openai_compatible` (DeepSeek/Ollama) hoặc `openai`.
- **Tìm kiếm thư viện** dùng `ILIKE`, giao diện chưa có ô tìm/lọc/sắp xếp (API đã hỗ trợ `q`, `status`, `sort`). Index trigram đã có sẵn.
- **HTTPS production**: `Caddyfile` đang cố định `http://`; khi triển khai thật đổi địa chỉ site thành `{$DOMAIN}`.

### Pipeline AI
- **Giới hạn độ dài hiển thị do code cắt gọn**: DeepSeek thường vượt giới hạn 120 ký tự/bullet, 10 thuật ngữ… và sửa lại vẫn sai, nên schema LLM tự cắt theo ranh giới từ (thêm "…") và giữ số phần tử tối đa thay vì báo lỗi. Lỗi cấu trúc, JSON hỏng, số trang ngoài khoảng chương vẫn được sửa 1 lần như ADR-0015.
- **Chia chương theo trang/dòng**: chưa nhận diện tiêu đề nhiều cấp, PDF hai cột, bảng biểu, công thức dạng ảnh.
- **Ước lượng PDF scan** theo tổng ký tự (< 100 ký tự/trang); PDF lai (một phần scan) có thể lọt qua và cho tóm tắt thiếu.
- **Ngôn ngữ**: cấu hình toàn hệ thống (`CONTENT_LANGUAGE`), chưa chọn theo bài giảng.

### Giao diện
- Slide web dùng theme Reveal `white` (tiêu đề in hoa); chưa có chế độ tối cho slide.
- Ghi chú thuyết trình chỉ có trong file PPTX (chưa nạp plugin notes của Reveal).
- PPTX dùng template mặc định của python-pptx; công thức LaTeX hiển thị dạng văn bản thô (ADR-0011).
- Trang thư viện tải tối đa 100 bài giảng (chưa phân trang trên giao diện).

### Môi trường dev (Windows)
- `docker compose build web` có lúc làm Docker Desktop (WSL) dừng đột ngột khi build Next.js. Đã giới hạn `NODE_OPTIONS=--max-old-space-size=2048` trong `frontend/Dockerfile`; nếu vẫn gặp, khởi động lại Docker Desktop rồi build lại.
