"""Schema đầu ra LLM (ADR-0010, 0011, 0012, 0015, 0017) và cấu trúc JSONB lưu DB.

Giới hạn hiển thị (độ dài, số phần tử) do code cắt gọn trong validator `mode="before"`;
lỗi cấu trúc vẫn được sửa 1 lần (ADR-0015).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

MAX_BULLET = 120
MAX_SLIDE_TITLE = 80
MAX_EXPLANATION = 300
MAX_EXAMPLE = 400


def clip(text: str, limit: int) -> str:
    """Cắt gọn theo ranh giới từ, thêm "…". Giới hạn hiển thị do code đảm bảo, không bắt LLM
    đếm ký tự (DeepSeek thường vượt vài ký tự và sửa lại vẫn sai)."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut[limit // 2 :]:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:.-–") + "…"


def _take(v: Any, n: int) -> Any:
    """Giữ tối đa n phần tử đầu (LLM đôi khi trả dư)."""
    return v[:n] if isinstance(v, list) else v


def _clip_all(v: Any, limit: int) -> Any:
    if isinstance(v, list):
        return [clip(x, limit) if isinstance(x, str) else x for x in v]
    return v


def _clip_opt(v: Any, limit: int) -> Any:
    if isinstance(v, str):
        v = clip(v, limit)
        return v or None
    return v


# ---------- Tách bài (outline) ----------


class OutlineLessonLLM(BaseModel):
    title: str = Field(min_length=1, description="Tên bài nêu đúng nội dung chính")
    start_page: int = Field(description="Trang bắt đầu bài, theo đánh dấu [[trang N]]")

    @field_validator("title", mode="before")
    @classmethod
    def _fit(cls, v: Any) -> Any:
        return clip(v, MAX_SLIDE_TITLE) if isinstance(v, str) else v


class OutlineLLM(BaseModel):
    chapter_title: str = Field(min_length=1, description="Tên chương ngắn gọn theo nội dung")
    lessons: list[OutlineLessonLLM] = Field(min_length=1)

    @field_validator("chapter_title", mode="before")
    @classmethod
    def _fit(cls, v: Any) -> Any:
        return clip(v, MAX_SLIDE_TITLE) if isinstance(v, str) else v

    @field_validator("lessons", mode="before")
    @classmethod
    def _cap(cls, v: Any) -> Any:
        return _take(v, 12)


# ---------- Tóm tắt bài ----------


class Term(BaseModel):
    term: str = Field(min_length=1, description="Thuật ngữ, giữ nguyên gốc")
    definition: str = Field(min_length=1, description="Định nghĩa ngắn gọn")


class LessonSection(BaseModel):
    title: str = Field(min_length=1, description="Tên mục nhỏ")
    page_start: int = Field(description="Trang bắt đầu của mục")
    page_end: int = Field(description="Trang kết thúc của mục")
    key_points: list[str] = Field(
        min_length=1, description="Ý chính của mục, mỗi ý một câu hoàn chỉnh"
    )

    @field_validator("title", mode="before")
    @classmethod
    def _fit_title(cls, v: Any) -> Any:
        return clip(v, 100) if isinstance(v, str) else v

    @field_validator("key_points", mode="before")
    @classmethod
    def _cap(cls, v: Any) -> Any:
        return _take(v, 6)


class LessonSummaryLLM(BaseModel):
    """Đầu ra LLM khi tóm tắt một bài; lưu ở lessons.summary sau khi code kẹp số trang."""

    title: str | None = Field(
        default=None, description="Tên bài cụ thể, nêu đúng nội dung chính của bài"
    )
    overview: str = Field(min_length=1, description="2–4 câu khái quát nội dung bài")
    sections: list[LessonSection] = Field(min_length=1)
    terms: list[Term] = Field(default_factory=list)

    @field_validator("title", mode="before")
    @classmethod
    def _fit_title(cls, v: Any) -> Any:
        return _clip_opt(v, MAX_SLIDE_TITLE)

    @field_validator("sections", mode="before")
    @classmethod
    def _cap_sections(cls, v: Any) -> Any:
        return _take(v, 10)

    @field_validator("terms", mode="before")
    @classmethod
    def _cap_terms(cls, v: Any) -> Any:
        return _take(v, 10)


