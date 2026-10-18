# ADR-0015: Làm rõ pipeline LLM – thử lại, slide, schema chương, ngôn ngữ, lưu kết quả theo chương

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-18
- **Sửa đổi một phần:** ADR-0008, ADR-0010, ADR-0011

## Bối cảnh
Rà soát tài liệu trước khi viết code phát hiện các điểm mâu thuẫn hoặc còn thiếu:
- PRD 5.3 ghi "thử lại tối đa 2 lần", ADR-0010 và `CLAUDE.md` ghi "thử lại 1 lần kèm thông báo lỗi"; ADR-0008 ghi Celery tự retry 2 lần cho lỗi tạm thời.
- ADR-0011 nói chỉ slide `title`/`agenda` do code sinh; ADR-0010 tính "1 lần/chương + 1 lần mở/kết"; kế hoạch lại ghi cả slide `summary` do code sinh.
- ADR-0010 cho `ChapterSummary` có `pages[]`, data-model dùng `page_start`/`page_end`.
- ADR-0010 ghi "ngôn ngữ của tài liệu hoặc tiếng Việt theo cấu hình" nhưng không có biến cấu hình.
- ADR-0008/0010 yêu cầu chạy lại không gọi lại chương đã xong, nhưng lược đồ chỉ ghi `summaries` một lần ở cuối, không có chỗ lưu kết quả từng chương.

## Yếu tố quyết định
- Ít lượt gọi LLM nhất có thể (chi phí, thời gian, giảm "bịa").
- Việc code làm chắc chắn được thì không giao cho LLM.
- Chạy lại task thực sự tiết kiệm (idempotent theo chương).
- Vừa sức kế hoạch MVP 1 ngày.

## Quyết định

### 1. Hai loại thử lại tách biệt
| Loại lỗi | Ví dụ | Xử lý | Nơi thực hiện |
|---|---|---|---|
| Tạm thời | timeout, mất mạng, 429, 5xx | Thử lại **2 lần**, backoff + jitter | Trong `LLMClient` (dùng `max_retries` của SDK) |
| Đầu ra sai | JSON hỏng, sai schema Pydantic | **Sửa 1 lần**: gọi lại kèm thông báo lỗi validate | `LLMClient.generate_json()` |

- Hết lượt → ném lỗi tương ứng `LLM_UNAVAILABLE` / `LLM_INVALID_OUTPUT` (data-model mục 6), lecture `failed`.
- Celery chỉ tự retry task cho **lỗi hạ tầng** (mất kết nối DB, Redis, MinIO), không retry vì lỗi LLM. Lý do: chạy lại cả task tốn thời gian và dễ chạm `task_time_limit`.

### 2. Phân công sinh slide
| Slide | Nguồn |
|---|---|
| `title` | Code – tiêu đề bài giảng |
| `agenda` | Code – danh sách tiêu đề chương |
| `section` | Code – tiêu đề chương |
| `bullets` (1–3 slide/chương) | **LLM** – đầu vào là `ChapterSummary` của chương, không phải văn bản gốc |
| `summary` | Code – từ `learning_objectives` của bước tổng quan |

- Số lượt gọi LLM cho slide: **1 lần/chương**, chạy song song (giới hạn `LLM_MAX_CONCURRENCY`). Bỏ lượt "mở/kết" trong ADR-0010.
- Để vừa một slide, `Overview.learning_objectives` tối đa 6 mục, mỗi mục ≤ 120 ký tự.

### 3. Schema tóm tắt chương
LLM **không** trả số trang của chương (code đã biết từ bảng `chapters`, tránh bịa):

```python
class Term(BaseModel):
    term: str
    definition: str

class ChapterSummaryLLM(BaseModel):      # đầu ra LLM
    key_points: list[str] = Field(min_length=1, max_length=8)
    terms: list[Term] = Field(default_factory=list, max_length=10)

class ChapterSummary(ChapterSummaryLLM):  # lưu DB (summaries.chapters)
    idx: int
    title: str
    page_start: int
    page_end: int
```
`idx`, `title`, `page_start`, `page_end` do code ghép từ bảng `chapters`.

### 4. Ngôn ngữ nội dung
- Biến môi trường `CONTENT_LANGUAGE`: `vi` (mặc định) | `source` (theo ngôn ngữ tài liệu). MVP cấu hình toàn hệ thống.
- Quy tắc prompt khi `vi`: viết tiếng Việt; **thuật ngữ chuyên ngành giữ nguyên gốc kèm giải nghĩa**, ví dụ "Primary key (khoá chính)"; công thức giữ LaTeX.
- Lý do: người dùng chính là sinh viên Việt Nam, giao diện tiếng Việt; nhiều giáo trình bằng tiếng Anh nên cần giữ thuật ngữ gốc để đối chiếu tài liệu và đề thi.

### 5. Lưu kết quả theo chương
Thêm hai cột nullable vào bảng `chapters`:

| Cột | Nội dung |
|---|---|
| `summary` JSONB | `ChapterSummaryLLM` của chương |
| `slides` JSONB | Danh sách slide `bullets` của chương |

- Mỗi chương xong ghi ngay; chạy lại bỏ qua chương đã có giá trị.
- Sau khi đủ các chương, code lắp ráp `summaries` và `slide_decks` từ các cột này.
- Quiz không áp dụng: sinh lại rẻ và có trạng thái riêng.

## Các phương án đã cân nhắc
1. **Thử lại đầu ra 2 lần** – tăng nhẹ tỉ lệ thành công nhưng lần thứ hai hiếm khi khác lần đầu, tốn token. Loại.
2. **LLM sinh cả slide mở/kết** – thêm lượt gọi, slide tổng kết có thể lệch với tóm tắt. Loại.
3. **Bảng `chapter_results` riêng** – linh hoạt hơn nhưng thừa cho quy mô hiện tại; thêm cột vào `chapters` đủ dùng. Loại.
4. **Cho chọn ngôn ngữ theo từng bài giảng ngay** – tốn thêm cột, trường API, UI; để sau.

## Hệ quả
- **Tích cực:** Số lượt gọi LLM ≈ 3 × số chương + 1 (tóm tắt, slide, quiz theo chương + tổng quan); `/retry` không gọi lại phần đã xong; số trang và cấu trúc slide luôn đúng vì do code sinh.
- **Tiêu cực:** Slide tổng kết phụ thuộc chất lượng `learning_objectives`; bảng `chapters` chứa thêm dữ liệu trung gian.

## Để sau
- Số trang cho từng ý chính (`key_points: [{text, page}]`).
- Chọn ngôn ngữ theo bài giảng: cột `lectures.content_language`, trường `language` khi upload, ô chọn trên giao diện.
