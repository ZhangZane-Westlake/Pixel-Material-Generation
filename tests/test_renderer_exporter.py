"""Tests for APNG rendering and export."""

from pathlib import Path

from PIL import Image

from pixel_apng.composition_models import (
    BackgroundDecorationMode,
    BackgroundPolicy,
    LayoutAnchor,
    RenderBox,
    RenderElementPlan,
    RenderPlan,
    TrailPolicy,
    TrailRenderMode,
)
from pixel_apng.exporter import PixelExporter
from pixel_apng.local_parser import LocalPromptParser
from pixel_apng.models import MotionName, PaletteName, RegionName, SubjectName
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


def test_renderer_uses_render_plan_boxes_for_object_and_progress_bar() -> None:
    render_plan = RenderPlan(
        palette_name=PaletteName.GREEN,
        canvas_width=128,
        canvas_height=128,
        output_scale=4,
        background_policy=BackgroundPolicy(
            decoration_mode=BackgroundDecorationMode.MINIMAL
        ),
        elements=[
            RenderElementPlan(
                element_id="object-0",
                subject=SubjectName.OBJECT,
                content="机器人",
                motion=MotionName.NONE,
                anchor_region=RegionName.CENTER,
                layout_anchor=LayoutAnchor.CENTER,
                box=RenderBox(left=20, top=10, right=104, bottom=70),
                importance_score=1.0,
                trail_policy=TrailPolicy(mode=TrailRenderMode.DISABLED),
            ),
            RenderElementPlan(
                element_id="progress-0",
                subject=SubjectName.PROGRESS_BAR,
                content="progress bar",
                motion=MotionName.FILL,
                anchor_region=RegionName.BOTTOM,
                layout_anchor=LayoutAnchor.BOTTOM,
                box=RenderBox(left=24, top=90, right=104, bottom=106),
                importance_score=0.35,
                trail_policy=TrailPolicy(mode=TrailRenderMode.DISABLED),
            ),
        ],
    )

    frames = PixelRenderer().render_plan_frames(render_plan, fps=12, duration_seconds=2.0)

    assert len(frames) == 24
    alpha_box = frames[0].getchannel("A").getbbox()
    assert alpha_box is not None
    assert alpha_box[1] <= 40
    assert alpha_box[3] >= 420


def test_renderer_skips_scanlines_when_background_policy_is_minimal() -> None:
    render_plan = RenderPlan(
        palette_name=PaletteName.RETRO,
        canvas_width=128,
        canvas_height=128,
        output_scale=4,
        background_policy=BackgroundPolicy(
            decoration_mode=BackgroundDecorationMode.MINIMAL
        ),
        elements=[],
    )

    frame = PixelRenderer().render_plan_frames(
        render_plan,
        fps=1,
        duration_seconds=1.0,
    )[0]

    alpha_box = frame.getchannel("A").getbbox()
    assert alpha_box is None


def test_renderer_respects_disabled_trail_policy() -> None:
    render_plan = RenderPlan(
        palette_name=PaletteName.GREEN,
        canvas_width=128,
        canvas_height=128,
        output_scale=4,
        background_policy=BackgroundPolicy(
            decoration_mode=BackgroundDecorationMode.MINIMAL
        ),
        elements=[
            RenderElementPlan(
                element_id="runner-0",
                subject=SubjectName.OBJECT,
                content="小猫",
                motion=MotionName.RUN,
                anchor_region=RegionName.LEFT,
                layout_anchor=LayoutAnchor.LOWER_LEFT,
                box=RenderBox(left=12, top=24, right=54, bottom=84),
                importance_score=0.9,
                trail_policy=TrailPolicy(mode=TrailRenderMode.DISABLED),
            )
        ],
    )

    frame = PixelRenderer().render_plan_frames(render_plan, fps=1, duration_seconds=1.0)[0]

    assert frame.getchannel("A").getbbox() is not None


def test_readme_mentions_composition_planner_pipeline() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Composition planner" in readme
    assert "RenderPlan" in readme
    assert "LLM only parses the prompt" in readme
