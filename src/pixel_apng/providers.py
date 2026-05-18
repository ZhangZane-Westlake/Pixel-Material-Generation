"""LLM provider abstraction for prompt-to-scene parsing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from pixel_apng.models import SceneSpec


class ProviderName(str):
    """Provider identifiers."""


@dataclass(frozen=True)
class ParserConfig:
    """Configuration for prompt parsing."""

    model: str
    max_output_tokens: int = 1024


class PromptParser(ABC):
    """Convert a prompt into a structured scene specification."""

    @abstractmethod
    def parse(self, prompt: str) -> SceneSpec:
        """Parse a prompt into a scene spec.

        Args:
            prompt: User input prompt.

        Returns:
            Parsed scene specification.
        """


@dataclass(frozen=True)
class ParserSelection:
    """Selected parser provider."""

    provider: str
    parser: PromptParser
