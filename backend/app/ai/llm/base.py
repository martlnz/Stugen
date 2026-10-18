import json
import logging
from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class LLMError(Exception):
    code = "LLM_UNAVAILABLE"


class LLMUnavailable(LLMError):
    """Lỗi tạm thời (timeout, 429, 5xx) vẫn còn sau khi thử lại."""

    code = "LLM_UNAVAILABLE"


class LLMInvalidOutput(LLMError):
    """Đầu ra sai định dạng sau khi đã sửa 1 lần (ADR-0015)."""

    code = "LLM_INVALID_OUTPUT"


class OutputError(Exception):
    """Đầu ra không dùng được ở một lượt gọi (sẽ được sửa 1 lần)."""


type Validator[T] = Callable[[T], None]


class LLMClient(Protocol):
    def generate_json[T: BaseModel](
        self,
        system: str,
        user: str,
        schema: type[T],
        *,
        purpose: str,
        fast: bool = False,
        validate: Validator[T] | None = None,
    ) -> T: ...


def parse_output[T: BaseModel](
    content: str | None, schema: type[T], validate: Validator[T] | None
) -> T:
    """JSON → Pydantic → kiểm tra theo ngữ cảnh. Lỗi nào cũng ném OutputError kèm mô tả."""
    if not content or not content.strip():
        raise OutputError("Phản hồi rỗng.")
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") :]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OutputError(f"JSON không hợp lệ: {exc}") from None
    try:
        result = schema.model_validate(data)
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:10]
        )
        raise OutputError(f"Sai schema: {errors}") from None
    if validate:
        try:
            validate(result)
        except ValueError as exc:
            raise OutputError(str(exc)) from None
    return result


def example_from_schema(schema: type[BaseModel]) -> str:
    """Ví dụ JSON sinh từ schema Pydantic, đưa vào prompt khi provider không hỗ trợ json_schema."""
    root = schema.model_json_schema()
    defs = root.get("$defs", {})

    def build(node: dict[str, Any]) -> Any:
        if "$ref" in node:
            return build(defs[node["$ref"].split("/")[-1]])
        if "anyOf" in node:
            options = [n for n in node["anyOf"] if n.get("type") != "null"]
            return build(options[0]) if options else None
        if "enum" in node:
            return node["enum"][0]
        if "const" in node:
            return node["const"]
        kind = node.get("type")
        desc = node.get("description")
        if kind == "object":
            return {k: build(v) for k, v in node.get("properties", {}).items()}
        if kind == "array":
            item = build(node.get("items", {}))
            return [item] * max(1, min(node.get("minItems", 1), 2))
        if kind == "integer":
            return node.get("minimum", 1)
        if kind == "number":
            return 1.0
        if kind == "boolean":
            return True
        return f"<{desc}>" if desc else "<chuỗi>"

    return json.dumps(build(root), ensure_ascii=False, indent=2)
