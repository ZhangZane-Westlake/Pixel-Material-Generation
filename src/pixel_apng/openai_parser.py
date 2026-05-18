"""OpenAI-backed prompt parser."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from pixel_apng.models import SceneSpec
from pixel_apng.providers import ParserConfig, PromptParser

_SYSTEM_PROMPT = """
Convert the user's prompt into a structured pixel animation scene.
Return only valid JSON matching the schema.

Use these enums when possible:
- regions: top, middle, bottom, left, right, center
- subjects: object, text, progress_bar, unknown
- motions: run, bounce, blink, fill, pulse, spin, none
- palettes: green, blue, red, pink, yellow, purple, retro

Prefer explicit layout from the prompt. For example, "上方" maps to top,
"下方" maps to bottom, "左侧" maps to left, and "中间" maps to center.
If the prompt mentions a progress/loading bar, use subject progress_bar and motion fill.
For visible entities such as animals, robots, plants, tools, weather objects,
or fantasy props, use subject object and keep the concrete object phrase inside
content so it can be rendered procedurally.
Keep the scene simple enough for procedural pixel rendering.
""".strip()


@dataclass(frozen=True)
class OpenAIPromptParser(PromptParser):
    """Parse prompts with OpenAI models."""

    config: ParserConfig
    client: OpenAI

    def parse(self, prompt: str) -> SceneSpec:
        """Parse a prompt into a scene spec.

        Args:
            prompt: User input prompt.

        Returns:
            Parsed scene specification.
        """
        response = self.client.responses.parse(
            model=self.config.model,
            input=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            text_format=SceneSpec,
        )
        parsed = response.output_parsed
        if not isinstance(parsed, SceneSpec):
            raise ValueError("OpenAI parser did not return a valid SceneSpec")
        return parsed


class ClaudePromptParser(PromptParser):
    """Parse prompts with Anthropic Claude."""

    def __init__(self, client: Any, config: ParserConfig) -> None:
        self._client = client
        self._config = config

    def parse(self, prompt: str) -> SceneSpec:
        """Parse a prompt into a scene spec.

        Args:
            prompt: User input prompt.

        Returns:
            Parsed scene specification.
        """
        message = self._client.messages.create(
            model=self._config.model,
            max_tokens=self._config.max_output_tokens,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": SceneSpec.model_json_schema(),
                }
            },
        )
        text = next((block.text for block in message.content if block.type == "text"), None)
        if text is None:
            raise ValueError("Claude parser did not return text content")
        return SceneSpec.model_validate_json(text)


def default_parser_provider(provider: str, model: str) -> str:
    """Return the default provider name for a requested backend."""

    if provider not in {"openai", "claude"}:
        raise ValueError(f"Unsupported provider: {provider}")
    return provider


def parse_prompt_with_fallback(prompt: str, provider: str = "openai") -> SceneSpec:
    """Parse a prompt using a provider-specific parser.

    Args:
        prompt: User input prompt.
        provider: Provider name.

    Returns:
        Parsed scene specification.
    """
    raise NotImplementedError("Provider wiring is handled in the CLI")
