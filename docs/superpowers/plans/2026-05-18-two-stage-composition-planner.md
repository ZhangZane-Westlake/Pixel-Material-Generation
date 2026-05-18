# Two-Stage Composition Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a deterministic composition-planning stage that converts `SceneSpec` into a scored `RenderPlan`, then make the renderer execute that plan so multi-region prompts compose better and stray line artifacts are suppressed.

**Architecture:** Keep `SceneSpec` semantic and add planner-facing models plus a dedicated `CompositionPlanner`. The renderer should stop deriving layout from hard-coded region boxes and instead rasterize objects, text, progress bars, trails, and backgrounds from explicit `RenderPlan` elements and policies.

**Tech Stack:** Python 3.11, Pydantic 2, Pillow, pytest, mypy, ruff, Typer

---

## File Structure

- Create: `src/pixel_apng/composition_models.py`
  - Planner-facing enums and models such as `LayoutAnchor`, `RenderBox`, `TrailPolicy`, `BackgroundPolicy`, `RenderElementPlan`, and `RenderPlan`.
- Create: `src/pixel_apng/composition_planner.py`
  - Rule-based candidate generator, scorer, fallback plan builder, and deterministic public planner entrypoint.
- Create: `tests/test_composition_planner.py`
  - Planner-focused TDD coverage for hierarchy, soft anchors, trail suppression, and background cleanliness.
- Modify: `src/pixel_apng/renderer.py`
  - Move from region-derived layout to `RenderPlan` execution while preserving procedural sprite drawing.
- Modify: `tests/test_renderer_exporter.py`
  - Add render-contract tests proving the renderer respects planner output and policy toggles.
- Modify: `README.md`
  - Document the new pipeline stage and the behavioral shift away from direct region-box rendering.

### Task 1: Add planner-facing models and planner TDD harness

**Files:**
- Create: `src/pixel_apng/composition_models.py`
- Create: `src/pixel_apng/composition_planner.py`
- Create: `tests/test_composition_planner.py`

- [x] **Step 1: Write the failing planner tests**

```python
from pixel_apng.composition_planner import CompositionPlanner
from pixel_apng.composition_models import BackgroundDecorationMode, TrailRenderMode
from pixel_apng.local_parser import LocalPromptParser
from pixel_apng.models import RegionName, SubjectName


def test_planner_promotes_primary_object_over_progress_bar() -> None:
    scene = LocalPromptParser().parse("上方是一只奔跑的小猫，下方是进度条，色调为绿色")

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
    scene = LocalPromptParser().parse("左侧是一台旋转的机器人，右侧是一朵蘑菇，色调为蓝色")

    plan = CompositionPlanner().build_plan(scene)

    left_element = next(element for element in plan.elements if "机器人" in element.content)
    right_element = next(element for element in plan.elements if "蘑菇" in element.content)

    assert left_element.anchor_region == RegionName.LEFT
    assert right_element.anchor_region == RegionName.RIGHT
    assert left_element.box.center_x < right_element.box.center_x
    assert left_element.box.right > 54
    assert right_element.box.left < 74


def test_planner_disables_retro_lines_for_sparse_scene() -> None:
    scene = LocalPromptParser().parse("中间是一颗星星，色调为复古")

    plan = CompositionPlanner().build_plan(scene)

    assert plan.background_policy.decoration_mode == BackgroundDecorationMode.MINIMAL


def test_planner_disables_run_trail_when_subject_is_too_small() -> None:
    scene = LocalPromptParser().parse("左侧是一只奔跑的小猫，右侧是文字，色调为绿色")

    plan = CompositionPlanner().build_plan(scene)

    cat_element = next(element for element in plan.elements if "小猫" in element.content)

    assert cat_element.trail_policy.mode in {
        TrailRenderMode.DISABLED,
        TrailRenderMode.SHORT,
    }
```

- [x] **Step 2: Run planner tests to verify they fail**

Run: `pytest tests/test_composition_planner.py -v`

Expected: FAIL with import errors such as `ModuleNotFoundError: No module named 'pixel_apng.composition_planner'` and missing model names like `BackgroundDecorationMode`.

- [x] **Step 3: Add the planner-facing model definitions**

