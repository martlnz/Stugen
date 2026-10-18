"""LLM giả, trả JSON cố định hợp lệ: dùng trong test và khi LLM_PROVIDER=fake (không gọi mạng)."""

import json
import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.ai.llm.base import LLMInvalidOutput, OutputError, Validator, parse_output

PAGE_RE = re.compile(r"\[\[trang (\d+)\]\]")
COUNT_RE = re.compile(r"Số câu hỏi cần tạo:\s*(\d+)")
TITLE_RE = re.compile(r"Chương:\s*(.+)")


RANGE_RE = re.compile(r"trang (\d+)–(\d+)")


def _pages(user: str) -> list[int]:
    if markers := PAGE_RE.findall(user):
        return [int(p) for p in markers]
    if match := RANGE_RE.search(user):
        return [int(match.group(1))]
    return [1]


def _default(schema_name: str, user: str) -> dict[str, Any]:
    pages = _pages(user)
    title_match = TITLE_RE.search(user)
    title = title_match.group(1).strip()[:60] if title_match else "Nội dung"
    match schema_name:
        case "ChapterSummaryLLM":
            return {
                "key_points": [f"Ý chính {i + 1} của {title}." for i in range(3)],
                "terms": [{"term": "DBMS", "definition": "Hệ quản trị cơ sở dữ liệu."}],
            }
        case "OverviewLLM":
            return {
                "overview": "Giáo trình trình bày các khái niệm nền tảng.",
                "learning_objectives": ["Hiểu khái niệm cơ bản", "Vận dụng vào bài tập"],
            }
        case "ChapterSlidesLLM":
            return {
                "slides": [
                    {
                        "title": title,
                        "bullets": ["Khái niệm chính", "Ví dụ minh hoạ"],
                        "notes": "Giới thiệu chương.",
                        "page_refs": pages[:1],
                    }
                ]
            }
        case "QuestionSetLLM":
            count_match = COUNT_RE.search(user)
            n = int(count_match.group(1)) if count_match else 1
            return {
                "questions": [
                    {
                        "question": f"Câu hỏi {i + 1} về {title}?",
                        "options": ["Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D"],
                        "answer_index": 0,
                        "explanation": "Theo giáo trình.",
                        "page_ref": pages[i % len(pages)],
                    }
                    for i in range(n)
                ]
            }
    raise ValueError(f"FakeLLMClient: không có dữ liệu mẫu cho {schema_name}")


class FakeLLMClient:
    """`responses` cho phép test ép đầu ra theo tên schema (chuỗi JSON thô hoặc dict)."""

    def __init__(self, responses: dict[str, list[str | dict[str, Any]]] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, str]] = []
        self.on_call: Callable[[str, str], None] | None = None

    def _next(self, schema_name: str, user: str) -> str:
        queue = self.responses.get(schema_name)
        if queue:
            item = queue.pop(0)
            return item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        return json.dumps(_default(schema_name, user), ensure_ascii=False)

    def generate_json[T: BaseModel](
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        purpose: str,
        fast: bool = False,
        validate: Validator[T] | None = None,
    ) -> T:
        self.calls.append((purpose, user))
        if self.on_call:
            self.on_call(purpose, user)
        for attempt in range(2):
            try:
                return parse_output(self._next(schema.__name__, user), schema, validate)
            except OutputError as exc:
                if attempt == 1:
                    raise LLMInvalidOutput(str(exc)) from None
        raise AssertionError("unreachable")
