"""Abstract base class for AI provider backends."""

from abc import ABC, abstractmethod
from typing import List, Dict


class BaseProvider(ABC):
    """
    Common interface that every provider must implement.

    messages format (OpenAI-compatible, shared across providers):
        [
            {"role": "user",      "content": "..."},
            {"role": "assistant", "content": "..."},
            ...
        ]
    Providers are responsible for translating to their own wire format.
    """

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        """
        Send a conversation turn and return the assistant's reply as a string.

        Args:
            messages:      Full conversation history.
            system_prompt: Static system instruction (will be prompt-cached where supported).
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. 'gemini', 'anthropic')."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Model identifier in use."""
