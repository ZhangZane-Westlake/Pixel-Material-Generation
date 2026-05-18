"""GUI application for generating pixel APNG animations."""

from __future__ import annotations

import base64
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import webview

from pixel_apng.cli import ProviderError
from pixel_apng.exporter import PixelExporter
from pixel_apng.local_parser import LocalPromptParser
from pixel_apng.openai_parser import ClaudePromptParser, OpenAIPromptParser
from pixel_apng.providers import ParserConfig, PromptParser
from pixel_apng.renderer import PixelRenderer
from pixel_apng.settings_store import export_settings, load_settings, save_settings

WINDOW_TITLE: Final[str] = "Pixel Material Generator"
DEFAULT_PROMPT: Final[str] = "上方是一只奔跑的小猫，下方是进度条，色调为绿色"
DEFAULT_SETTINGS: Final[dict[str, str]] = {
    "openai_api_key": "",
    "openai_base_url": "",
    "anthropic_api_key": "",
    "anthropic_base_url": "",
}


def _normalize_base_url(base_url: str) -> str:
    """Normalize optional base URLs before use."""
    return base_url.strip()


class OpenAIGuiParser(OpenAIPromptParser):
    """OpenAI parser configured from saved GUI settings."""

    def __init__(self, api_key: str, base_url: str) -> None:
        """Create an OpenAI parser from stored credentials."""
        from openai import OpenAI

        if base_url:
            client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            client = OpenAI(api_key=api_key)
        super().__init__(config=ParserConfig(model="gpt-5.5"), client=client)


class ClaudeGuiParser(ClaudePromptParser):
    """Claude parser configured from saved GUI settings."""

    def __init__(self, api_key: str, base_url: str) -> None:
        """Create a Claude parser from stored credentials."""
        from anthropic import Anthropic

        if base_url:
            client = Anthropic(api_key=api_key, base_url=base_url)
        else:
            client = Anthropic(api_key=api_key)
        super().__init__(client=client, config=ParserConfig(model="claude-opus-4-7"))


class PixelApngGuiApi:
    """Bridge between the native WebView and the APNG generator."""

    def __init__(self) -> None:
        """Initialize renderer, exporter, and persisted settings."""
        self._renderer = PixelRenderer()
        self._exporter = PixelExporter()
        self._settings = self.get_settings()

    def get_settings(self) -> dict[str, str]:
        """Return the stored GUI settings."""
        return {**DEFAULT_SETTINGS, **load_settings()}

    def save_settings(self, settings: dict[str, str]) -> dict[str, bool]:
        """Persist settings entered in the GUI."""
        normalized = {key: str(settings.get(key, "")).strip() for key in DEFAULT_SETTINGS}
        save_settings(normalized)
        self._settings = {**DEFAULT_SETTINGS, **normalized}
        return {"ok": True}

    def export_settings(self) -> dict[str, str]:
        """Export the current GUI settings as JSON text."""
        return {"content": export_settings()}

    def _build_parser(self, provider: str) -> PromptParser:
        settings = self._settings
        if provider == "local":
            return LocalPromptParser()
        if provider == "openai":
            api_key = settings["openai_api_key"] or os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                raise ProviderError("请先设置 OpenAI API Key")
            return OpenAIGuiParser(api_key, _normalize_base_url(settings["openai_base_url"]))
        if provider == "claude":
            api_key = settings["anthropic_api_key"] or os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                raise ProviderError("请先设置 Anthropic API Key")
            return ClaudeGuiParser(api_key, _normalize_base_url(settings["anthropic_base_url"]))
        raise ProviderError(f"Unsupported provider: {provider}")

    def generate(self, prompt: str, provider: str) -> dict[str, str | bool]:
        """Generate an APNG and return a data URL for preview/download."""
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            return {"ok": False, "error": "请输入动画描述。"}

        try:
            parser = self._build_parser(provider)
            scene = parser.parse(normalized_prompt)
            frames = self._renderer.render_frames(scene)
            with tempfile.NamedTemporaryFile(suffix=".apng", delete=False) as temporary_file:
                output_path = Path(temporary_file.name)
            self._exporter.save_apng(frames, output_path, scene.animation.fps)
            encoded_apng = base64.b64encode(output_path.read_bytes()).decode("ascii")
            output_path.unlink(missing_ok=True)
        except ProviderError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            return {"ok": False, "error": f"生成失败：{exc}"}

        return {
            "ok": True,
            "title": scene.title or "pixel-animation",
            "dataUrl": f"data:image/png;base64,{encoded_apng}",
        }

    def save(self, data_url: str, filename: str) -> dict[str, str | bool]:
        """Save a generated APNG through a native file dialog."""
        if not data_url.startswith("data:image/png;base64,"):
            return {"ok": False, "error": "没有可保存的 APNG 数据。"}
        save_window = webview.windows[0]
        save_result = save_window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=filename or "pixel-animation.apng",
            file_types=("APNG Files (*.apng)", "PNG Files (*.png)", "All Files (*.*)"),
        )
        if not save_result:
            return {"ok": False, "error": "已取消保存。"}
        if isinstance(save_result, Sequence) and not isinstance(save_result, (str, bytes)):
            target_path = Path(save_result[0])
        else:
            target_path = Path(save_result)
        target_path.write_bytes(base64.b64decode(data_url.split(",", maxsplit=1)[1]))
        return {"ok": True, "path": str(target_path)}