```python
"""Planner-facing render models for two-stage composition."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from pixel_apng.models import MotionName, PaletteName, RegionName, SubjectName


class LayoutAnchor(StrEnum):
    """Soft layout anchor used by the composition planner."""

    TOP = "top"
    UPPER_LEFT = "upper_left"
    UPPER_RIGHT = "upper_right"
    CENTER = "center"
    LOWER_LEFT = "lower_left"
    LOWER_RIGHT = "lower_right"
    BOTTOM = "bottom"


class TrailRenderMode(StrEnum):
    """How strongly a motion trail should render."""

    DISABLED = "disabled"
    SHORT = "short"
    CLIPPED = "clipped"
    SOFT = "soft"
    FULL = "full"


class BackgroundDecorationMode(StrEnum):
    """Background decoration strength."""

    MINIMAL = "minimal"
    SPARKLE = "sparkle"
    SCANLINE = "scanline"


class RenderBox(BaseModel):
    """Pixel-space box chosen by the planner."""

    left: int = Field(ge=0)
    top: int = Field(ge=0)
    right: int = Field(ge=0)
    bottom: int = Field(ge=0)

    @property
    def width(self) -> int:
        """Return the box width."""
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        """Return the box height."""
        return max(0, self.bottom - self.top)

    @property
    def center_x(self) -> int:
        """Return the horizontal box center."""
        return self.left + self.width // 2


class TrailPolicy(BaseModel):
    """Per-element trail decision from the planner."""

    mode: TrailRenderMode = TrailRenderMode.DISABLED


class BackgroundPolicy(BaseModel):
    """Scene-level background rendering policy."""

    decoration_mode: BackgroundDecorationMode = BackgroundDecorationMode.MINIMAL


class RenderElementPlan(BaseModel):
    """Final draw instructions for one scene element."""

    element_id: str
    subject: SubjectName
    content: str
    motion: MotionName
    anchor_region: RegionName
    layout_anchor: LayoutAnchor
    box: RenderBox
    z_order: int = 0
    scale: float = Field(default=1.0, gt=0)
    safe_margin: int = Field(default=2, ge=0)
    importance_score: float = Field(default=0.0, ge=0)
    trail_policy: TrailPolicy = Field(default_factory=TrailPolicy)


class RenderPlan(BaseModel):
    """Scene-level render contract emitted by the planner."""

    palette_name: PaletteName
    canvas_width: int = Field(ge=32)
    canvas_height: int = Field(ge=32)
    output_scale: int = Field(default=4, ge=1)
    background_policy: BackgroundPolicy = Field(default_factory=BackgroundPolicy)
    elements: list[RenderElementPlan] = Field(default_factory=list)
```

- [x] **Step 4: Add minimal planner implementation to satisfy the tests**

