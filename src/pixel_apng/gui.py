"""GUI application for generating pixel APNG animations."""

from __future__ import annotations

import base64
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import webview

from pixel_apng.cli import ProviderError, build_parser
from pixel_apng.exporter import PixelExporter
from pixel_apng.renderer import PixelRenderer

WINDOW_TITLE: Final[str] = "Pixel Material Generator"
DEFAULT_PROMPT: Final[str] = "上方是一只奔跑的小猫，下方是进度条，色调为绿色"


class PixelApngGuiApi:
    """Bridge between the native WebView and the APNG generator."""

    def __init__(self) -> None:
        """Initialize renderer and exporter dependencies."""
        self._renderer = PixelRenderer()
        self._exporter = PixelExporter()

    def generate(self, prompt: str, provider: str) -> dict[str, str | bool]:
        """Generate an APNG and return a data URL for preview/download.

        Args:
            prompt: Natural-language animation prompt.
            provider: Parser provider name.

        Returns:
            JSON-serializable generation result.
        """
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            return {"ok": False, "error": "请输入动画描述。"}

        try:
            parser = build_parser(provider)
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
        """Save a generated APNG through a native file dialog.

        Args:
            data_url: Base64 data URL returned by generate.
            filename: Suggested file name.

        Returns:
            JSON-serializable save result.
        """
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
      color-scheme: light dark;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }}
    body {{ margin: 0; background: #10131a; color: #f4f7fb; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 32px; }}
    h1 {{ margin: 0 0 8px; font-size: 32px; }}
    p {{ color: #a9b2c3; line-height: 1.6; }}
    .panel {{
      background: #171c26;
      border: 1px solid #283142;
      border-radius: 18px;
      padding: 24px;
      box-shadow: 0 20px 60px #0006;
    }}
    label {{ display: block; margin: 16px 0 8px; font-weight: 700; }}
    textarea, select {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #364258;
      border-radius: 12px;
      background: #0f131b;
      color: #f4f7fb;
      padding: 12px 14px;
      font-size: 15px;
    }}
    textarea {{ min-height: 120px; resize: vertical; }}
    .row {{
      display: grid;
      grid-template-columns: 1fr 180px;
      gap: 16px;
      align-items: end;
    }}
    button {{
      border: 0;
      border-radius: 12px;
      padding: 13px 18px;
      font-size: 15px;
      font-weight: 700;
      color: white;
      background: linear-gradient(135deg, #43c77b, #2d8cff);
      cursor: pointer;
    }}
    button:disabled {{ opacity: .55; cursor: not-allowed; }}
    .actions {{ display: flex; gap: 12px; margin-top: 18px; }}
    .preview {{
      display: grid;
      place-items: center;
      min-height: 360px;
      margin-top: 22px;
      border: 1px dashed #3a465d;
      border-radius: 16px;
      background: #0d1118;
    }}
    .preview img {{ max-width: min(512px, 90%); image-rendering: pixelated; }}
    .status {{ min-height: 24px; margin-top: 14px; color: #b9c2d4; }}
    .error {{ color: #ff9b9b; }}
    .success {{ color: #8df0af; }}
  </style>
</head>
<body>
  <main>
    <h1>Pixel Material Generator</h1>
    <p>输入自然语言描述，生成透明像素风 APNG 动画。默认使用 OpenAI；离线测试请选择 local。</p>
    <section class="panel">
      <div class="row">
        <div>
          <label for="provider">解析 Provider</label>
          <select id="provider">
            <option value="openai">openai</option>
            <option value="claude">claude</option>
            <option value="local">local</option>
          </select>
        </div>
        <button id="generate">生成 APNG</button>
      </div>
      <label for="prompt">动画描述</label>
      <textarea id="prompt">{DEFAULT_PROMPT}</textarea>
      <div class="actions">
        <button id="save" disabled>保存为 .apng</button>
      </div>
      <div id="status" class="status"></div>
      <div class="preview" id="preview"><p>生成后会在这里预览。</p></div>
    </section>
  </main>
  <script>
    const promptInput = document.getElementById('prompt');
    const providerInput = document.getElementById('provider');
    const generateButton = document.getElementById('generate');
    const saveButton = document.getElementById('save');
    const statusNode = document.getElementById('status');
    const previewNode = document.getElementById('preview');
    let currentDataUrl = '';

    function setStatus(message, className = '') {{
      statusNode.textContent = message;
      statusNode.className = `status ${{className}}`;
    }}

    generateButton.addEventListener('click', async () => {{
      generateButton.disabled = true;
      saveButton.disabled = true;
      setStatus('正在生成...');
      previewNode.innerHTML = '<p>正在生成 APNG...</p>';
      const result = await pywebview.api.generate(promptInput.value, providerInput.value);
      generateButton.disabled = false;
      if (!result.ok) {{
        currentDataUrl = '';
        setStatus(result.error, 'error');
        previewNode.innerHTML = '<p>生成失败。</p>';
        return;
      }}
      currentDataUrl = result.dataUrl;
      previewNode.innerHTML = `<img src="${{currentDataUrl}}" alt="generated pixel APNG">`;
      saveButton.disabled = false;
      setStatus('生成完成，可以保存为 .apng。', 'success');
    }});

    saveButton.addEventListener('click', async () => {{
      const result = await pywebview.api.save(currentDataUrl, 'pixel-animation.apng');
      const className = result.ok ? 'success' : 'error';
      const message = result.ok ? `已保存：${{result.path}}` : result.error;
      setStatus(message, className);
    }});
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
        width=1080,
        height=820,
        min_size=(860, 640),
        resizable=True,
        text_select=True,
        easy_drag=False,
    )
    webview.start()


if __name__ == "__main__":
    main()
