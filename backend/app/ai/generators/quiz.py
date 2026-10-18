"""Sinh quiz theo chương (ADR-0012): phân bổ theo độ dài, kiểm tra trang, xáo trộn đáp án."""

import random
from dataclasses import dataclass

from app.ai.llm import LLMClient
from app.ai.prompting import render, system_prompt
from app.db.models import Chapter
from app.schemas.llm import QuestionLLM, QuestionSetLLM

MAX_CHAPTER_PROMPT_CHARS = 30_000


@dataclass
class GeneratedQuestion:
    question: str
    options: list[str]
    answer_index: int
    explanation: str
    page_ref: int
    chapter_idx: int


def allocate(total: int, sizes: list[int]) -> list[int]:
    """Chia `total` câu cho các chương tỉ lệ theo độ dài; mỗi chương ≥ 1 câu nếu đủ câu."""
    n = len(sizes)
    if n == 0:
        return []
    if total < n:
        # Không đủ cho mọi chương: ưu tiên các chương dài nhất
        top = sorted(range(n), key=lambda i: -sizes[i])[:total]
        return [1 if i in top else 0 for i in range(n)]
    counts = [1] * n
    rest = total - n
    weight = sum(sizes) or n
    shares = [rest * (s or 1) / weight for s in sizes]
    for i, share in enumerate(shares):
        counts[i] += int(share)
    remaining = total - sum(counts)
    by_remainder = sorted(range(n), key=lambda i: -(shares[i] - int(shares[i])))
    for i in by_remainder[:remaining]:
        counts[i] += 1
    return counts


def shuffle_options(q: QuestionLLM, rng: random.Random) -> tuple[list[str], int]:
    """LLM hay đặt đáp án đúng cùng vị trí → server xáo trộn và cập nhật answer_index."""
    order = list(range(4))
    rng.shuffle(order)
    options = [q.options[i] for i in order]
    return options, order.index(q.answer_index)


def questions_for_chapter(
    llm: LLMClient,
    lecture_title: str,
    chapter: Chapter,
    count: int,
    avoid: list[str],
    rng: random.Random,
) -> list[GeneratedQuestion]:
    def check(result: QuestionSetLLM) -> None:
        if len(result.questions) < count:
            raise ValueError(f"Cần {count} câu hỏi nhưng chỉ có {len(result.questions)}")
        for i, q in enumerate(result.questions[:count], start=1):
            if not chapter.page_start <= q.page_ref <= chapter.page_end:
                raise ValueError(
                    f"Câu {i}: page_ref {q.page_ref} nằm ngoài khoảng "
                    f"{chapter.page_start}–{chapter.page_end}"
                )

    user = render(
        "quiz_v1",
        lecture_title=lecture_title,
        chapter_title=chapter.title,
        page_start=chapter.page_start,
        page_end=chapter.page_end,
        count=count,
        avoid=avoid[-30:],
        chapter_text=chapter.text[:MAX_CHAPTER_PROMPT_CHARS],
    )
    result = llm.generate_json(
        system_prompt(), user, QuestionSetLLM, purpose="quiz", validate=check
    )
    generated = []
    for q in result.questions[:count]:
        options, answer = shuffle_options(q, rng)
        generated.append(
            GeneratedQuestion(
                question=q.question,
                options=options,
                answer_index=answer,
                explanation=q.explanation,
                page_ref=q.page_ref,
                chapter_idx=chapter.idx,
            )
        )
    return generated
