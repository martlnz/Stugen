from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.core.config import settings

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "prompts"),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
    keep_trailing_newline=False,
)


def render(name: str, **context: Any) -> str:
    """Render prompt `app/ai/prompts/<name>.j2` kèm cấu hình ngôn ngữ nội dung."""
    return (
        _env.get_template(f"{name}.j2")
        .render(content_language=settings.content_language, **context)
        .strip()
    )


def system_prompt() -> str:
    return render("system_v1")
