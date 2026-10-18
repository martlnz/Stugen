# Architecture Decision Records (ADR)

Tài liệu ghi lại các quyết định kiến trúc của dự án **Stugen** – website tạo học liệu từ giáo trình PDF, dựa trên [PRD](../product/PRD.md).

## Danh sách

| # | Tiêu đề | Trạng thái |
|---|---|---|
| [0001](0001-ghi-nhan-quyet-dinh-bang-adr.md) | Ghi nhận quyết định kiến trúc bằng ADR | Chấp nhận |
| [0002](0002-kien-truc-tong-the.md) | Kiến trúc tổng thể: Frontend – Backend API – AI Worker | Chấp nhận |
| [0003](0003-frontend-nextjs.md) | Frontend dùng Next.js + TypeScript | Chấp nhận |
| [0004](0004-backend-fastapi.md) | Backend API dùng FastAPI | Chấp nhận |
| [0005](0005-xac-thuc-google-oauth.md) | Xác thực Google do backend quản lý, phiên bằng cookie | Chấp nhận |
| [0006](0006-co-so-du-lieu-postgresql.md) | PostgreSQL + SQLAlchemy 2.0 + Alembic | Chấp nhận |
| [0007](0007-luu-tru-file-minio.md) | Lưu trữ file bằng MinIO (S3-compatible) | Chấp nhận |
| [0008](0008-xu-ly-bat-dong-bo-celery.md) | Xử lý bất đồng bộ bằng Celery + Redis | Chấp nhận · Sửa đổi một phần bởi 0015 |
| [0009](0009-trich-xuat-pdf-pymupdf.md) | Trích xuất và chia chương PDF bằng PyMuPDF | Chấp nhận |
| [0010](0010-chien-luoc-goi-llm.md) | Chiến lược gọi LLM: theo chương, đầu ra có cấu trúc | Chấp nhận · Sửa đổi một phần bởi 0015 |
| [0011](0011-dinh-dang-slide.md) | Slide lưu dạng JSON trung gian, render Reveal.js, xuất PPTX | Chấp nhận · Sửa đổi một phần bởi 0015 |
| [0012](0012-thiet-ke-quiz.md) | Quiz chấm điểm phía server, không lộ đáp án | Chấp nhận |
| [0013](0013-cap-nhat-trang-thai-polling.md) | Cập nhật trạng thái xử lý bằng polling | Chấp nhận |
| [0014](0014-trien-khai-docker-compose.md) | Triển khai bằng Docker Compose + reverse proxy | Chấp nhận |
| [0015](0015-lam-ro-pipeline-llm.md) | Làm rõ pipeline LLM: thử lại, slide, schema chương, ngôn ngữ, lưu theo chương | Chấp nhận |

## Nguồn chuẩn

Khi tài liệu nói khác nhau, ưu tiên theo bảng sau:

| Nội dung | Nguồn chuẩn |
|---|---|
| Lược đồ CSDL, cấu trúc JSONB | [data-model.md](../design/data-model.md) |
| Request/response, mã lỗi | [api.md](../design/api.md) |
| Lệnh phát triển, quy tắc code | [CLAUDE.md](../../CLAUDE.md) |
| Lý do của quyết định | ADR (ADR mới hơn thắng ADR cũ) |

Lược đồ và đoạn code minh hoạ trong ADR là bản phác thảo tại thời điểm quyết định, không cập nhật theo code.

## Thay đổi so với PRD

ADR-0005 thay thế cách xác thực ban đầu của PRD v2.0 (Auth.js gửi `id_token` mỗi request) bằng luồng OAuth do backend quản lý và cookie phiên. PRD đã được cập nhật lên v2.1 cho khớp.

ADR-0015 làm rõ chính sách thử lại LLM và cách sinh slide; PRD được cập nhật lên v2.2 cho khớp.

## Quy trình

Tạo ADR mới bằng cách sao chép `template.md`, đánh số tiếp theo và thêm vào bảng trên.