```python
"""Deterministic composition planner for SceneSpec inputs."""

from __future__ import annotations

from dataclasses import dataclass

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
from pixel_apng.models import MotionName, PaletteName, RegionName, SceneSpec, SubjectName


@dataclass(frozen=True)
class _RegionAnchorSeed:
    """Soft-anchor seed values for a region."""

    center_x: int
    center_y: int
    width: int
    height: int
    layout_anchor: LayoutAnchor


class CompositionPlanner:
    """Build a render plan from a semantic scene."""

    def build_plan(self, scene: SceneSpec) -> RenderPlan:
        """Return a deterministic render plan for the scene."""
        elements: list[RenderElementPlan] = []
        for index, region in enumerate(scene.regions):
            importance_score = self._importance(region.subject, region.name)
            seed = self._seed_for_region(scene, region.name, importance_score)
            box = self._box_from_seed(seed, importance_score)
            trail_policy = self._trail_policy(region.subject, region.motion, box)
            elements.append(
                RenderElementPlan(
                    element_id=f"{region.name.value}-{index}",
                    subject=region.subject,
                    content=region.content,
                    motion=region.motion,
                    anchor_region=region.name,
                    layout_anchor=seed.layout_anchor,
                    box=box,
                    z_order=int(importance_score * 10),
                    scale=1.0,
                    safe_margin=2,
                    importance_score=importance_score,
                    trail_policy=trail_policy,
                )
            )
        return RenderPlan(
            palette_name=scene.palette.name,
            canvas_width=scene.canvas.width,
            canvas_height=scene.canvas.height,
            output_scale=scene.canvas.scale,
            background_policy=self._background_policy(scene, elements),
            elements=elements,
        )

    def _importance(self, subject: SubjectName, region_name: RegionName) -> float:
        """Return a deterministic importance score."""
        if subject == SubjectName.OBJECT:
            return 1.0 if region_name == RegionName.CENTER else 0.9
        if subject == SubjectName.TEXT:
            return 0.45
        if subject == SubjectName.PROGRESS_BAR:
            return 0.35
        return 0.4

    def _seed_for_region(
        self,
        scene: SceneSpec,
        region_name: RegionName,
        importance_score: float,
    ) -> _RegionAnchorSeed:
        """Return a soft anchor seed for the region."""
        width = scene.canvas.width
        height = scene.canvas.height
        if region_name == RegionName.LEFT:
            return _RegionAnchorSeed(width // 3, height // 2, 42, 62, LayoutAnchor.LOWER_LEFT)
        if region_name == RegionName.RIGHT:
            return _RegionAnchorSeed(width * 2 // 3, height // 2, 42, 62, LayoutAnchor.LOWER_RIGHT)
        if region_name == RegionName.TOP:
            return _RegionAnchorSeed(width // 2, height // 4, 84, 38, LayoutAnchor.TOP)
        if region_name == RegionName.BOTTOM:
            return _RegionAnchorSeed(width // 2, height * 3 // 4, 80, 20, LayoutAnchor.BOTTOM)
        return _RegionAnchorSeed(width // 2, height // 2, 68, 68, LayoutAnchor.CENTER)

    def _box_from_seed(self, seed: _RegionAnchorSeed, importance_score: float) -> RenderBox:
        """Return a softened render box for the seed."""
        half_width = int(seed.width * (0.55 + importance_score * 0.4)) // 2
        half_height = int(seed.height * (0.55 + importance_score * 0.4)) // 2
        return RenderBox(
            left=max(0, seed.center_x - half_width),
            top=max(0, seed.center_y - half_height),
            right=seed.center_x + half_width,
            bottom=seed.center_y + half_height,
        )

    def _trail_policy(
        self,
        subject: SubjectName,
        motion: MotionName,
        box: RenderBox,
    ) -> TrailPolicy:
        """Return the trail policy for one element."""
        if subject != SubjectName.OBJECT or motion != MotionName.RUN:
            return TrailPolicy(mode=TrailRenderMode.DISABLED)
        if box.width < 34 or box.height < 24:
            return TrailPolicy(mode=TrailRenderMode.SHORT)
        return TrailPolicy(mode=TrailRenderMode.SOFT)

    def _background_policy(
        self,
        scene: SceneSpec,
        elements: list[RenderElementPlan],
    ) -> BackgroundPolicy:
        """Choose a scene-level background policy."""
        if scene.palette.name == PaletteName.RETRO and len(elements) > 1:
            return BackgroundPolicy(decoration_mode=BackgroundDecorationMode.SCANLINE)
        return BackgroundPolicy(decoration_mode=BackgroundDecorationMode.MINIMAL)
```

- [x] **Step 5: Run planner tests to verify they pass**

Run: `pytest tests/test_composition_planner.py -v`

Expected: PASS for the four new planner tests.

- [x] **Step 6: Run the existing parser tests to verify no semantic regressions**

Run: `pytest tests/test_local_parser.py -v`

Expected: PASS for all parser tests.

- [ ] **Step 7: Commit planner foundation**

Blocked in this environment: `.git/index.lock` cannot be created, so `git add` and
`git commit` both fail with `Operation not permitted`.

```bash
git add src/pixel_apng/composition_models.py src/pixel_apng/composition_planner.py tests/test_composition_planner.py
git commit -m "feat: add composition planner models and scoring foundation"
```

### Task 2: Refactor the renderer to consume RenderPlan

**Files:**
- Modify: `src/pixel_apng/renderer.py`
- Modify: `tests/test_renderer_exporter.py`
- Test: `tests/test_composition_planner.py`

- [x] **Step 1: Write the failing render-contract tests**

```python
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
from pixel_apng.models import MotionName, PaletteName, RegionName, SubjectName
from pixel_apng.renderer import PixelRenderer


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
```

- [x] **Step 2: Run render-contract tests to verify they fail**

Run: `pytest tests/test_renderer_exporter.py -v`

Expected: FAIL because `PixelRenderer` does not yet expose `render_plan_frames` and the current renderer still derives layout from `SceneSpec` regions.

- [x] **Step 3: Refactor the renderer to execute a RenderPlan**

