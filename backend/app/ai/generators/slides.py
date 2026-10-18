"""Slide (ADR-0011, ADR-0015): code sinh title/agenda/section/summary, LLM sinh slide bullets."""

from app.ai.llm import LLMClient
from app.ai.prompting import render, system_prompt
from app.db.models import Chapter
from app.schemas.llm import ChapterSlidesLLM, ChapterSummaryLLM, Slide, SlideDeck, clip


def chapter_slides(llm: LLMClient, lecture_title: str, chapter: Chapter) -> list[Slide]:
    summary = ChapterSummaryLLM.model_validate(chapter.summary)

    def check_pages(result: ChapterSlidesLLM) -> None:
        for slide in result.slides:
            bad = [p for p in slide.page_refs if not chapter.page_start <= p <= chapter.page_end]
            if bad:
                raise ValueError(
                    f"page_refs {bad} nằm ngoài khoảng {chapter.page_start}–{chapter.page_end}"
                )

    user = render(
        "slides_v1",
        lecture_title=lecture_title,
        chapter_title=chapter.title,
        page_start=chapter.page_start,
        page_end=chapter.page_end,
        key_points=summary.key_points,
        terms=summary.terms,
        min_slides=1,
        max_slides=3 if len(summary.key_points) > 4 else 2,
    )
    result = llm.generate_json(
        system_prompt(), user, ChapterSlidesLLM, purpose="slides", fast=True, validate=check_pages
    )
    return [
        Slide(
            layout="bullets",
            title=s.title,
            bullets=s.bullets,
            notes=s.notes,
            page_refs=sorted(set(s.page_refs)),
        )
        for s in result.slides
    ]


def build_deck(
    lecture_title: str, chapters: list[Chapter], learning_objectives: list[str]
) -> SlideDeck:
    titles = [ch.title for ch in chapters]
    slides = [
        Slide(layout="title", title=clip(lecture_title, 80), subtitle="Tóm lược giáo trình"),
    ]
    # Mục lục tối đa 6 dòng/slide → tách nhiều slide nếu nhiều chương
    for i in range(0, len(titles), 6):
        part = "" if len(titles) <= 6 else f" ({i // 6 + 1})"
        slides.append(
            Slide(
                layout="agenda",
                title=f"Nội dung{part}",
                bullets=[clip(t, 120) for t in titles[i : i + 6]],
            )
        )
    for ch in chapters:
        slides.append(
            Slide(
                layout="section",
                title=clip(ch.title, 80),
                subtitle=f"Trang {ch.page_start}–{ch.page_end}",
            )
        )
        slides.extend(Slide.model_validate(s) for s in ch.slides or [])
    slides.append(
        Slide(
            layout="summary",
            title="Tổng kết",
            bullets=[clip(o, 120) for o in learning_objectives[:6]],
        )
    )
    return SlideDeck(title=lecture_title, slides=slides)
