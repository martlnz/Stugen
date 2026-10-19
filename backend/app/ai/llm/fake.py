"""LLM giả, trả JSON cố định hợp lệ: dùng trong test và khi LLM_PROVIDER=fake (không gọi mạng)."""

import json
import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.ai.llm.base import LLMInvalidOutput, OutputError, Validator, parse_output

PAGE_RE = re.compile(r"\[\[trang (\d+)\]\]")
COUNT_RE = re.compile(r"Số câu hỏi cần tạo:\s*(\d+)")
TITLE_RE = re.compile(r"(?:Bài|Chương):\s*(.+?)(?: \(trang|$)", re.MULTILINE)
QUOTED_TITLE_RE = re.compile(r"bài học \"(.+?)\"")
RANGE_RE = re.compile(r"trang (\d+)–(\d+)")


def _range(user: str) -> tuple[int, int]:
    if match := RANGE_RE.search(user):
        return int(match.group(1)), int(match.group(2))
    markers = [int(p) for p in PAGE_RE.findall(user)] or [1]
    return min(markers), max(markers)


def _pages(user: str) -> list[int]:
    if markers := PAGE_RE.findall(user):
        return [int(p) for p in markers]
    return [_range(user)[0]]


def _title(user: str) -> str:
    match = TITLE_RE.search(user) or QUOTED_TITLE_RE.search(user)
    return match.group(1).strip()[:60] if match else "Nội dung"


def _default(schema_name: str, user: str) -> dict[str, Any]:
    pages = _pages(user)
    start, end = _range(user)
    title = _title(user)
    match schema_name:
        case "OutlineLLM":
            mid = (start + end) // 2 + 1
            return {
                "chapter_title": "Chủ đề do AI đặt tên",
                "lessons": [
                    {"title": "Bài mở đầu", "start_page": start},
                    {"title": "Bài tiếp theo", "start_page": mid},
                ],
            }
        case "LessonSummaryLLM":
            return {
                "title": f"Kiến thức về {title}",
                "overview": f"Bài {title} trình bày các khái niệm nền tảng.",
                "sections": [
                    {
                        "title": f"Mục {i + 1} của {title}",
                        "page_start": p,
                        "page_end": p,
                        "key_points": [f"Ý chính {k + 1} của mục {i + 1}." for k in range(2)],
                    }
                    for i, p in enumerate(sorted(set(pages)))
                ],
                "terms": [{"term": "DBMS", "definition": "Hệ quản trị cơ sở dữ liệu."}],
            }
        case "LessonSlidesLLM":
            return {
                "slides": [
                    {
                        "title": f"Kiến thức {i + 1} của {title}",
                        "bullets": ["Khái niệm chính", "Cách áp dụng"],
                        "explanation": "Giải thích dễ hiểu.",
                        "example": "Ví dụ minh hoạ: một bảng sinh viên có khoá chính MSSV.",
                        "notes": "Gợi ý thuyết trình.",
                        "page_refs": pages[:1],
                    }
                    for i in range(3)
                ],
                "takeaways": ["Điều cần nhớ 1", "Điều cần nhớ 2", "Điều cần nhớ 3"],
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
