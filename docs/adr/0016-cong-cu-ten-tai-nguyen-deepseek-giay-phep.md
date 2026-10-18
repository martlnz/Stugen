# ADR-0016: Chạy lệnh bằng `just`, đặt tên tài nguyên `stugen`, dùng DeepSeek làm LLM mặc định, giấy phép AGPL-3.0

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-19
- **Sửa đổi một phần:** ADR-0003 (lệnh sinh kiểu TS), ADR-0007 (tên bucket), ADR-0010 (ghi chú triển khai nhà cung cấp LLM)

## Bối cảnh
Trước khi viết code còn năm điểm chưa chốt (`docs/progress.md` mục 5–6):
- Máy phát triển là Windows và không có `make`, trong khi `CLAUDE.md` dùng `make up/test/lint/...`. Máy đã cài sẵn `just`.
- Tên mặc định của DB là `app`, của bucket MinIO là `lectures`. Tên `lectures` trùng tên bảng và tên prefix trong key, dễ nhầm.
- LLM đã chọn là DeepSeek (provider `openai_compatible`). DeepSeek có vài khác biệt so với OpenAI mà tài liệu chưa ghi.
- Repo sẽ chuyển sang public nên cần có giấy phép. PyMuPDF dùng giấy phép AGPL-3.0 (ADR-0009).

## Yếu tố quyết định
- Chạy được ngay trên Windows, không phụ thuộc Git Bash/WSL.
- Tên tài nguyên rõ ràng, không trùng tên bảng.
- Pipeline LLM chạy ổn định với DeepSeek nhưng vẫn đổi được nhà cung cấp chỉ bằng cấu hình.
- Giấy phép tương thích với các thư viện phụ thuộc.

## Các phương án
**Chạy lệnh**
1. **GNU Make** – giữ nguyên tài liệu; phải cài thêm, recipe chạy qua `sh` nên dễ lỗi cú pháp trên Windows.
2. **`just`** – đã cài sẵn, cú pháp gọn, đặt được shell PowerShell cho Windows; phải sửa tài liệu.
3. **Script `tasks.ps1`** – không cần công cụ ngoài; khó dùng trên Linux/macOS.

**Giấy phép**
1. **MIT/Apache-2.0** – dễ dãi hơn, nhưng sản phẩm phân phối kèm PyMuPDF vẫn chịu ràng buộc AGPL nên không có lợi thực tế.
2. **AGPL-3.0** – tương thích PyMuPDF, đúng tinh thần phi thương mại và mở mã nguồn.

## Quyết định
1. **Dùng `just`** với `justfile` ở gốc repo. Tên recipe giữ như cũ: `just up`, `just down`, `just logs`, `just migrate`, `just revision "mô tả"`, `just test`, `just lint`, `just fmt`, `just gen-api`. `justfile` đặt `set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]`.
2. **`just test` và `just lint` cho backend chạy trong container `api`** (Python 3.12 theo image). Máy phát triển không bắt buộc cài Python 3.12. Lint frontend (`eslint`, `tsc`) chạy bằng Node trên máy.
3. **Đổi tên tài nguyên thành `stugen`:** user và database PostgreSQL `stugen`, bucket MinIO `stugen`. Cấu trúc key trong bucket giữ nguyên (`users/{user_id}/lectures/{lecture_id}/...`).
4. **DeepSeek là LLM mặc định** qua `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL=https://api.deepseek.com`, `LLM_MODEL=deepseek-v4-pro`, `LLM_MODEL_FAST=deepseek-flash`. Tên `deepseek-v4-flash` đã ngừng (vẫn được chuyển hướng sang `deepseek-flash`).
5. **Giấy phép AGPL-3.0** (file `LICENSE`), repo GitHub public.

## Hệ quả
- **Tích cực:** chạy lệnh được ngay trên Windows; test chạy cùng phiên bản Python với production; tên tài nguyên không trùng tên bảng; giấy phép khớp với PyMuPDF.
- **Tiêu cực:** người đóng góp phải cài `just`. Đã có `.env` cũ thì phải tự đổi tên DB/bucket (xem `docs/progress.md`). Ai tự host bản sửa đổi phải công bố mã nguồn (AGPL).

## Ghi chú triển khai
DeepSeek khác OpenAI ở các điểm sau. Provider `openai_compatible` phải xử lý được:
- Chỉ có `response_format={"type": "json_object"}`, không có `json_schema`. Provider có cờ `supports_json_schema`. Khi cờ tắt, prompt phải chứa chữ "json" và một ví dụ JSON mẫu, sinh từ schema Pydantic.
- API đôi khi trả `content` rỗng. Trường hợp này coi là đầu ra sai định dạng và sửa 1 lần như ADR-0015.
- Mặc định bật chế độ thinking. Tắt bằng `extra_body={"thinking": {"type": "disabled"}}` để giảm độ trễ và chi phí.
- Đặt `max_tokens` khoảng 4–8K để JSON không bị cắt giữa chừng. Timeout mỗi lời gọi khoảng 120 giây.
- Nội dung giáo trình được gửi tới dịch vụ AI bên thứ ba. Giao diện và PRD (mục 4) phải ghi rõ điều này.
