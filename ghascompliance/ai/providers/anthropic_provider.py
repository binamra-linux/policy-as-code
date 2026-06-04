"""Anthropic Claude provider (API key required, paid)."""

import os
from typing import List, Dict

from ghascompliance.ai.providers.base import BaseProvider

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048


class AnthropicProvider(BaseProvider):
    """
    Backed by the Anthropic SDK with prompt caching on the system prompt.

    Required env var: ANTHROPIC_API_KEY
    """

    def __init__(self, model: str | None = None):
        try:
            import anthropic
            self._anthropic = anthropic
        except ImportError:
            raise ImportError(
                "The 'anthropic' package is required for the Anthropic provider.\n"
                "Install it with:  pip install anthropic"
            )

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set.\n"
                "Export it before running:  export ANTHROPIC_API_KEY=your-key-here"
            )

        self._client = self._anthropic.Anthropic(api_key=api_key)
        self._model_name = model or DEFAULT_ANTHROPIC_MODEL

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model(self) -> str:
        return self._model_name

    def chat(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model_name,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=messages,
        )
        return response.content[0].text.strip()
