"""Claude API client for policy generation."""

import os
from typing import List, Dict

from ghascompliance.ai.prompts import (
    SINGLE_SHOT_SYSTEM_PROMPT,
    INTERACTIVE_SYSTEM_PROMPT,
    RETRY_USER_MESSAGE,
)

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048


def _get_client():
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "The 'anthropic' package is required for AI features.\n"
            "Install it with:  pip install anthropic"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY environment variable is not set.\n"
            "Export it before running:  export ANTHROPIC_API_KEY=your-key-here"
        )

    return anthropic.Anthropic(api_key=api_key)


def generate_single_shot(description: str, model: str = DEFAULT_MODEL) -> str:
    """Generate a policy YAML from a natural language description."""
    client = _get_client()

    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SINGLE_SHOT_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": description}],
    )
    return response.content[0].text.strip()


def generate_with_error_fix(
    description: str,
    previous_yaml: str,
    error: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """Retry generation after a validation failure, feeding the error back to Claude."""
    client = _get_client()

    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SINGLE_SHOT_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {"role": "user", "content": description},
            {"role": "assistant", "content": previous_yaml},
            {
                "role": "user",
                "content": RETRY_USER_MESSAGE.format(error=error),
            },
        ],
    )
    return response.content[0].text.strip()


def chat_turn(
    messages: List[Dict[str, str]],
    model: str = DEFAULT_MODEL,
) -> str:
    """Send one turn of the interactive conversation and return Claude's response."""
    client = _get_client()

    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": INTERACTIVE_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    )
    return response.content[0].text.strip()
