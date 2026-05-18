"""Tests for the composition planner."""

from pixel_apng.composition_models import BackgroundDecorationMode, TrailRenderMode
from pixel_apng.composition_planner import CompositionPlanner
from pixel_apng.local_parser import LocalPromptParser
from pixel_apng.models import RegionName, SubjectName


def test_planner_promotes_primary_object_over_progress_bar() -> None:
    parser = LocalPromptParser()
    scene = parser.parse("上方是一只奔跑的小猫，下方是进度条，色调为绿色")

    plan = CompositionPlanner().build_plan(scene)

    object_element = next(
        element for element in plan.elements if element.subject == SubjectName.OBJECT
    )
    progress_element = next(
        element for element in plan.elements if element.subject == SubjectName.PROGRESS_BAR
    )

    assert object_element.importance_score > progress_element.importance_score
    assert object_element.box.height > progress_element.box.height


def test_planner_softens_left_and_right_regions_without_losing_order() -> None:
    parser = LocalPromptParser()
    scene = parser.parse("左侧是一台旋转的机器人，右侧是一朵蘑菇，色调为蓝色")

    plan = CompositionPlanner().build_plan(scene)

    left_element = next(element for element in plan.elements if "机器人" in element.content)
    right_element = next(element for element in plan.elements if "蘑菇" in element.content)

    assert left_element.anchor_region == RegionName.LEFT
    assert right_element.anchor_region == RegionName.RIGHT
    assert left_element.box.center_x < right_element.box.center_x
    assert left_element.box.right > 54
    assert right_element.box.left < 74


def test_planner_disables_retro_lines_for_sparse_scene() -> None:
    parser = LocalPromptParser()
    scene = parser.parse("中间是一颗星星，色调为复古")

    plan = CompositionPlanner().build_plan(scene)

    assert plan.background_policy.decoration_mode == BackgroundDecorationMode.MINIMAL


def test_planner_disables_run_trail_when_subject_is_too_small() -> None:
    parser = LocalPromptParser()
    scene = parser.parse("左侧是一只奔跑的小猫，右侧是文字，色调为绿色")

    plan = CompositionPlanner().build_plan(scene)

    cat_element = next(element for element in plan.elements if "小猫" in element.content)

    assert cat_element.trail_policy.mode in {
        TrailRenderMode.DISABLED,
        TrailRenderMode.SHORT,
    }
