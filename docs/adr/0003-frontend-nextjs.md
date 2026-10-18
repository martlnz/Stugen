# ADR-0003: Frontend dùng Next.js + TypeScript

- **Trạng thái:** Chấp nhận · Sửa đổi một phần bởi [ADR-0016](0016-cong-cu-ten-tai-nguyen-deepseek-giay-phep.md)
- **Ngày:** 2026-10-18
- **Ghi chú:** Lệnh sinh kiểu API chuẩn là `just gen-api` (xem `CLAUDE.md`; ADR-0016 thay cho `make gen-api`), lấy schema từ `http://localhost/api/openapi.json`.

## Bối cảnh
PRD cho phép chọn công nghệ frontend tốt nhất. Giao diện cần: danh sách thư viện, upload kéo-thả, hiển thị Markdown + công thức toán, trình chiếu slide, làm quiz; chạy tốt trên mobile.

## Yếu tố quyết định
- Hệ sinh thái component phong phú, tài liệu tốt.
- Type-safe khi làm việc với API.
- Không cần SEO phức tạp (hầu hết trang sau đăng nhập), nhưng cần routing tốt.

## Các phương án
1. **Next.js (App Router)** – framework React phổ biến nhất, routing theo file, có thể build standalone chạy Node.
2. **Vite + React SPA** – nhẹ, đơn giản, build ra file tĩnh; phải tự chọn router.
3. **SvelteKit / Nuxt** – tốt nhưng hệ sinh thái component (shadcn, Reveal wrapper…) nhỏ hơn.

## Quyết định
Chọn **Next.js (App Router) + TypeScript** với bộ thư viện:

| Nhu cầu | Thư viện |
|---|---|
| UI | Tailwind CSS + shadcn/ui |
| Gọi API, cache, polling | TanStack Query |
| Kiểu dữ liệu API | Sinh từ OpenAPI của FastAPI bằng `openapi-typescript` |
| Form & validate | react-hook-form + zod |
| Upload kéo-thả | react-dropzone |
| Markdown + công thức | react-markdown + remark-math + rehype-katex |
| Trình chiếu slide | Reveal.js |
| Xem PDF gốc | react-pdf (pdf.js) |
| Icon | lucide-react |

Phần lớn trang là **Client Components** gọi API qua cookie phiên (xem ADR-0005). Không dùng Server Actions để truy cập DB — mọi dữ liệu đi qua FastAPI để chỉ có một nguồn logic.

Không dùng Auth.js (khác với PRD 5.1) vì xác thực do backend quản lý.

## Hệ quả
- **Tích cực:** Phát triển nhanh, giao diện đẹp sẵn, kiểu dữ liệu đồng bộ với backend.
- **Tiêu cực:** Next.js nặng hơn mức cần cho một SPA thuần; chấp nhận để đổi lấy routing, layout và khả năng mở rộng.

## Ghi chú triển khai
- Build với `output: "standalone"` để image Docker nhỏ.
- Script `npm run gen:api` sinh `src/lib/api-types.ts` từ `http://api/openapi.json`.
- Route chính: `/`, `/library`, `/upload`, `/lectures/[id]` (tab summary/slides/quiz), `/quizzes/[id]`, `/attempts/[id]`.
