"""Tests for the local prompt parser."""

from pixel_apng.local_parser import LocalPromptParser
from pixel_apng.models import MotionName, PaletteName, RegionName, SubjectName


def test_local_parser_builds_scene_spec() -> None:
    parser = LocalPromptParser()
    scene = parser.parse("上方是一只奔跑的小猫，下方是进度条，色调为绿色")

    assert scene.palette.name == PaletteName.GREEN
    assert scene.canvas.width == 128
    assert scene.canvas.height == 128
    assert scene.regions[0].name == RegionName.TOP
    assert scene.regions[0].subject == SubjectName.CAT
    assert scene.regions[0].motion == MotionName.RUN
    assert scene.regions[1].name == RegionName.BOTTOM
    assert scene.regions[1].subject == SubjectName.PROGRESS_BAR
    assert scene.regions[1].motion == MotionName.FILL


def test_local_parser_understands_multiple_layouts() -> None:
    parser = LocalPromptParser()
    scene = parser.parse("左侧是一朵云，右侧是星星，中间是文字，色调为紫色")

    assert scene.palette.name == PaletteName.PURPLE
    assert {region.name for region in scene.regions} == {
        RegionName.LEFT,
        RegionName.RIGHT,
        RegionName.CENTER,
    }
    assert any(region.subject == SubjectName.CLOUD for region in scene.regions)
    assert any(region.subject == SubjectName.STAR for region in scene.regions)
    assert any(region.subject == SubjectName.TEXT for region in scene.regions)
