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
from pixel_apng.models import (
    MotionName,
    PaletteName,
    RegionName,
    RegionSpec,
    SceneSpec,
    SubjectName,
)


@dataclass(frozen=True)
class _RegionAnchorSeed:
    """Soft anchor seed values for a semantic region."""

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
            importance_score = self._importance(region)
            seed = self._seed_for_region(scene, region, importance_score)
            box = self._box_from_seed(scene, seed, importance_score)
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

    def _importance(self, region: RegionSpec) -> float:
        """Return a deterministic importance score for one semantic region."""
        if region.subject == SubjectName.OBJECT:
            return 1.0 if region.name == RegionName.CENTER else 0.9
        if region.subject == SubjectName.TEXT:
            return 0.45
        if region.subject == SubjectName.PROGRESS_BAR:
            return 0.35
        return 0.4

    def _seed_for_region(
        self,
        scene: SceneSpec,
        region: RegionSpec,
        importance_score: float,
    ) -> _RegionAnchorSeed:
        """Return a softened anchor seed for the region."""
        del importance_score
        width = scene.canvas.width
        height = scene.canvas.height

        if region.name == RegionName.LEFT:
            return _RegionAnchorSeed(
                center_x=width // 3,
                center_y=height // 2,
                width=58,
                height=72,
                layout_anchor=LayoutAnchor.LOWER_LEFT,
            )
        if region.name == RegionName.RIGHT:
            return _RegionAnchorSeed(
                center_x=width * 2 // 3,
                center_y=height // 2,
                width=58,
                height=72,
                layout_anchor=LayoutAnchor.LOWER_RIGHT,
            )
        if region.name == RegionName.TOP:
            return _RegionAnchorSeed(
                center_x=width // 2,
                center_y=height // 4,
                width=86,
                height=46,
                layout_anchor=LayoutAnchor.TOP,
            )
        if region.name == RegionName.BOTTOM:
            return _RegionAnchorSeed(
                center_x=width // 2,
                center_y=height * 3 // 4,
                width=84,
                height=18,
                layout_anchor=LayoutAnchor.BOTTOM,
            )
        return _RegionAnchorSeed(
            center_x=width // 2,
            center_y=height // 2,
            width=72,
            height=72,
            layout_anchor=LayoutAnchor.CENTER,
        )

    def _box_from_seed(
        self,
        scene: SceneSpec,
        seed: _RegionAnchorSeed,
        importance_score: float,
    ) -> RenderBox:
        """Return a render box derived from the seed and importance."""
        emphasis_multiplier = 0.7 + importance_score * 0.3
        half_width = max(6, int(seed.width * emphasis_multiplier) // 2)
        half_height = max(6, int(seed.height * emphasis_multiplier) // 2)
        return RenderBox(
            left=max(0, seed.center_x - half_width),
            top=max(0, seed.center_y - half_height),
            right=min(scene.canvas.width, seed.center_x + half_width),
            bottom=min(scene.canvas.height, seed.center_y + half_height),
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
        if box.width <= 56 or box.height <= 68:
            return TrailPolicy(mode=TrailRenderMode.SHORT)
        return TrailPolicy(mode=TrailRenderMode.SOFT)

    def _background_policy(
        self,
        scene: SceneSpec,
        elements: list[RenderElementPlan],
    ) -> BackgroundPolicy:
        """Choose a scene-level background policy."""
        if scene.palette.name == PaletteName.RETRO and len(elements) >= 2:
            return BackgroundPolicy(decoration_mode=BackgroundDecorationMode.SCANLINE)
        return BackgroundPolicy(decoration_mode=BackgroundDecorationMode.MINIMAL)
