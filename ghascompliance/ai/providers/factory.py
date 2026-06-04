"""Factory for creating AI provider instances."""

import os

from ghascompliance.ai.providers.base import BaseProvider

SUPPORTED_PROVIDERS = ("groq", "gemini", "anthropic")
_DEFAULT_PROVIDER = "groq"


def get_provider(provider_name: str | None = None, model: str | None = None) -> BaseProvider:
    """
    Return an initialised provider instance.

    Resolution order for provider_name:
      1. Explicit argument
      2. AI_PROVIDER environment variable
      3. Default: "groq"
    """
    name = (provider_name or os.environ.get("AI_PROVIDER", _DEFAULT_PROVIDER)).lower().strip()

    if name == "groq":
        from ghascompliance.ai.providers.groq_provider import GroqProvider
        return GroqProvider(model=model)

    if name == "gemini":
        from ghascompliance.ai.providers.gemini import GeminiProvider
        return GeminiProvider(model=model)

    if name == "anthropic":
        from ghascompliance.ai.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(model=model)

    raise ValueError(
        f"Unknown provider: {name!r}. "
        f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}"
    )