def build_html() -> str:
    """Build the self-contained GUI HTML page."""
    return f"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{WINDOW_TITLE}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6efdf;
      --bg-deep: #f0dfbc;
      --surface: rgba(255, 251, 242, 0.92);
      --surface-strong: #fffdfa;
      --surface-muted: rgba(250, 240, 218, 0.84);
      --border: rgba(116, 90, 47, 0.18);
      --border-strong: rgba(87, 63, 28, 0.34);
      --text: #1d2230;
      --muted: #5d6471;
      --accent: #23c47e;
      --accent-deep: #149a61;
      --accent-alt: #4d6bff;
      --accent-warm: #ff805d;
      --danger: #c43d35;
      --success: #0e9a5d;
      --shadow: 0 28px 80px rgba(60, 43, 12, 0.14);
      --pixel-shadow: 8px 8px 0 rgba(34, 26, 13, 0.08);
      --radius-lg: 28px;
      --radius-md: 18px;
      --radius-sm: 12px;
      font-family: 'Avenir Next', 'SF Pro Rounded', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 12% 18%, rgba(255, 255, 255, 0.82) 0%, transparent 26%),
        radial-gradient(circle at 88% 16%, rgba(255, 150, 103, 0.16) 0%, transparent 24%),
        radial-gradient(circle at 86% 84%, rgba(35, 196, 126, 0.2) 0%, transparent 20%),
        linear-gradient(180deg, #fbf4e5 0%, #f4e6c8 100%);
      color: var(--text);
      position: relative;
      overflow-x: hidden;
    }}
    body::before {{
      content: '';
      position: fixed;
      inset: 0;
      background:
        linear-gradient(rgba(255, 255, 255, 0.1) 1px, transparent 1px) 0 0 / 24px 24px,
        linear-gradient(90deg, rgba(255, 255, 255, 0.08) 1px, transparent 1px) 0 0 / 24px 24px;
      opacity: 0.42;
      pointer-events: none;
    }}
    main {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 32px 28px 40px;
      position: relative;
      z-index: 1;
    }}
    .hero-shell {{
      position: relative;
      overflow: hidden;
      margin-bottom: 18px;
      padding: 28px;
      border-radius: 32px;
      background:
        linear-gradient(145deg, rgba(255, 253, 248, 0.96), rgba(255, 246, 229, 0.9));
      border: 1px solid rgba(91, 68, 31, 0.18);
      box-shadow: var(--shadow);
    }}
    .hero-shell::before {{
      content: '';
      position: absolute;
      inset: 0;
      background:
        linear-gradient(135deg, rgba(77, 107, 255, 0.08), transparent 28%),
        linear-gradient(315deg, rgba(35, 196, 126, 0.12), transparent 36%);
      pointer-events: none;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
      gap: 24px;
      align-items: stretch;
      position: relative;
      z-index: 1;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #463413;
      background: rgba(255, 240, 201, 0.92);
      border: 1px solid rgba(116, 90, 47, 0.18);
    }}
    .eyebrow::before {{
      content: '';
      width: 10px;
      height: 10px;
      border-radius: 2px;
      background: linear-gradient(135deg, var(--accent), var(--accent-alt));
      box-shadow: 4px 4px 0 rgba(29, 34, 48, 0.1);
    }}
    .hero-copy h1 {{
      margin: 16px 0 0;
      font-size: clamp(34px, 4.5vw, 54px);
      line-height: 1.04;
      letter-spacing: -0.05em;
      max-width: 12ch;
    }}
    .hero-copy p {{
      max-width: 62ch;
      margin: 14px 0 0;
      color: var(--muted);
      line-height: 1.75;
      font-size: 16px;
    }}
    .pill-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 14px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.76);
      border: 1px solid var(--border);
      color: #403728;
      font-size: 12px;
      font-weight: 700;
    }}
    .pill::before {{
      content: '';
      width: 8px;
      height: 8px;
      border-radius: 2px;
      background: var(--accent-warm);
    }}
    .hero-aside {{
      display: grid;
      gap: 14px;
      align-content: space-between;
      justify-items: stretch;
    }}
    .nav-bar {{
      display: inline-grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      padding: 8px;
      border-radius: 24px;
      background: rgba(255, 255, 255, 0.9);
      border: 1px solid rgba(87, 63, 28, 0.16);
      box-shadow: var(--pixel-shadow);
    }}
    .nav-button {{
      border: 1px solid transparent;
      border-radius: 16px;
      padding: 14px 18px;
      font-size: 14px;
      font-weight: 800;
      color: var(--muted);
      background: transparent;
      cursor: pointer;
      transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
    }}
    .nav-button.active {{
      color: #17351f;
      background: linear-gradient(135deg, rgba(35, 196, 126, 0.18), rgba(77, 107, 255, 0.16));
      border-color: rgba(22, 125, 82, 0.18);
      box-shadow: inset 0 0 0 1px rgba(35, 196, 126, 0.14);
    }}
    .nav-button:hover {{ transform: translateY(-1px); }}
    .hero-stat-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .hero-stat {{
      padding: 18px;
      border-radius: 20px;
      background: rgba(34, 26, 13, 0.92);
      color: #fff6e6;
      box-shadow: var(--pixel-shadow);
    }}
    .hero-stat strong {{
      display: block;
      font-size: 26px;
      letter-spacing: -0.04em;
    }}
    .hero-stat span {{
      display: block;
      margin-top: 6px;
      font-size: 13px;
      line-height: 1.55;
      color: rgba(255, 246, 230, 0.76);
    }}
    .status {{
      display: flex;
      align-items: center;
      gap: 12px;
      min-height: 60px;
      margin: 0 0 20px;
      padding: 14px 18px;
      border-radius: 20px;
      background: rgba(255, 251, 244, 0.9);
      color: var(--muted);
      border: 1px solid rgba(87, 63, 28, 0.12);
      box-shadow: 0 14px 34px rgba(60, 43, 12, 0.08);
    }}
    .status::before {{
      content: '';
      flex: 0 0 auto;
      width: 12px;
      height: 12px;
      border-radius: 3px;
      background: rgba(93, 100, 113, 0.4);
      box-shadow: 4px 4px 0 rgba(29, 34, 48, 0.08);
    }}
    .status.error {{
      color: var(--danger);
      background: #fff0ec;
      border-color: rgba(196, 61, 53, 0.2);
    }}
    .status.error::before {{ background: var(--danger); }}
    .status.success {{
      color: var(--success);
      background: #effcf4;
      border-color: rgba(14, 154, 93, 0.2);
    }}
    .status.success::before {{ background: var(--success); }}
    .view {{
      display: none;
      gap: 18px;
    }}
    .view.active {{
      display: grid;
    }}
    .generate-layout {{
      grid-template-columns: minmax(420px, 0.95fr) minmax(440px, 1.05fr);
    }}
    .settings-layout {{
      grid-template-columns: minmax(0, 1fr);
    }}
    .panel {{
      background: var(--surface);
      border: 1px solid rgba(87, 63, 28, 0.14);
      border-radius: var(--radius-lg);
      padding: 28px;
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
    }}
    .panel::before {{
      content: '';
      position: absolute;
      inset: 0 auto auto 0;
      width: 160px;
      height: 160px;
      background: radial-gradient(circle, rgba(77, 107, 255, 0.1) 0%, transparent 70%);
      pointer-events: none;
    }}
    .panel > * {{ position: relative; z-index: 1; }}
    .panel-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 14px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 244, 221, 0.92);
      border: 1px solid rgba(116, 90, 47, 0.14);
      color: #5d4721;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .panel-badge::before {{
      content: '';
      width: 8px;
      height: 8px;
      border-radius: 2px;
      background: var(--accent-alt);
    }}
    .section-title {{
      margin: 0 0 8px;
      font-size: 28px;
      letter-spacing: -0.04em;
    }}
    .section-copy {{
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.7;
    }}
    .subtle-divider {{
      height: 1px;
      margin: 20px 0;
      background: linear-gradient(90deg, rgba(87, 63, 28, 0.16), transparent);
    }}
    label {{
      display: block;
      margin: 16px 0 8px;
      font-weight: 800;
      font-size: 13px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: #453922;
    }}
    input, textarea, select {{
      width: 100%;
      border: 1px solid rgba(87, 63, 28, 0.22);
      border-radius: 18px;
      background: rgba(255, 253, 248, 0.92);
      color: var(--text);
      padding: 14px 16px;
      font-size: 15px;
      outline: none;
      transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease, transform 0.18s ease;
    }}
    input:focus, textarea:focus, select:focus {{
      border-color: rgba(35, 196, 126, 0.62);
      box-shadow: 0 0 0 5px rgba(35, 196, 126, 0.12);
      transform: translateY(-1px);
    }}
    textarea {{
      min-height: 220px;
      resize: vertical;
      line-height: 1.7;
    }}
    .provider-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }}
    .provider-card {{
      border: 1px solid rgba(87, 63, 28, 0.16);
      border-radius: 20px;
      padding: 16px;
      background: rgba(255, 255, 255, 0.58);
      cursor: pointer;
      transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
    }}
    .provider-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 18px 36px rgba(60, 43, 12, 0.1);
    }}
    .provider-card.active {{
      background: linear-gradient(135deg, rgba(35, 196, 126, 0.14), rgba(77, 107, 255, 0.12));
      border-color: rgba(35, 196, 126, 0.28);
      box-shadow: inset 0 0 0 1px rgba(35, 196, 126, 0.18);
    }}
    .provider-card strong {{
      display: block;
      font-size: 16px;
      letter-spacing: -0.02em;
    }}
    .provider-card span {{
      display: block;
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }}
    .prompt-shell {{
      position: relative;
      padding: 14px;
      border-radius: 24px;
      background: rgba(255, 250, 241, 0.78);
      border: 1px solid rgba(87, 63, 28, 0.1);
    }}
    .prompt-shell textarea {{
      min-height: 190px;
      background: rgba(255, 253, 248, 0.95);
    }}
    .helper {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 10px;
      line-height: 1.6;
    }}
    .preset-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 16px;
    }}
    .preset-button {{
      border: 1px solid rgba(87, 63, 28, 0.14);
      border-radius: 18px;
      padding: 14px;
      text-align: left;
      background: rgba(255, 255, 255, 0.72);
      color: #342917;
      box-shadow: none;
      cursor: pointer;
      transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background 0.18s ease;
    }}
    .preset-button:hover {{
      transform: translateY(-2px);
      border-color: rgba(77, 107, 255, 0.18);
      box-shadow: 0 14px 28px rgba(60, 43, 12, 0.08);
    }}
    .preset-button strong {{
      display: block;
      font-size: 14px;
      margin-bottom: 6px;
      color: #211b10;
    }}
    .preset-button span {{
      display: block;
      font-size: 13px;
      line-height: 1.55;
      color: var(--muted);
    }}
    .actions, .footer-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 20px;
    }}
    button:not(.nav-button):not(.provider-card):not(.preset-button) {{
      border: 1px solid transparent;
      border-radius: 18px;
      padding: 14px 20px;
      font-size: 15px;
      font-weight: 800;
      color: white;
      background: linear-gradient(135deg, var(--accent), var(--accent-deep));
      cursor: pointer;
      box-shadow: 0 16px 32px rgba(20, 154, 97, 0.22);
      transition: transform 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease, background 0.18s ease;
    }}
    button:not(.nav-button):not(.provider-card):not(.preset-button):hover {{
      transform: translateY(-2px);
      box-shadow: 0 18px 36px rgba(20, 154, 97, 0.26);
    }}
    button.secondary:not(.preset-button) {{
      color: var(--text);
      background: rgba(255, 255, 255, 0.72);
      border-color: rgba(87, 63, 28, 0.18);
      box-shadow: none;
    }}
    button.secondary:not(.preset-button):hover {{
      box-shadow: 0 12px 24px rgba(60, 43, 12, 0.08);
    }}
    button:not(.nav-button):not(.provider-card):not(.preset-button):focus-visible,
    .nav-button:focus-visible,
    .provider-card:focus-visible,
    .preset-button:focus-visible {{
      outline: 3px solid rgba(77, 107, 255, 0.35);
      outline-offset: 2px;
    }}
    button:not(.nav-button):not(.provider-card):not(.preset-button):disabled {{
      opacity: .55;
      cursor: not-allowed;
    }}
    .preview {{
      display: grid;
      place-items: center;
      min-height: 600px;
      padding: 24px;
      border-radius: 30px;
      border: 1px solid rgba(87, 63, 28, 0.16);
      background:
        linear-gradient(180deg, rgba(36, 31, 20, 0.96), rgba(24, 22, 16, 0.98));
      overflow: hidden;
      position: relative;
    }}
    .preview::before {{
      content: '';
      position: absolute;
      inset: 20px;
      border-radius: 20px;
      background:
        linear-gradient(90deg, rgba(255, 255, 255, 0.06) 1px, transparent 1px) 0 0 / 26px 26px,
        linear-gradient(rgba(255, 255, 255, 0.06) 1px, transparent 1px) 0 0 / 26px 26px;
      pointer-events: none;
    }}
    .preview > * {{ position: relative; z-index: 1; }}
    .preview-stage {{
      display: grid;
      gap: 18px;
      justify-items: center;
      width: min(100%, 640px);
    }}
    .preview-frame {{
      display: grid;
      place-items: center;
      width: min(100%, 560px);
      min-height: 360px;
      padding: 22px;
      border-radius: 24px;
      background:
        linear-gradient(180deg, rgba(255, 252, 246, 0.96), rgba(243, 233, 214, 0.94));
      border: 1px solid rgba(255, 255, 255, 0.22);
      box-shadow: 0 24px 48px rgba(0, 0, 0, 0.22);
    }}
    .preview-frame img {{
      max-width: 100%;
      image-rendering: pixelated;
      filter: drop-shadow(0 18px 28px rgba(0, 0, 0, 0.16));
    }}
    .preview-empty {{
      display: grid;
      gap: 18px;
      justify-items: center;
      text-align: center;
      color: rgba(255, 246, 230, 0.88);
    }}
    .preview-empty strong {{
      font-size: 24px;
      letter-spacing: -0.03em;
    }}
    .preview-empty p {{
      max-width: 34ch;
      margin: 0;
      line-height: 1.7;
      color: rgba(255, 246, 230, 0.68);
    }}
    .pixel-orb {{
      width: 112px;
      height: 112px;
      border-radius: 24px;
      background:
        linear-gradient(135deg, rgba(35, 196, 126, 0.95), rgba(77, 107, 255, 0.92));
      box-shadow:
        0 0 0 8px rgba(255, 255, 255, 0.08),
        18px 18px 0 rgba(255, 128, 93, 0.28);
      transform: rotate(-6deg);
    }}
    .preview-meta {{
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 10px;
    }}
    .preview-meta span {{
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.08);
      color: rgba(255, 246, 230, 0.82);
      font-size: 12px;
      font-weight: 700;
    }}
    .workflow-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 20px;
    }}
    .workflow-card,
    .settings-box {{
      background: rgba(255, 250, 241, 0.82);
      border: 1px solid rgba(87, 63, 28, 0.12);
      border-radius: 22px;
      padding: 18px;
    }}
    .workflow-card strong,
    .info-card strong {{
      display: block;
      margin-bottom: 8px;
      font-size: 14px;
      letter-spacing: -0.01em;
    }}
    .workflow-card span,
    .info-card span {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }}
    .settings-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }}
    .settings-header-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(280px, 0.9fr);
      gap: 18px;
      margin-bottom: 18px;
    }}
    .settings-note {{
      padding: 20px;
      border-radius: 24px;
      background: rgba(34, 26, 13, 0.94);
      color: #fff7e8;
      box-shadow: var(--pixel-shadow);
    }}
    .settings-note strong {{
      display: block;
      margin-bottom: 10px;
      font-size: 16px;
    }}
    .settings-note p {{
      margin: 0;
      color: rgba(255, 247, 232, 0.76);
      line-height: 1.7;
      font-size: 14px;
    }}
    .info-strip {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
    }}
    .info-card {{
      padding: 16px;
      border-radius: 20px;
      background: rgba(255, 250, 241, 0.82);
      border: 1px solid rgba(87, 63, 28, 0.12);
      transition: transform 0.18s ease, box-shadow 0.18s ease;
    }}
    .info-card:hover,
    .workflow-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 16px 30px rgba(60, 43, 12, 0.08);
    }}
    .hidden-select {{
      position: absolute;
      width: 1px;
      height: 1px;
      opacity: 0;
      pointer-events: none;
    }}
    .loading-scan {{
      width: min(100%, 440px);
      display: grid;
      gap: 14px;
    }}
    .loading-bar {{
      height: 18px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.1);
    }}
    .loading-bar::before {{
      content: '';
      display: block;
      width: 38%;
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--accent-alt), var(--accent-warm));
      animation: loading-scan 1.15s ease-in-out infinite;
    }}
    .loading-copy {{
      color: rgba(255, 246, 230, 0.76);
      text-align: center;
      line-height: 1.7;
    }}
    @keyframes loading-scan {{
      0% {{ transform: translateX(-110%); }}
      100% {{ transform: translateX(320%); }}
    }}
    @media (max-width: 960px) {{
      main {{ padding: 20px 16px 28px; }}
      .hero-shell {{ padding: 20px; }}
      .hero {{
        grid-template-columns: 1fr;
        align-items: flex-start;
      }}
      .generate-layout,
      .settings-header-grid,
      .settings-grid,
      .info-strip,
      .workflow-grid,
      .provider-grid,
      .preset-grid,
      .hero-stat-grid {{
        grid-template-columns: 1fr;
      }}
      .nav-bar {{
        width: 100%;
      }}
      .nav-button {{
        flex: 1 1 0;
      }}
      .preview {{
        min-height: 460px;
      }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      *,
      *::before,
      *::after {{
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
      }}
      .pixel-orb,
      button:hover,
      .provider-card:hover,
      .nav-button:hover,
      .info-card:hover,
      .workflow-card:hover {{
        transform: none !important;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero-shell">
      <div class="hero">
        <div class="hero-copy">
          <span class="eyebrow">Pixel Control Deck</span>
          <h1>把自然语言压成可导出的像素动画素材。</h1>
          <p>
            这个工作台围绕“写 Prompt、选 Provider、立刻预览、直接导出”四步展开，
            用更强的分区和状态反馈减少切换成本，让它看起来像一个真正的创作工具，而不是普通表单页。
          </p>
          <div class="pill-row">
            <span class="pill">Transparent APNG</span>
            <span class="pill">Pixel Preview</span>
            <span class="pill">Provider Routing</span>
            <span class="pill">Local Settings</span>
          </div>
        </div>
        <aside class="hero-aside">
          <div class="nav-bar" aria-label="主导航">
            <button
              id="nav-generate"
              class="nav-button active"
              data-view-target="generate-view"
            >生成器</button>
            <button
              id="nav-settings"
              class="nav-button"
              data-view-target="settings-view"
            >设置</button>
          </div>
          <div class="hero-stat-grid">
            <div class="hero-stat">
              <strong>128×128</strong>
              <span>默认内部画布，适合稳定控制像素密度和缩放表现。</span>
            </div>
            <div class="hero-stat">
              <strong>12 FPS</strong>
              <span>默认动画节奏，用于轻量 APNG 预览和素材导出。</span>
            </div>
          </div>
        </aside>
      </div>
    </section>

    <div id="status" class="status">等待输入。</div>

    <section id="generate-view" class="view generate-layout active">
      <section class="panel">
        <span class="panel-badge">Scene Composer</span>
        <h2 class="section-title">生成</h2>
        <p class="section-copy">先确定解析 Provider，再编排场景描述。左侧专注输入，右侧专注结果，不把配置和创作混在一起。</p>

        <label for="provider">Provider</label>
        <div class="provider-grid" aria-label="Provider 选择">
          <button type="button" class="provider-card active" data-provider="openai">
            <strong>OpenAI</strong>
            <span>默认解析路径，适合更复杂的结构化提示理解。</span>
          </button>
          <button type="button" class="provider-card" data-provider="claude">
            <strong>Claude</strong>
            <span>保留第二条解析通道，适合切换模型做对照。</span>
          </button>
          <button type="button" class="provider-card" data-provider="local">
            <strong>Local</strong>
            <span>离线测试模式，不依赖远程 API，适合快速试排版。</span>
          </button>
        </div>
        <select id="provider" class="hidden-select" aria-hidden="true" tabindex="-1">
          <option value="openai">openai</option>
          <option value="claude">claude</option>
          <option value="local">local</option>
        </select>

        <label for="prompt">动画描述</label>
        <div class="prompt-shell">
          <textarea id="prompt">{DEFAULT_PROMPT}</textarea>
          <div class="helper">直接描述布局、主体、动作和色调，例如“上方是一台旋转的机器人，下方是进度条，色调为绿色”。</div>
        </div>

        <div class="preset-grid">
          <button
            type="button"
            class="preset-button secondary"
            data-prompt="上方是一只奔跑的小猫，下方是进度条，色调为绿色"
          >
            <strong>角色 + 进度条</strong>
            <span>最适合验证角色运动、底部状态条和单色调控制。</span>
          </button>
          <button
            type="button"
            class="preset-button secondary"
            data-prompt="左侧是一朵云，右侧是一颗星星，中间是文字，色调为紫色"
          >
            <strong>布局测试</strong>
            <span>快速检查多区域构图、元素分离和中心文字表现。</span>
          </button>
          <button
            type="button"
            class="preset-button secondary"
            data-prompt="中间是一台闪烁的机器人，周围有像素粒子，色调为蓝色"
          >
            <strong>主体强化</strong>
            <span>验证单主体聚焦、节奏动作和偏冷色调氛围。</span>
          </button>
          <button
            type="button"
            class="preset-button secondary"
            data-prompt="上方是一艘缓慢漂浮的飞船，下方是逐步填充的能量槽，色调为黄色"
          >
            <strong>材质感测试</strong>
            <span>适合观察机械体块、填充动画和暖色能量面板。</span>
          </button>
        </div>

        <div class="actions">
          <button id="generate">生成 APNG</button>
          <button id="save" class="secondary" disabled>保存文件</button>
        </div>

        <div class="subtle-divider"></div>

        <div class="workflow-grid">
          <div class="workflow-card">
            <strong>1. Parse</strong>
            <span>把自然语言拆成布局、主体、动作和色调约束。</span>
          </div>
          <div class="workflow-card">
            <strong>2. Compose</strong>
            <span>将 prompt 条目映射为可绘制的程序化像素蓝图。</span>
          </div>
          <div class="workflow-card">
            <strong>3. Render</strong>
            <span>在本地逐帧渲染，保留透明背景与像素边缘。</span>
          </div>
          <div class="workflow-card">
            <strong>4. Export</strong>
            <span>输出透明 APNG，直接进入剪辑或素材库流程。</span>
          </div>
        </div>
      </section>

      <section class="panel">
        <span class="panel-badge">Preview Stage</span>
        <h2 class="section-title">预览</h2>
        <p class="section-copy">这里展示当前生成结果。成功生成后，右侧会始终保持最新的 APNG 预览和导出状态。</p>
        <div class="preview" id="preview">
          <div class="preview-stage">
            <div class="preview-empty">
              <div class="pixel-orb" aria-hidden="true"></div>
              <strong>等待第一张像素动画</strong>
              <p>输入描述后点击“生成 APNG”。预览区域会保留高对比舞台，让透明边缘和细小动作更容易观察。</p>
            </div>
            <div class="preview-meta">
              <span>Alpha Background</span>
              <span>Pixelated Rendering</span>
              <span>Export Ready</span>
            </div>
          </div>
        </div>
      </section>
    </section>

    <section id="settings-view" class="view settings-layout">
      <section class="panel">
        <span class="panel-badge">Provider Settings</span>
        <h2 class="section-title">API 配置</h2>
        <p class="section-copy">把密钥和可选 Base URL 放到独立视图，保持生成区干净。这里做的是连接管理，不干扰创作流程。</p>

        <div class="settings-header-grid">
          <div class="settings-box">
            <strong>为什么拆成单独页面</strong>
            <span>
              生成区是高频动作，设置区是低频维护。把两者拆开后，
              你在连续调 Prompt 时不会被密钥输入框和网络配置打断。
            </span>
          </div>
          <div class="settings-note">
            <strong>配置策略</strong>
            <p>页面填写的 Key 会优先使用；如果留空，程序仍会回退到当前 shell 的环境变量。这样既能图形化操作，也不破坏现有 CLI 工作流。</p>
          </div>
        </div>

        <div class="settings-grid">
          <div class="settings-box">
            <label for="openai-api-key">OpenAI API Key</label>
            <input id="openai-api-key" type="password" placeholder="sk-...">

            <label for="openai-base-url">OpenAI Base URL</label>
            <input id="openai-base-url" type="text" placeholder="https://api.openai.com/v1">
          </div>

          <div class="settings-box">
            <label for="anthropic-api-key">Anthropic API Key</label>
            <input id="anthropic-api-key" type="password" placeholder="sk-ant-...">

            <label for="anthropic-base-url">Anthropic Base URL</label>
            <input id="anthropic-base-url" type="text" placeholder="https://api.anthropic.com">
          </div>
        </div>

        <div class="footer-actions">
          <button id="save-settings">保存设置</button>
          <button id="export-settings" class="secondary">导出配置</button>
        </div>

        <div class="info-strip">
          <div class="info-card">
            <strong>本地存储</strong>
            <span>
              设置会持久化到 `~/.pixel-material-generator/settings.db`，便于下次直接使用。
            </span>
          </div>
          <div class="info-card">
            <strong>环境变量兜底</strong>
            <span>如果页面里没填 Key，程序仍会回退读取当前 shell 的环境变量。</span>
          </div>
          <div class="info-card">
            <strong>导出配置</strong>
            <span>可把当前设置导出为 JSON，便于迁移到另一台机器或保留备份。</span>
          </div>
        </div>
      </section>
    </section>
  </main>
  <script>
    const navButtons = Array.from(document.querySelectorAll('[data-view-target]'));
    const views = Array.from(document.querySelectorAll('.view'));
    const promptInput = document.getElementById('prompt');
    const providerInput = document.getElementById('provider');
    const generateButton = document.getElementById('generate');
    const saveButton = document.getElementById('save');
    const saveSettingsButton = document.getElementById('save-settings');
    const exportSettingsButton = document.getElementById('export-settings');
    const statusNode = document.getElementById('status');
    const previewNode = document.getElementById('preview');
    const providerCards = Array.from(document.querySelectorAll('[data-provider]'));
    const presetButtons = Array.from(document.querySelectorAll('[data-prompt]'));
    const openaiApiKeyInput = document.getElementById('openai-api-key');
    const openaiBaseUrlInput = document.getElementById('openai-base-url');
    const anthropicApiKeyInput = document.getElementById('anthropic-api-key');
    const anthropicBaseUrlInput = document.getElementById('anthropic-base-url');
    let currentDataUrl = '';
    let currentFilename = 'pixel-animation.apng';

    function switchView(viewId) {{
      views.forEach((viewNode) => {{
        viewNode.classList.toggle('active', viewNode.id === viewId);
      }});
      navButtons.forEach((buttonNode) => {{
        buttonNode.classList.toggle(
          'active',
          buttonNode.dataset.viewTarget === viewId,
        );
      }});
    }}

    function syncProviderCards(selectedProvider) {{
      providerCards.forEach((cardNode) => {{
        cardNode.classList.toggle('active', cardNode.dataset.provider === selectedProvider);
      }});
      providerInput.value = selectedProvider;
    }}

    function sanitizeFilename(rawTitle) {{
      const normalized = String(rawTitle || 'pixel-animation')
        .trim()
        .replace(/\\s+/g, '-')
        .replace(/[^\\w\\u4e00-\\u9fff-]+/g, '-')
        .replace(/-+/g, '-')
        .replace(/^-|-$/g, '');
      return `${{normalized || 'pixel-animation'}}.apng`;
    }}

    function setStatus(message, className = '') {{
      statusNode.textContent = message;
      statusNode.className = `status ${{className}}`;
    }}

    function renderLoadingState() {{
      previewNode.innerHTML = `
        <div class="preview-stage">
          <div class="loading-scan" aria-hidden="true">
            <div class="loading-bar"></div>
          </div>
          <p class="loading-copy">正在解析场景、渲染帧序列并编码 APNG，请稍等。</p>
          <div class="preview-meta">
            <span>Parsing Prompt</span>
            <span>Rendering Frames</span>
            <span>Encoding APNG</span>
          </div>
        </div>
      `;
    }}

    function renderEmptyState(message) {{
      previewNode.innerHTML = `
        <div class="preview-stage">
          <div class="preview-empty">
            <div class="pixel-orb" aria-hidden="true"></div>
            <strong>${{message}}</strong>
            <p>重新调整 Prompt、切换 Provider，或者直接点一个预设模板继续测试。</p>
          </div>
          <div class="preview-meta">
            <span>Transparent Canvas</span>
            <span>Prompt Driven</span>
            <span>Retry Ready</span>
          </div>
        </div>
      `;
    }}

    function renderPreviewState(dataUrl, title) {{
      previewNode.innerHTML = `
        <div class="preview-stage">
          <div class="preview-frame">
            <img src="${{dataUrl}}" alt="${{title}} 的像素 APNG 预览">
          </div>
          <div class="preview-meta">
            <span>${{title}}</span>
            <span>Ready to Save</span>
            <span>Pixel Perfect</span>
          </div>
        </div>
      `;
    }}

    async function loadSettings() {{
      const settings = await pywebview.api.get_settings();
      openaiApiKeyInput.value = settings.openai_api_key || '';
      openaiBaseUrlInput.value = settings.openai_base_url || '';
      anthropicApiKeyInput.value = settings.anthropic_api_key || '';
      anthropicBaseUrlInput.value = settings.anthropic_base_url || '';
    }}

    navButtons.forEach((buttonNode) => {{
      buttonNode.addEventListener('click', () => {{
        switchView(buttonNode.dataset.viewTarget);
      }});
    }});

    providerCards.forEach((cardNode) => {{
      cardNode.addEventListener('click', () => {{
        syncProviderCards(cardNode.dataset.provider);
      }});
    }});

    providerInput.addEventListener('change', () => {{
      syncProviderCards(providerInput.value);
    }});

    presetButtons.forEach((buttonNode) => {{
      buttonNode.addEventListener('click', () => {{
        promptInput.value = buttonNode.dataset.prompt;
        switchView('generate-view');
        setStatus('已载入预设 Prompt，可以直接生成。');
      }});
    }});

    saveSettingsButton.addEventListener('click', async () => {{
      const result = await pywebview.api.save_settings({{
        openai_api_key: openaiApiKeyInput.value,
        openai_base_url: openaiBaseUrlInput.value,
        anthropic_api_key: anthropicApiKeyInput.value,
        anthropic_base_url: anthropicBaseUrlInput.value,
      }});
      switchView('settings-view');
      setStatus(result.ok ? '设置已保存。' : result.error, result.ok ? 'success' : 'error');
    }});

    exportSettingsButton.addEventListener('click', async () => {{
      const result = await pywebview.api.export_settings();
      const blob = new Blob([result.content], {{ type: 'application/json' }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'pixel-material-generator-settings.json';
      link.click();
      URL.revokeObjectURL(url);
      switchView('settings-view');
      setStatus('已导出配置文件。', 'success');
    }});

    generateButton.addEventListener('click', async () => {{
      switchView('generate-view');
      generateButton.disabled = true;
      saveButton.disabled = true;
      setStatus('正在生成...');
      renderLoadingState();
      const result = await pywebview.api.generate(promptInput.value, providerInput.value);
      generateButton.disabled = false;
      if (!result.ok) {{
        currentDataUrl = '';
        currentFilename = 'pixel-animation.apng';
        setStatus(result.error, 'error');
        renderEmptyState('生成失败');
        return;
      }}
      currentDataUrl = result.dataUrl;
      currentFilename = sanitizeFilename(result.title);
      renderPreviewState(currentDataUrl, result.title || 'pixel-animation');
      saveButton.disabled = false;
      setStatus('生成完成，可以保存为 .apng。', 'success');
    }});

    saveButton.addEventListener('click', async () => {{
      const result = await pywebview.api.save(currentDataUrl, currentFilename);
      const className = result.ok ? 'success' : 'error';
      const message = result.ok ? `已保存：${{result.path}}` : result.error;
      setStatus(message, className);
    }});

    syncProviderCards(providerInput.value);
    loadSettings();
  </script>
</body>
</html>
"""


def main() -> None:
    """Open the native desktop GUI."""
    webview.create_window(
        title=WINDOW_TITLE,
        html=build_html(),
        js_api=PixelApngGuiApi(),
        width=1280,
        height=920,
        min_size=(980, 720),
        resizable=True,
        text_select=True,
        easy_drag=False,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
