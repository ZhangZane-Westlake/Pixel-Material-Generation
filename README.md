# Pixel-Material-Generation

Generate pixel-style APNG animations from natural-language prompts.

## Overview

This project turns a prompt such as:

> 上方是一只奔跑的小猫，下方是进度条，色调为绿色

into a transparent pixel-art APNG you can drop into video editing software.

Pipeline:

1. Parse the prompt into a structured `SceneSpec` using a provider model.
2. Composition planner: score candidate layouts and choose a scene composition.
3. Convert the chosen composition into a `RenderPlan`.
4. Render pixel frames locally with Pillow from the `RenderPlan`.
5. Export the result as APNG.
6. Open the result in a native macOS GUI when needed.

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
pixel-apng generate "上方是一台旋转的机器人，下方是进度条，色调为绿色" --output output/robot_progress.apng
```

Use the local provider for offline testing:

```bash
pixel-apng generate "上方是一台旋转的机器人，下方是进度条，色调为绿色" --provider local --output output/robot_progress.apng
```

GUI:

```bash
python -m pixel_apng.gui
```

The GUI stores API key and Base URL settings locally in `~/.pixel-material-generator/settings.db`.
The desktop UI uses a pixel-tool-inspired control deck with a dedicated preview stage,
provider cards, prompt presets, and separate `生成器` / `设置` views so API configuration
is not mixed into the generation workspace.

## Prompt understanding

LLM only parses the prompt into a semantic `SceneSpec`. The provider does not
generate the final pixel artwork directly. Composition planning and rendering
happen locally, which keeps the rendering path deterministic and testable.

The structured scene parser supports:

- Regions: `上方/top`, `下方/bottom`, `左侧/left`, `右侧/right`, `中间/center`
- Subjects: `object`, `progress_bar`, `text`
- Motions: run, bounce, blink, fill, pulse, spin
- Palettes: green, blue, red, pink, yellow, purple, retro

For normal visual entities, the parser keeps the concrete object phrase in `content`
and the renderer generates a procedural pixel object from that description instead of
selecting from a fixed sprite library. This means prompts like `机器人`, `蘑菇`, `热气球`,
or `机械鲸鱼` can render without adding new built-in assets first.

Example:

```bash
pixel-apng generate "左侧是一朵云，右侧是一颗星星，中间是文字，色调为紫色" --provider local --output output/cloud_star_text.apng
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

The packaged app uses the bundled virtual environment and does not install dependencies at launch.

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