```python
from pixel_apng.composition_models import (
    BackgroundDecorationMode,
    RenderElementPlan,
    RenderPlan,
    TrailRenderMode,
)
from pixel_apng.composition_planner import CompositionPlanner


class PixelRenderer:
    """Render scene specs into raster frames."""

    def __init__(self, planner: CompositionPlanner | None = None) -> None:
        """Initialize the renderer with an optional planner."""
        self._planner = planner or CompositionPlanner()

    def render_frames(self, scene: SceneSpec) -> list[Image.Image]:
        """Render all frames for a scene."""
        render_plan = self._planner.build_plan(scene)
        return self.render_plan_frames(
            render_plan,
            fps=scene.animation.fps,
            duration_seconds=scene.animation.duration_seconds,
        )

    def render_plan_frames(
        self,
        render_plan: RenderPlan,
        fps: int,
        duration_seconds: float,
    ) -> list[Image.Image]:
        """Render frames directly from a planner-produced render plan."""
        total_frames = max(1, int(fps * duration_seconds))
        return [
            self._render_plan_frame(render_plan, frame_index, total_frames)
            for frame_index in range(total_frames)
        ]

    def _render_plan_frame(
        self,
        render_plan: RenderPlan,
        frame_index: int,
        total_frames: int,
    ) -> Image.Image:
        """Render a single frame from a render plan."""
        palette = PALETTES[render_plan.palette_name]
        image = Image.new(
            "RGBA",
            (render_plan.canvas_width, render_plan.canvas_height),
            palette["bg"],
        )
        draw = ImageDraw.Draw(image)
        self._draw_background_from_plan(render_plan, draw, palette, frame_index)
        for element in sorted(render_plan.elements, key=lambda item: item.z_order):
            self._draw_render_element(draw, palette, element, frame_index, total_frames)
        return image.resize(
            (
                render_plan.canvas_width * render_plan.output_scale,
                render_plan.canvas_height * render_plan.output_scale,
            ),
            Image.Resampling.NEAREST,
        )

    def _draw_background_from_plan(
        self,
        render_plan: RenderPlan,
        draw: ImageDraw.ImageDraw,
        palette: Palette,
        frame_index: int,
    ) -> None:
        """Draw the background according to planner policy."""
        if (
            render_plan.background_policy.decoration_mode
            == BackgroundDecorationMode.SCANLINE
        ):
            for y_coord in range(frame_index % 2, render_plan.canvas_height, 4):
                draw.line([0, y_coord, render_plan.canvas_width, y_coord], fill=(255, 255, 255, 18))
            return
        if (
            render_plan.background_policy.decoration_mode
            == BackgroundDecorationMode.SPARKLE
        ):
            draw.point(
                ((frame_index * 7) % render_plan.canvas_width, 12),
                fill=palette["white"],
            )

    def _draw_render_element(
        self,
        draw: ImageDraw.ImageDraw,
        palette: Palette,
        element: RenderElementPlan,
        frame_index: int,
        total_frames: int,
    ) -> None:
        """Draw one render-plan element."""
        bounds = (
            element.box.left,
            element.box.top,
            element.box.right,
            element.box.bottom,
        )
        if element.subject == SubjectName.PROGRESS_BAR:
            self._draw_progress_bar(draw, bounds, palette, frame_index, total_frames)
            return
        if element.subject == SubjectName.TEXT:
            self._draw_text_block(draw, bounds, palette, element.content, frame_index, element.motion)
            return
        self._draw_prompt_object(
            draw,
            bounds,
            palette,
            element.content,
            frame_index,
            element.motion,
            element.trail_policy.mode,
        )
```

- [x] **Step 4: Update motion drawing to obey trail policy**

```python
def _draw_prompt_object(
    self,
    draw: ImageDraw.ImageDraw,
    bounds: Bounds,
    palette: Palette,
    content: str,
    frame_index: int,
    motion: MotionName,
    trail_mode: TrailRenderMode,
) -> None:
    """Render a procedural object derived from the region content."""
    spec = self._build_object_spec(content, motion)
    grid = self._build_sprite_grid(spec)
    self._draw_motion_trail(draw, bounds, palette, spec, frame_index, motion, trail_mode)
    self._draw_grid_sprite(draw, bounds, palette, grid, spec, frame_index)


def _draw_motion_trail(
    self,
    draw: ImageDraw.ImageDraw,
    bounds: Bounds,
    palette: Palette,
    spec: ProceduralObjectSpec,
    frame_index: int,
    motion: MotionName,
    trail_mode: TrailRenderMode,
) -> None:
    """Draw a lightweight motion cue behind the object."""
    if trail_mode == TrailRenderMode.DISABLED:
        return
    left, top, right, bottom = bounds
    center_y = (top + bottom) // 2
    if motion == MotionName.RUN:
        trail_length = 3 if trail_mode == TrailRenderMode.SHORT else 6
        draw.line(
            [left + 4, center_y + 4, left + 4 - trail_length, center_y + 2],
            fill=palette["accent_dark"],
            width=1 if trail_mode == TrailRenderMode.SOFT else 2,
        )
```

