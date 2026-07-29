"""OpenRouter AsyncOpenAI client factory with app attribution headers."""

from openai import AsyncOpenAI

from app.core.config import settings


def create_openrouter_client(*, api_key: str) -> AsyncOpenAI:
    """Build an OpenAI SDK client pointed at OpenRouter with attribution headers."""
    headers: dict[str, str] = {}
    app_url = settings.ai.openrouter_app_url
    app_title = settings.ai.openrouter_app_title
    if app_url:
        headers["HTTP-Referer"] = app_url
    if app_title:
        headers["X-OpenRouter-Title"] = app_title

    return AsyncOpenAI(
        api_key=api_key,
        base_url=settings.ai.openrouter_base_url,
        default_headers=headers or None,
    )
