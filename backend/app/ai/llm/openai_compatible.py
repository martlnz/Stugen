"""Provider tương thích OpenAI: DeepSeek (mặc định, ADR-0016), OpenAI, Ollama."""

import logging
import time
from typing import Any

import openai
from pydantic import BaseModel

from app.ai.llm.base import (
    LLMInvalidOutput,
    LLMUnavailable,
    OutputError,
    Validator,
    example_from_schema,
    parse_output,
)

logger = logging.getLogger(__name__)

# Lỗi tạm thời: SDK đã tự thử lại `max_retries` lần có backoff (ADR-0015)
TRANSIENT_ERRORS = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
)


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None,
        model: str,
        model_fast: str,
        supports_json_schema: bool,
        disable_thinking: bool,
        timeout: float,
        max_tokens: int,
        max_retries: int = 2,
    ) -> None:
        self.client = openai.OpenAI(
            api_key=api_key or "not-set",
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        self.model = model
        self.model_fast = model_fast or model
        self.supports_json_schema = supports_json_schema
        self.disable_thinking = disable_thinking
        self.max_tokens = max_tokens

    def _response_format(self, schema: type[BaseModel]) -> dict[str, Any]:
        if self.supports_json_schema:
            return {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
            }
        return {"type": "json_object"}

    def _system(self, system: str, schema: type[BaseModel]) -> str:
        if self.supports_json_schema:
            return system
        # json_object yêu cầu prompt có chữ "json" và nên kèm ví dụ cấu trúc
        return (
            f"{system}\n\nChỉ trả về một đối tượng json hợp lệ, không kèm giải thích, "
            f"đúng cấu trúc như ví dụ sau (thay nội dung trong <...>):\n"
            f"{example_from_schema(schema)}"
        )

    def _call(self, model: str, messages: list[dict[str, str]], schema: type[BaseModel]) -> str:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "response_format": self._response_format(schema),
            "max_tokens": self.max_tokens,
            "temperature": 0.3,
        }
        if self.disable_thinking:
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        try:
            resp = self.client.chat.completions.create(**kwargs)
        except TRANSIENT_ERRORS as exc:
            logger.warning("LLM transient error after retries: %s", type(exc).__name__)
            raise LLMUnavailable(str(exc)) from exc
        except openai.APIStatusError as exc:
            logger.error("LLM API error %s: %s", exc.status_code, exc.message)
            raise LLMUnavailable(str(exc)) from exc
        choice = resp.choices[0]
        usage = resp.usage
        logger.info(
            "LLM call model=%s finish=%s in=%s out=%s",
            model,
            choice.finish_reason,
            usage.prompt_tokens if usage else None,
            usage.completion_tokens if usage else None,
        )
        content = choice.message.content or ""
        if choice.finish_reason == "length":
            raise OutputError("Phản hồi bị cắt do quá dài; hãy viết ngắn gọn hơn.")
        return content

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
        model = self.model_fast if fast else self.model
        messages = [
            {"role": "system", "content": self._system(system, schema)},
            {"role": "user", "content": user},
        ]
        started = time.monotonic()
        content = ""
        try:
            content = self._call(model, messages, schema)
            return parse_output(content, schema, validate)
        except OutputError as first:
            # Sửa 1 lần, kèm thông báo lỗi validate (ADR-0015)
            logger.warning("LLM %s invalid output, repairing: %s", purpose, first)
            messages += [
                {"role": "assistant", "content": content or "(rỗng)"},
                {
                    "role": "user",
                    "content": (
                        f"Đầu ra trên không hợp lệ: {first}\n"
                        "Hãy trả lại toàn bộ json đã sửa, đúng cấu trúc yêu cầu."
                    ),
                },
            ]
            try:
                content = self._call(model, messages, schema)
                return parse_output(content, schema, validate)
            except OutputError as second:
                logger.error("LLM %s invalid output after repair: %s", purpose, second)
                raise LLMInvalidOutput(str(second)) from None
        finally:
            logger.info("LLM %s done in %.1fs", purpose, time.monotonic() - started)
