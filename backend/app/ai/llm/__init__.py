from app.ai.llm.base import LLMClient, LLMError, LLMInvalidOutput, LLMUnavailable
from app.core.config import settings

_client: LLMClient | None = None


def get_llm() -> LLMClient:
    """LLMClient theo cấu hình LLM_PROVIDER; mọi lời gọi LLM đi qua đây."""
    global _client
    if _client is None:
        _client = build_client()
    return _client


def set_llm(client: LLMClient | None) -> None:
    global _client
    _client = client


def build_client() -> LLMClient:
    if settings.llm_provider == "fake":
        from app.ai.llm.fake import FakeLLMClient

        return FakeLLMClient()
    if settings.llm_provider in ("openai_compatible", "openai"):
        from app.ai.llm.openai_compatible import OpenAICompatibleClient

        base_url = settings.llm_base_url or None
        is_deepseek = "deepseek" in (base_url or "")
        return OpenAICompatibleClient(
            api_key=settings.llm_api_key,
            base_url=base_url,
            model=settings.llm_model,
            model_fast=settings.llm_model_fast,
            # DeepSeek/Ollama chỉ có json_object; OpenAI chính chủ hỗ trợ json_schema
            supports_json_schema=settings.llm_provider == "openai",
            disable_thinking=is_deepseek,
            timeout=settings.llm_timeout_s,
            max_tokens=settings.llm_max_tokens,
        )
    raise NotImplementedError(
        f"LLM_PROVIDER={settings.llm_provider} chưa được hỗ trợ; dùng openai_compatible"
    )


__all__ = ["LLMClient", "LLMError", "LLMInvalidOutput", "LLMUnavailable", "get_llm", "set_llm"]