# ---------- Slide ----------


def _check_bullets(v: list[str]) -> list[str]:
    for item in v:
        if len(item) > MAX_BULLET:
            raise ValueError(f"Gạch đầu dòng dài {len(item)} ký tự, tối đa {MAX_BULLET}")
    return v


class Slide(BaseModel):
    layout: Literal["title", "agenda", "section", "bullets", "summary"]
    title: str = Field(max_length=MAX_SLIDE_TITLE)
    subtitle: str | None = None
    bullets: list[str] = Field(default_factory=list, max_length=8)
    explanation: str | None = Field(default=None, max_length=MAX_EXPLANATION)
    example: str | None = Field(default=None, max_length=MAX_EXAMPLE)
    notes: str | None = None
    page_refs: list[int] = Field(default_factory=list)

    _bullets = field_validator("bullets")(_check_bullets)


class SlideDeck(BaseModel):
    version: Literal[1] = 1
    title: str
    slides: list[Slide]


class LessonSlideLLM(BaseModel):
    title: str = Field(min_length=1, description="Tiêu đề nêu đúng kiến thức chính của slide")
    bullets: list[str] = Field(min_length=1, description="2–5 ý ngắn gọn")
    explanation: str | None = Field(
        default=None, description="Giải thích dễ hiểu bằng lời thường, 1–3 câu"
    )
    example: str | None = Field(default=None, description="Ví dụ cụ thể minh hoạ kiến thức")
    notes: str | None = Field(default=None, description="Ghi chú cho người thuyết trình")
    page_refs: list[int] = Field(default_factory=list, description="Số trang tham chiếu")

    @field_validator("title", mode="before")
    @classmethod
    def _fit_title(cls, v: Any) -> Any:
        return clip(v, MAX_SLIDE_TITLE) if isinstance(v, str) else v

    @field_validator("bullets", mode="before")
    @classmethod
    def _fit_bullets(cls, v: Any) -> Any:
        return _clip_all(_take(v, 5), MAX_BULLET)

    @field_validator("explanation", mode="before")
    @classmethod
    def _fit_explanation(cls, v: Any) -> Any:
        return _clip_opt(v, MAX_EXPLANATION)

    @field_validator("example", mode="before")
    @classmethod
    def _fit_example(cls, v: Any) -> Any:
        return _clip_opt(v, MAX_EXAMPLE)


class LessonSlidesLLM(BaseModel):
    slides: list[LessonSlideLLM] = Field(min_length=1)
    takeaways: list[str] = Field(min_length=1, description="3–5 điều cần ghi nhớ")

    @field_validator("slides", mode="before")
    @classmethod
    def _cap(cls, v: Any) -> Any:
        return _take(v, 12)

    @field_validator("takeaways", mode="before")
    @classmethod
    def _fit_takeaways(cls, v: Any) -> Any:
        return _clip_all(_take(v, 6), MAX_BULLET)


# ---------- Quiz ----------


class QuestionLLM(BaseModel):
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=4, max_length=4, description="Đúng 4 lựa chọn")
    answer_index: int = Field(ge=0, le=3, description="Vị trí đáp án đúng trong options (0–3)")
    explanation: str = Field(min_length=1, description="Giải thích ngắn vì sao đáp án đúng")
    page_ref: int = Field(description="Số trang chứa thông tin, theo đánh dấu [[trang N]]")

    @field_validator("options")
    @classmethod
    def _distinct(cls, v: list[str]) -> list[str]:
        if len({o.strip().casefold() for o in v}) != len(v):
            raise ValueError("4 lựa chọn phải khác nhau")
        return v


class QuestionSetLLM(BaseModel):
    questions: list[QuestionLLM] = Field(min_length=1)
