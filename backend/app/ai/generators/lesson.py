"""Học liệu theo bài nhỏ (ADR-0017): tách bài, tóm tắt theo mục, slide dễ hiểu có ví dụ."""

import logging
import math
from typing import Protocol

from app.ai.llm import LLMClient, LLMError
from app.ai.pdf import ExtractedChapter, LessonHint, page_snippets
from app.ai.prompting import render, system_prompt
from app.schemas.llm import (
    LessonSection,
    LessonSlidesLLM,
    LessonSummaryLLM,
    OutlineLLM,
    Slide,
    SlideDeck,
    clip,
)

logger = logging.getLogger(__name__)


class LessonLike(Protocol):
    title: str
    page_start: int
    page_end: int
    text: str


def page_count(unit: LessonLike) -> int:
    return unit.page_end - unit.page_start + 1


def pages_label(start: int, end: int) -> str:
    return f"tr. {start}" if start == end else f"tr. {start}–{end}"


# ---------- Tách bài ----------


def outline_hint(llm: LLMClient, chapter: ExtractedChapter) -> LessonHint | None:
    """Gợi ý ranh giới và tên bài cho chương không có tiêu đề phụ; lỗi → None (chia đều)."""
    n = chapter.page_end - chapter.page_start + 1
    user = render(
        "outline_v1",
        chapter_title=chapter.title,
        page_start=chapter.page_start,
        page_end=chapter.page_end,
        min_lessons=max(2, math.ceil(n / 6)),
        max_lessons=max(2, min(8, math.ceil(n / 2))),
        snippets=page_snippets(chapter.text),
    )
    try:
        result = llm.generate_json(system_prompt(), user, OutlineLLM, purpose="outline", fast=True)
    except LLMError:
        logger.warning("Outline LLM failed for chapter %s; using page chunks", chapter.title)
        return None
    return LessonHint(
        chapter_title=result.chapter_title,
        starts=[(lesson.title, lesson.start_page) for lesson in result.lessons],
    )


# ---------- Tóm tắt ----------


def _clamp_sections(sections: list[LessonSection], start: int, end: int) -> list[LessonSection]:
    """Trang mục nhỏ do LLM đọc từ [[trang N]]; code kẹp vào khoảng bài và sắp xếp."""
    fixed = []
    for s in sections:
        a = min(max(s.page_start, start), end)
        b = min(max(s.page_end, a), end)
        fixed.append(s.model_copy(update={"page_start": a, "page_end": b}))
    return sorted(fixed, key=lambda s: s.page_start)


def summarize_lesson(llm: LLMClient, lesson: LessonLike) -> LessonSummaryLLM:
    n = page_count(lesson)
    user = render(
        "lesson_summary_v1",
        lesson_title=lesson.title,
        page_start=lesson.page_start,
        page_end=lesson.page_end,
        min_sections=2 if n > 1 else 1,
        max_sections=min(8, max(3, n + 1)),
        lesson_text=lesson.text,
    )
    result = llm.generate_json(system_prompt(), user, LessonSummaryLLM, purpose="lesson_summary")
    sections = _clamp_sections(result.sections, lesson.page_start, lesson.page_end)
    return result.model_copy(update={"sections": sections})


def summary_markdown(summary: LessonSummaryLLM) -> str:
    """Markdown lắp bằng code; không có tên file hay tên giáo trình."""
    lines = ["## Tổng quan", "", summary.overview, ""]
    for s in summary.sections:
        lines += [f"### {s.title} *({pages_label(s.page_start, s.page_end)})*", ""]
        lines += [f"- {p}" for p in s.key_points]
        lines.append("")
    if summary.terms:
        lines += ["## Thuật ngữ", ""]
        lines += [f"- **{t.term}**: {t.definition}" for t in summary.terms]
    return "\n".join(lines).strip() + "\n"


# ---------- Slide ----------


def slide_count(lesson: LessonLike) -> tuple[int, int]:
    target = min(10, max(3, math.ceil(page_count(lesson) * 1.2)))
    return max(3, target - 1), target + 1


def lesson_slides(llm: LLMClient, lesson: LessonLike, summary: LessonSummaryLLM) -> LessonSlidesLLM:
    min_slides, max_slides = slide_count(lesson)
    user = render(
        "lesson_slides_v1",
        lesson_title=lesson.title,
        page_start=lesson.page_start,
        page_end=lesson.page_end,
        sections=summary.sections,
        min_slides=min_slides,
        max_slides=min(max_slides, 12),
        lesson_text=lesson.text,
    )
    result = llm.generate_json(system_prompt(), user, LessonSlidesLLM, purpose="slides")
    # Số trang ngoài khoảng bài bị bỏ thay vì coi là lỗi
    slides = [
        s.model_copy(
            update={
                "page_refs": sorted(
                    {p for p in s.page_refs if lesson.page_start <= p <= lesson.page_end}
                )
            }
        )
        for s in result.slides
    ]
    return result.model_copy(update={"slides": slides})


def build_deck(
    lesson: LessonLike,
    number: str,
    chapter_title: str,
    summary: LessonSummaryLLM,
    content: LessonSlidesLLM,
) -> SlideDeck:
    """Code ghép slide tiêu đề, mục lục (mục nhỏ kèm trang), nội dung, ghi nhớ."""
    title = clip(lesson.title, 80)
    slides = [
        Slide(
            layout="title",
            title=title,
            subtitle=f"Bài {number} · {clip(chapter_title, 60)}",
        )
    ]
    agenda = [
        clip(f"{s.title} ({pages_label(s.page_start, s.page_end)})", 120) for s in summary.sections
    ]
    for i in range(0, len(agenda), 6):
        part = "" if len(agenda) <= 6 else f" ({i // 6 + 1})"
        slides.append(
            Slide(layout="agenda", title=f"Nội dung bài{part}", bullets=agenda[i : i + 6])
        )
    for s in content.slides:
        slides.append(
            Slide(
                layout="bullets",
                title=s.title,
                bullets=s.bullets,
                explanation=s.explanation,
                example=s.example,
                notes=s.notes,
                page_refs=s.page_refs,
            )
        )
    slides.append(Slide(layout="summary", title="Ghi nhớ", bullets=content.takeaways[:6]))
    return SlideDeck(title=title, slides=slides)
