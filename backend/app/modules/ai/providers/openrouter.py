"""OpenRouter AI provider using OpenAI SDK.

This is the official recommended approach from OpenRouter documentation.
"""

from typing import Any, cast

from openai.types.chat import ChatCompletionMessageParam

from app.core.config import settings
from app.modules.ai.exceptions import OpenRouterError, TokenValidationError
from app.modules.usage.openrouter_client import create_openrouter_client

from .base import AIProvider, ChatResponse


class OpenRouterProvider(AIProvider):
    """OpenRouter provider using OpenAI SDK.

    Uses the official OpenAI SDK with custom base URL for OpenRouter.
    This is the recommended approach from OpenRouter documentation.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize OpenRouter provider.

        Args:
            api_key: Optional API key (uses system key if not provided)
        """
        self.api_key = api_key or settings.ai.openrouter_api_key
        self.base_url = settings.ai.openrouter_base_url

        if not self.api_key:
            raise OpenRouterError("OpenRouter API key not configured")

        self.client = create_openrouter_client(api_key=self.api_key)

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int | None = None,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> ChatResponse:
        """Send chat completion request to OpenRouter.

        Args:
            messages: List of chat messages
            model: Model identifier (e.g., "openai/gpt-4o-mini")
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            **kwargs: Additional OpenRouter parameters

        Returns:
            ChatResponse with message and token usage

        Raises:
            OpenRouterError: If API request fails
        """
        try:
            # Cast messages to the expected type for OpenAI SDK
            typed_messages = cast(list[ChatCompletionMessageParam], messages)
            response = await self.client.chat.completions.create(
                model=model,
                messages=typed_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            # Extract response data
            choice = response.choices[0]
            message_content = choice.message.content or ""

            return ChatResponse(
                message=message_content,
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=(response.usage.completion_tokens if response.usage else 0),
                total_tokens=response.usage.total_tokens if response.usage else 0,
                model=response.model,
                finish_reason=choice.finish_reason,
                raw_response=response.model_dump(),
            )

        except Exception as e:
            raise OpenRouterError(f"OpenRouter API request failed: {e}") from e

    async def validate_token(self, api_token: str) -> bool:
        """Validate an OpenRouter API token.

        Args:
            api_token: API token to validate

        Returns:
            True if token is valid

        Raises:
            TokenValidationError: If token is invalid
        """
        try:
            # Create temporary client with the token
            test_client = AsyncOpenAI(api_key=api_token, base_url=self.base_url)

            # Try a minimal request to validate the token
            await test_client.chat.completions.create(
                model="openai/gpt-3.5-turbo",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )

            return True

        except Exception as e:
            raise TokenValidationError(f"Token validation failed: {e}") from e
