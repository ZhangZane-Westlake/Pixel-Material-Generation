"""Command-line interface for the pixel APNG generator."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from anthropic import Anthropic
from openai import OpenAI

from pixel_apng.exporter import PixelExporter
from pixel_apng.local_parser import LocalPromptParser
from pixel_apng.openai_parser import ClaudePromptParser, OpenAIPromptParser
from pixel_apng.providers import ParserConfig, PromptParser
from pixel_apng.renderer import PixelRenderer

app = typer.Typer(add_completion=False)


class ProviderError(RuntimeError):
    """Raised when a requested provider cannot be initialized."""


class OpenAIGPT55Parser(OpenAIPromptParser):
    """OpenAI parser preconfigured for GPT-5.5."""

    def __init__(self) -> None:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        super().__init__(config=ParserConfig(model="gpt-5.5"), client=client)


class ClaudeParserWrapper(ClaudePromptParser):
    """Claude parser preconfigured from environment variables."""

    def __init__(self) -> None:
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        super().__init__(client=client, config=ParserConfig(model="claude-opus-4-7"))


@app.callback()
def main() -> None:
    """Pixel APNG generator."""


def build_parser(provider: str) -> PromptParser:
    """Build a parser for the requested provider.

    Args:
        provider: Provider name.

    Returns:
        Prompt parser implementation.
    """
    if provider == "local":
        return LocalPromptParser()
    if provider == "openai":
        if "OPENAI_API_KEY" not in os.environ:
            raise ProviderError("OPENAI_API_KEY is required for the default provider")
        return OpenAIGPT55Parser()
    if provider == "claude":
        if "ANTHROPIC_API_KEY" not in os.environ:
            raise ProviderError("ANTHROPIC_API_KEY is required for the Claude provider")
        return ClaudeParserWrapper()
    raise ProviderError(f"Unsupported provider: {provider}")


@app.command()
def generate(
    prompt: Annotated[str, typer.Argument(help="Prompt describing the animation.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output APNG path.")],
    provider: Annotated[
        str,
        typer.Option(help="Prompt parser provider: openai, claude, or local."),
    ] = "openai",
) -> None:
    """Generate an APNG from a natural-language prompt."""
    parser = build_parser(provider)
    scene = parser.parse(prompt)
    renderer = PixelRenderer()
    frames = renderer.render_frames(scene)
    exporter = PixelExporter()
    exporter.save_apng(frames, output, scene.animation.fps)
    typer.echo(f"Saved APNG to {output}")


if __name__ == "__main__":
    app()
