"""Orchestrates AI generation calls using an injected provider."""

from typing import List, Dict

from ghascompliance.ai.providers.base import BaseProvider
from ghascompliance.ai.prompts import (
    SINGLE_SHOT_SYSTEM_PROMPT,
    INTERACTIVE_SYSTEM_PROMPT,
    RETRY_USER_MESSAGE,
)


def generate_single_shot(description: str, provider: BaseProvider) -> str:
    """Generate a policy YAML from a one-line natural language description."""
    return provider.chat(
        [{"role": "user", "content": description}],
        SINGLE_SHOT_SYSTEM_PROMPT,
    )


def generate_with_error_fix(
    description: str,
    previous_yaml: str,
    error: str,
    provider: BaseProvider,
) -> str:
    """Retry after a validation failure, feeding the schema error back to the model."""
    messages: List[Dict[str, str]] = [
        {"role": "user", "content": description},
        {"role": "assistant", "content": previous_yaml},
        {"role": "user", "content": RETRY_USER_MESSAGE.format(error=error)},
    ]
    return provider.chat(messages, SINGLE_SHOT_SYSTEM_PROMPT)


def chat_turn(messages: List[Dict[str, str]], provider: BaseProvider) -> str:
    """Send one turn of the interactive conversation and return the model's reply."""
    return provider.chat(messages, INTERACTIVE_SYSTEM_PROMPT)
