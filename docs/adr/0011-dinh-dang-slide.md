# ADR-0011: Slide lưu dạng JSON trung gian, render bằng Reveal.js, xuất PPTX bằng python-pptx

- **Trạng thái:** Chấp nhận · Sửa đổi một phần bởi [ADR-0015](0015-lam-ro-pipeline-llm.md), [ADR-0017](0017-bai-nho-chon-pham-vi-slide-tu-van-ban-goc.md)
- **Ngày:** 2026-10-18

## Bối cảnh
PRD yêu cầu xem slide trực tuyến (trình chiếu) và tải về PPTX. Hai đầu ra này phải nhất quán nội dung.

## Các phương án
1. **LLM sinh trực tiếp HTML/Markdown slide (Marp, Slidev)** – nhanh nhưng khó xuất PPTX đẹp, khó kiểm tra cấu trúc.
2. **Sinh PPTX trước, chuyển sang ảnh để xem web** – cần LibreOffice trong container, nặng và chậm.
3. **JSON trung gian có cấu trúc**, từ đó render ra cả web và PPTX.

## Quyết định
Chọn **phương án 3**.

### Schema
```python
class Slide(BaseModel):
    layout: Literal["title", "agenda", "section", "bullets", "summary"]
    title: str = Field(max_length=80)
    subtitle: str | None = None
    bullets: list[str] = Field(default_factory=list, max_length=6)
    notes: str | None = None          # ghi chú người thuyết trình
    page_refs: list[int] = []

class SlideDeck(BaseModel):
    version: Literal[1] = 1
    title: str
    slides: list[Slide]
```
- `bullets` mỗi dòng ≤ 120 ký tự; hỗ trợ LaTeX inline `$...$`.
- Cấu trúc bộ slide: `title` → `agenda` → với mỗi chương (`section` + 1–3 `bullets`) → `summary`.
- Slide `title`, `agenda` được sinh bằng code; LLM chỉ sinh slide nội dung từng chương.

### Hiển thị web
- Frontend map từng `layout` sang component React, đặt trong Reveal.js.
- Công thức hiển thị bằng plugin KaTeX của Reveal.
- Một theme mặc định, hỗ trợ sáng/tối.

### Xuất PPTX
- Worker dùng **python-pptx** với một file template `.pptx` có sẵn các layout tương ứng, sinh file ngay sau khi tạo JSON và lưu vào MinIO (`slides.pptx`).
- Công thức LaTeX trong PPTX được hiển thị dạng văn bản thô (python-pptx không hỗ trợ OMML dễ dàng) — chấp nhận ở MVP.
- `notes` ghi vào speaker notes.

## Hệ quả
- **Tích cực:** Một nguồn dữ liệu cho hai đầu ra; dễ validate; dễ thêm chức năng chỉnh sửa slide sau này (chỉ sửa JSON rồi sinh lại PPTX).
- **Tiêu cực:** Không có hình ảnh/biểu đồ trong slide ở MVP; giao diện web và PPTX không giống hệt nhau; công thức trong PPTX chưa đẹp.
