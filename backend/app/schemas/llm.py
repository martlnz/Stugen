"""Schema đầu ra LLM (ADR-0010, 0011, 0012, 0015) và cấu trúc JSONB lưu DB."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

MAX_BULLET = 120
MAX_SLIDE_TITLE = 80


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


class Term(BaseModel):
    term: str = Field(min_length=1, description="Thuật ngữ, giữ nguyên gốc")
    definition: str = Field(min_length=1, description="Định nghĩa ngắn gọn")


class ChapterSummaryLLM(BaseModel):
    """Đầu ra LLM cho một chương; lưu ở chapters.summary."""

    key_points: list[str] = Field(
        min_length=1, max_length=8, description="Ý chính của chương, mỗi ý một câu hoàn chỉnh"
    )
    terms: list[Term] = Field(default_factory=list, max_length=10)

    @field_validator("key_points", mode="before")
    @classmethod
    def _cap_points(cls, v: Any) -> Any:
        return _take(v, 8)

    @field_validator("terms", mode="before")
    @classmethod
    def _cap_terms(cls, v: Any) -> Any:
        return _take(v, 10)


class ChapterSummary(ChapterSummaryLLM):
    """Lưu ở summaries.chapters; idx/title/page_* do code ghép từ bảng chapters."""

    idx: int
    title: str
    page_start: int
    page_end: int


class OverviewLLM(BaseModel):
    overview: str = Field(min_length=1, description="Đoạn tổng quan toàn bộ giáo trình")
    learning_objectives: list[str] = Field(
        min_length=1, max_length=6, description="Mục tiêu học tập, mỗi mục tối đa 120 ký tự"
    )

    @field_validator("learning_objectives", mode="before")
    @classmethod
    def _fit(cls, v: Any) -> Any:
        return _clip_all(_take(v, 6), MAX_BULLET)


def _check_bullets(v: list[str]) -> list[str]:
    for item in v:
        if len(item) > MAX_BULLET:
            raise ValueError(f"Gạch đầu dòng dài {len(item)} ký tự, tối đa {MAX_BULLET}")
    return v


class Slide(BaseModel):
    layout: Literal["title", "agenda", "section", "bullets", "summary"]
    title: str = Field(max_length=80)
    subtitle: str | None = None
    bullets: list[str] = Field(default_factory=list, max_length=6)
    notes: str | None = None
    page_refs: list[int] = Field(default_factory=list)

    _bullets = field_validator("bullets")(_check_bullets)


class SlideDeck(BaseModel):
    version: Literal[1] = 1
    title: str
    slides: list[Slide]


class ContentSlideLLM(BaseModel):
    title: str = Field(min_length=1, max_length=80, description="Tiêu đề slide ngắn")
    bullets: list[str] = Field(
        min_length=1, max_length=6, description="Gạch đầu dòng ngắn gọn dạng ý"
    )
    notes: str | None = Field(default=None, description="Ghi chú cho người thuyết trình")
    page_refs: list[int] = Field(default_factory=list, description="Số trang tham chiếu")

    @field_validator("title", mode="before")
    @classmethod
    def _fit_title(cls, v: Any) -> Any:
        return clip(v, MAX_SLIDE_TITLE) if isinstance(v, str) else v

    @field_validator("bullets", mode="before")
    @classmethod
    def _fit_bullets(cls, v: Any) -> Any:
        return _clip_all(_take(v, 6), MAX_BULLET)


class ChapterSlidesLLM(BaseModel):
    slides: list[ContentSlideLLM] = Field(min_length=1, max_length=3)

    @field_validator("slides", mode="before")
    @classmethod
    def _cap(cls, v: Any) -> Any:
        return _take(v, 3)


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
