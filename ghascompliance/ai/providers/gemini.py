"""Google Gemini provider using the current google-genai SDK."""

import os
from typing import List, Dict

from ghascompliance.ai.providers.base import BaseProvider

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


class GeminiProvider(BaseProvider):
    """
    Backed by the google-genai SDK (google.genai).
    Free tier: 1 500 requests/day, 15 RPM — enough for thesis work.

    Required env var: GEMINI_API_KEY  (also accepts GOOGLE_API_KEY)
    Get a free key at: https://aistudio.google.com/app/apikey
    """

    def __init__(self, model: str | None = None):
        try:
            from google import genai
            from google.genai import types as genai_types
            self._genai = genai
            self._types = genai_types
        except ImportError:
            raise ImportError(
                "The 'google-genai' package is required for the Gemini provider.\n"
                "Install it with:  pip install google-genai"
            )

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY environment variable is not set.\n"
                "Get a free key at https://aistudio.google.com/app/apikey\n"
                "Then run:  export GEMINI_API_KEY=your-key-here"
            )

        self._client = self._genai.Client(api_key=api_key)
        self._model_name = model or DEFAULT_GEMINI_MODEL

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model(self) -> str:
        return self._model_name

    def chat(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        types = self._types

        # Convert messages to google-genai Content objects.
        # Gemini uses "model" where Anthropic/OpenAI use "assistant".
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                types.Content(role=role, parts=[types.Part(text=msg["content"])])
            )

        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=2048,
                ),
                contents=contents,
            )
        except Exception as exc:
            exc_str = str(exc)
            if "RESOURCE_EXHAUSTED" in exc_str or "429" in exc_str or "quota" in exc_str.lower():
                raise RuntimeError(
                    "Gemini API quota exceeded.\n\n"
                    "If you just created the key, make sure it was created at\n"
                    "  https://aistudio.google.com/app/apikey  (not Google Cloud Console).\n"
                    "Free-tier quotas are only active for AI Studio keys.\n\n"
                    "Alternatively, use the Groq provider (also free):\n"
                    "  export GROQ_API_KEY=your-key  (get one at https://console.groq.com)\n"
                    "  python -m ghascompliance generate-policy --provider groq --description '...'"
                ) from exc
            raise

        return response.text.strip()
