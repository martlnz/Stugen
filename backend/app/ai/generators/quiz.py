"""Sinh quiz theo bài (ADR-0012, ADR-0017): phân bổ theo độ dài, kiểm tra trang, xáo đáp án."""

import random
from dataclasses import dataclass
from typing import Protocol

from app.ai.llm import LLMClient
from app.ai.prompting import render, system_prompt
from app.schemas.llm import LessonSection, QuestionLLM, QuestionSetLLM

MIN_LESSON_QUESTIONS = 5
MAX_LESSON_QUESTIONS = 15


class QuizSource(Protocol):
    idx: int
    title: str
    page_start: int
    page_end: int
    text: str


@dataclass
class GeneratedQuestion:
    question: str
    options: list[str]
    answer_index: int
    explanation: str
    page_ref: int
    source_idx: int


def default_question_count(page_start: int, page_end: int) -> int:
    """Quiz mặc định của bài: ~1,5 câu/trang, 5–15 câu (ADR-0017)."""
    pages = page_end - page_start + 1
    return min(MAX_LESSON_QUESTIONS, max(MIN_LESSON_QUESTIONS, round(pages * 1.5)))


def allocate(total: int, sizes: list[int]) -> list[int]:
    """Chia `total` câu cho các phần tỉ lệ theo độ dài; mỗi phần ≥ 1 câu nếu đủ câu."""
    n = len(sizes)
    if n == 0:
        return []
    if total < n:
        # Không đủ cho mọi phần: ưu tiên các phần dài nhất
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


def questions_for_source(
    llm: LLMClient,
    source: QuizSource,
    count: int,
    avoid: list[str],
    rng: random.Random,
    sections: list[LessonSection] | None = None,
) -> list[GeneratedQuestion]:
    def check(result: QuestionSetLLM) -> None:
        if len(result.questions) < count:
            raise ValueError(f"Cần {count} câu hỏi nhưng chỉ có {len(result.questions)}")
        for i, q in enumerate(result.questions[:count], start=1):
            if not source.page_start <= q.page_ref <= source.page_end:
                raise ValueError(
                    f"Câu {i}: page_ref {q.page_ref} nằm ngoài khoảng "
                    f"{source.page_start}–{source.page_end}"
                )

    user = render(
        "lesson_quiz_v1",
        lesson_title=source.title,
        page_start=source.page_start,
        page_end=source.page_end,
        count=count,
        sections=sections or [],
        avoid=avoid[-30:],
        lesson_text=source.text,
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
                source_idx=source.idx,
            )
        )
    return generated
