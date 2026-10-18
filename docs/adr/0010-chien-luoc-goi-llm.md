# ADR-0010: Chiến lược gọi LLM – theo chương, đầu ra có cấu trúc

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-18

## Bối cảnh
Cần sinh tóm tắt, slide, quiz từ giáo trình tới 200 trang (có thể > 100.000 token). Đầu ra phải đúng định dạng để lưu DB và hiển thị. Dự án phi thương mại nên cần kiểm soát chi phí và cho phép dùng mô hình miễn phí/chạy cục bộ.

## Yếu tố quyết định
- Độ chính xác, bám sát tài liệu gốc (hạn chế "bịa").
- Đầu ra parse được 100% trước khi lưu.
- Không phụ thuộc cứng vào một nhà cung cấp.
- Chi phí và thời gian hợp lý.

## Các phương án
1. **Đưa toàn bộ PDF vào một prompt** – đơn giản nếu mô hình có ngữ cảnh dài, nhưng tốn kém, chất lượng giảm với tài liệu dài, một lỗi là hỏng cả lượt.
2. **RAG (embedding + vector DB)** – phù hợp hỏi đáp, không phù hợp tóm tắt toàn bộ nội dung.
3. **Map–reduce theo chương** – xử lý từng chương rồi tổng hợp.

## Quyết định
Chọn **map–reduce theo chương** với **đầu ra JSON kiểm tra bằng Pydantic**.

### Lớp trừu tượng LLM
```python
class LLMClient(Protocol):
    def generate_json(self, system: str, user: str,
                      schema: type[BaseModel]) -> BaseModel: ...
```
- Triển khai qua adapter cho các nhà cung cấp có API tương thích; chọn bằng biến môi trường `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`.
- Hỗ trợ **Ollama** (chạy cục bộ, miễn phí) qua endpoint tương thích OpenAI để phát triển/thử nghiệm.
- Dùng tính năng structured output / JSON mode của nhà cung cấp khi có; luôn validate lại bằng Pydantic.
- Có thể cấu hình hai mô hình: `LLM_MODEL` (chính) và `LLM_MODEL_FAST` (rẻ, cho bước đơn giản).

### Pipeline
| Bước | Đầu vào | Đầu ra (schema) | Gọi LLM |
|---|---|---|---|
| Tóm tắt chương (map) | Văn bản 1 chương | `ChapterSummary{title, key_points[], terms[{term, definition}], pages[]}` | 1 lần/chương, chạy song song (tối đa 4) |
| Tổng quan (reduce) | Các `ChapterSummary` | `Overview{overview, learning_objectives[]}` | 1 lần |
| Slide | Tổng quan + tóm tắt chương | `SlideDeck` (ADR-0011) | 1 lần/chương + 1 lần mở/kết |
| Quiz | Văn bản chương | `QuestionSet{questions[]}` (ADR-0012) | 1 lần/chương, chia đều số câu |

Markdown tóm tắt cuối cùng được **lắp ráp bằng code** từ các schema trên (không để LLM tự viết Markdown tự do), đảm bảo bố cục thống nhất.

### Prompt
- Lưu dưới dạng file template (Jinja2) trong `app/ai/prompts/`, có phiên bản (`summary_v1.j2`).
- Nguyên tắc chung trong system prompt:
  - Chỉ dùng thông tin trong văn bản được cung cấp; không bổ sung kiến thức ngoài.
  - Trả lời bằng ngôn ngữ của tài liệu (hoặc tiếng Việt theo cấu hình).
  - Ghi số trang dựa trên đánh dấu `[[trang N]]`.
  - Giữ công thức ở dạng LaTeX (`$...$`).

### Kiểm tra và thử lại
1. Parse JSON → validate Pydantic (kèm ràng buộc: số gạch đầu dòng, `answer_index` trong 0–3, `page_ref` nằm trong khoảng trang của chương).
2. Lỗi validate → gọi lại 1 lần, đính kèm thông báo lỗi để mô hình sửa.
3. Vẫn lỗi → đánh dấu job thất bại (ADR-0008).

### Kiểm soát chi phí
- Ghi log số token vào/ra từng lần gọi (bảng `llm_calls` hoặc log có cấu trúc).
- Giới hạn PDF 200 trang (PRD) là trần chi phí cho mỗi bài giảng.
- Kết quả từng chương được lưu ngay, chạy lại không gọi lại phần đã xong.

## Hệ quả
- **Tích cực:** Chất lượng ổn định với tài liệu dài; lỗi cục bộ theo chương; dễ đổi nhà cung cấp; tham chiếu trang chính xác hơn.
- **Tiêu cực:** Nhiều lượt gọi hơn (≈ 3 × số chương); mất mạch liên kết giữa các chương (giảm bớt bằng bước tổng quan); chất lượng phụ thuộc mô hình được cấu hình.

## Ghi chú
- Tạo bộ 5–10 giáo trình mẫu (`tests/fixtures/`) để so sánh chất lượng khi đổi prompt hoặc mô hình.
- Unit test dùng `FakeLLMClient` trả JSON cố định.