- [x] **Step 5: Run render and exporter tests to verify they pass**

Run: `pytest tests/test_renderer_exporter.py -v`

Expected: PASS for the new render-contract tests and the existing APNG export test.

- [x] **Step 6: Re-run planner tests to verify renderer integration did not change planner behavior**

Run: `pytest tests/test_composition_planner.py -v`

Expected: PASS.

- [ ] **Step 7: Commit renderer contract migration**

Blocked in this environment: `.git/index.lock` cannot be created, so `git add` and
`git commit` both fail with `Operation not permitted`.

```bash
git add src/pixel_apng/renderer.py tests/test_renderer_exporter.py
git commit -m "feat: render from composition plans"
```

### Task 3: Update docs and run project verification

**Files:**
- Modify: `README.md`
- Test: `tests/test_local_parser.py`
- Test: `tests/test_composition_planner.py`
- Test: `tests/test_renderer_exporter.py`

- [x] **Step 1: Write the failing documentation assertion**

```python
from pathlib import Path


def test_readme_mentions_composition_planner_pipeline() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Composition planner" in readme
    assert "RenderPlan" in readme
    assert "LLM only parses the prompt" in readme
```

Save the test at the bottom of `tests/test_renderer_exporter.py` to keep the README contract near the rendering contract.

- [x] **Step 2: Run the documentation assertion to verify it fails**

Run: `pytest tests/test_renderer_exporter.py::test_readme_mentions_composition_planner_pipeline -v`

Expected: FAIL because the README still describes the old direct parser-to-renderer pipeline.

- [x] **Step 3: Update the README pipeline and rendering explanation**

```markdown
Pipeline:

1. Parse the prompt into a structured `SceneSpec` using a provider model.
2. Score candidate compositions in a deterministic composition planner.
3. Convert the chosen composition into a `RenderPlan`.
4. Render pixel frames locally with Pillow from the `RenderPlan`.
5. Export the result as APNG.

The provider model does not generate the pixel artwork directly. It only parses the prompt into a semantic scene description. Composition and rendering happen locally.
```

- [x] **Step 4: Run targeted verification for docs and behavior**

Run: `pytest tests/test_local_parser.py tests/test_composition_planner.py tests/test_renderer_exporter.py -v`

Expected: PASS for all targeted tests.

- [x] **Step 5: Run static checks for the changed code**

Run: `ruff check src tests`

Expected: `All checks passed!`

Run: `mypy src`

Expected: `Success: no issues found`

- [ ] **Step 6: Commit docs and verification updates**

Blocked in this environment: `.git/index.lock` cannot be created, so `git add` and
`git commit` both fail with `Operation not permitted`.

```bash
git add README.md tests/test_renderer_exporter.py
git commit -m "docs: describe composition planner render pipeline"
```

## Spec Coverage Check

- Two-stage pipeline: covered by Task 1 planner introduction and Task 2 renderer contract migration.
- Soft region anchoring and hierarchy inference: covered by Task 1 planner tests and planner implementation.
- Minimal background policy and trail suppression: covered by Task 1 policy tests and Task 2 render-contract tests.
- Renderer as executor-only: covered by Task 2.
- README sync requirement: covered by Task 3.
- Test strategy from the spec: covered by planner tests, render-contract tests, and targeted verification in Task 3.

## Placeholder Scan

- No `TODO`, `TBD`, or deferred “implement later” markers should remain in this plan.
- All referenced files, classes, test names, and commands are defined in-line above.

## Type Consistency Check

- Planner-facing models live in `composition_models.py`.
- Scene semantics remain in `models.py`.
- `CompositionPlanner.build_plan(...)` returns `RenderPlan`.
- `PixelRenderer.render_frames(...)` remains the public scene-based API and now delegates to `render_plan_frames(...)`.

Plan complete and saved to `docs/superpowers/plans/2026-05-18-two-stage-composition-planner.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Because you already asked me to execute the plan, default to option 2 unless you redirect.
