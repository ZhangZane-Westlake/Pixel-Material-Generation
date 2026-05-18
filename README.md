# Pixel-Material-Generation

Generate pixel-style APNG animations from natural-language prompts.

## Overview

This project turns a prompt such as:

> 上方是一只奔跑的小猫，下方是进度条，色调为绿色

into a transparent pixel-art APNG you can drop into video editing software.

Pipeline:

1. Parse the prompt into a structured `SceneSpec` using a provider model.
2. Render pixel frames locally with Pillow.
3. Export the result as APNG.
4. Open the result in a native macOS GUI when needed.

## Default provider

The default prompt parser uses **OpenAI GPT-5.5**.

Supported providers:
- `openai` — default, requires `OPENAI_API_KEY`
- `claude` — optional, requires `ANTHROPIC_API_KEY`
- `local` — offline parser for tests and demos

## Installation

```bash
python -m pip install -e .[dev]
```

On macOS, install the GUI dependencies as well:

```bash
python -m pip install pywebview pyobjc
```

## Environment variables

Create a `.env` file or export these in your shell:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

Only the provider you use needs a key.

## Usage

CLI:

```bash
pixel-apng generate "上方是一只奔跑的小猫，下方是进度条，色调为绿色" --output output/cat_progress.apng
```

Use the local provider for offline testing:

```bash
pixel-apng generate "上方是一只奔跑的小猫，下方是进度条，色调为绿色" --provider local --output output/cat_progress.apng
```

GUI:

```bash
python -m pixel_apng.gui
```

## Prompt understanding

The structured scene parser supports:

- Regions: `上方/top`, `下方/bottom`, `左侧/left`, `右侧/right`, `中间/center`
- Subjects: cat, dog, progress bar, star, cloud, heart, arrow, text, box
- Motions: run, bounce, blink, fill, pulse, spin
- Palettes: green, blue, red, pink, yellow, purple, retro

Example:

```bash
pixel-apng generate "左侧是一朵云，右侧是星星，中间是文字，色调为紫色" --provider local --output output/cloud_star_text.apng
```

## Output

- APNG with alpha channel
- Default internal canvas: `128x128`
- Default scale: `4x`
- Default animation: `12 fps`, `2 seconds`, seamless loop

## macOS packaging

Build a local `.app` bundle and `.dmg` from the `mac/` directory:

```bash
chmod +x mac/build.sh
./mac/build.sh
```

The script creates an app bundle under `build/macos/` and a DMG in `dist/`.

## Development

Run tests:

```bash
pytest
```

Run linting:

```bash
ruff check .
```

Run type checks:

```bash
mypy src
```

## Notes

- Prompt caching is most effective when the system prompt and schema remain stable.
- The prompt parser is intentionally provider-agnostic so you can swap models later without changing the renderer.
