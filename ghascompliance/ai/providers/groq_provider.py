"""Groq provider — free tier, fast inference, no billing required."""

import os
from typing import List, Dict

from ghascompliance.ai.providers.base import BaseProvider

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


class GroqProvider(BaseProvider):
    """
    Backed by the Groq SDK (OpenAI-compatible API).
    Free tier: generous daily token limits, no credit card required.

    Required env var: GROQ_API_KEY
    Get a free key at: https://console.groq.com
    """

    def __init__(self, model: str | None = None):
        try:
            from groq import Groq
            self._Groq = Groq
        except ImportError:
            raise ImportError(
                "The 'groq' package is required for the Groq provider.\n"
                "Install it with:  pip install groq"
            )

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY environment variable is not set.\n"
                "Get a free key at https://console.groq.com\n"
                "Then run:  export GROQ_API_KEY=your-key-here"
            )

        self._client = self._Groq(api_key=api_key)
        self._model_name = model or DEFAULT_GROQ_MODEL

    @property
    def name(self) -> str:
        return "groq"

    @property
    def model(self) -> str:
        return self._model_name

    def chat(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        # Groq follows the OpenAI chat format: system message + conversation history
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        completion = self._client.chat.completions.create(
            model=self._model_name,
            messages=full_messages,
            max_tokens=2048,
        )
        return completion.choices[0].message.content.strip()
