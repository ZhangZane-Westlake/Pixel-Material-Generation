"""Tests for APNG rendering and export."""

from pathlib import Path

from PIL import Image

from pixel_apng.exporter import PixelExporter
from pixel_apng.local_parser import LocalPromptParser
from pixel_apng.renderer import PixelRenderer


def test_renderer_and_exporter_create_apng(tmp_path: Path) -> None:
    scene = LocalPromptParser().parse("上方是一台旋转的机器人，下方是进度条，色调为绿色")
    frames = PixelRenderer().render_frames(scene)
    output_path = tmp_path / "robot_progress.apng"

    PixelExporter().save_apng(frames, output_path, scene.animation.fps)

    assert output_path.exists()
    with output_path.open("rb") as file_handle:
        assert file_handle.read(8) == b"\x89PNG\r\n\x1a\n"

    with Image.open(output_path) as image:
        assert image.n_frames > 1
        expected_size = (
            scene.canvas.width * scene.canvas.scale,
            scene.canvas.height * scene.canvas.scale,
        )
        assert image.size == expected_size
        assert image.mode == "RGBA"


def test_renderer_supports_arbitrary_prompt_objects() -> None:
    scene = LocalPromptParser().parse("中间是一朵会弹跳的蘑菇，色调为黄色")
    frames = PixelRenderer().render_frames(scene)

    assert len(frames) > 1
    first_frame = frames[0]
    assert first_frame.getchannel("A").getbbox() is not None
