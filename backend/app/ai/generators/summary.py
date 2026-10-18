"""Tóm tắt theo chương (map) + tổng quan (reduce); Markdown lắp ráp bằng code (ADR-0010)."""

from app.ai.llm import LLMClient
from app.ai.prompting import render, system_prompt
from app.db.models import Chapter
from app.schemas.llm import ChapterSummary, ChapterSummaryLLM, OverviewLLM


def summarize_chapter(llm: LLMClient, lecture_title: str, chapter: Chapter) -> ChapterSummaryLLM:
    user = render(
        "chapter_summary_v1",
        lecture_title=lecture_title,
        chapter_title=chapter.title,
        page_start=chapter.page_start,
        page_end=chapter.page_end,
        chapter_text=chapter.text,
    )
    return llm.generate_json(system_prompt(), user, ChapterSummaryLLM, purpose="chapter_summary")


def make_overview(
    llm: LLMClient, lecture_title: str, chapters: list[ChapterSummary]
) -> OverviewLLM:
    user = render("overview_v1", lecture_title=lecture_title, chapters=chapters)
    return llm.generate_json(system_prompt(), user, OverviewLLM, purpose="overview", fast=True)


def chapter_summaries(chapters: list[Chapter]) -> list[ChapterSummary]:
    """Ghép kết quả LLM (chapters.summary) với idx/title/trang do code biết (ADR-0015)."""
    return [
        ChapterSummary(
            **ChapterSummaryLLM.model_validate(ch.summary).model_dump(),
            idx=ch.idx,
            title=ch.title,
            page_start=ch.page_start,
            page_end=ch.page_end,
        )
        for ch in chapters
    ]


def _pages(start: int, end: int) -> str:
    return f"trang {start}" if start == end else f"trang {start}–{end}"


def build_markdown(
    lecture_title: str, overview: OverviewLLM, chapters: list[ChapterSummary]
) -> str:
    lines = [f"# {lecture_title}", "", "## Tổng quan", "", overview.overview, ""]
    lines += ["## Mục tiêu học tập", ""]
    lines += [f"- {o}" for o in overview.learning_objectives]
    for ch in chapters:
        lines += ["", f"## {ch.title}", "", f"*({_pages(ch.page_start, ch.page_end)})*", ""]
        lines += ["### Ý chính", ""]
        lines += [f"- {p}" for p in ch.key_points]
        if ch.terms:
            lines += ["", "### Thuật ngữ", ""]
            lines += [f"- **{t.term}**: {t.definition}" for t in ch.terms]
    return "\n".join(lines) + "\n"
