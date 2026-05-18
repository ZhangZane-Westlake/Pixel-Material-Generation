"""Local rendering helpers for pixel APNG animations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw

from pixel_apng.composition_models import (
    BackgroundDecorationMode,
    RenderElementPlan,
    RenderPlan,
    TrailRenderMode,
)
from pixel_apng.composition_planner import CompositionPlanner
from pixel_apng.models import (
    MotionName,
    PaletteName,
    RegionName,
    SceneSpec,
    SubjectName,
)

Palette = dict[str, tuple[int, int, int, int]]
Bounds = tuple[int, int, int, int]
Grid = list[list[int]]


PALETTES: dict[PaletteName, Palette] = {
    PaletteName.GREEN: {
        "bg": (7, 24, 13, 0),
        "accent": (70, 200, 120, 255),
        "accent_dark": (20, 120, 60, 255),
        "white": (230, 255, 235, 255),
    },
    PaletteName.BLUE: {
        "bg": (6, 14, 32, 0),
        "accent": (90, 160, 255, 255),
        "accent_dark": (40, 90, 180, 255),
        "white": (235, 245, 255, 255),
    },
    PaletteName.RED: {
        "bg": (32, 8, 8, 0),
        "accent": (255, 100, 100, 255),
        "accent_dark": (160, 40, 40, 255),
        "white": (255, 240, 240, 255),
    },
    PaletteName.PINK: {
        "bg": (28, 10, 22, 0),
        "accent": (255, 138, 191, 255),
        "accent_dark": (180, 70, 125, 255),
        "white": (255, 240, 248, 255),
    },
    PaletteName.YELLOW: {
        "bg": (28, 20, 6, 0),
        "accent": (252, 219, 100, 255),
        "accent_dark": (176, 140, 38, 255),
        "white": (255, 250, 228, 255),
    },
    PaletteName.PURPLE: {
        "bg": (18, 8, 28, 0),
        "accent": (175, 133, 255, 255),
        "accent_dark": (96, 66, 176, 255),
        "white": (244, 238, 255, 255),
    },
    PaletteName.RETRO: {
        "bg": (22, 18, 14, 0),
        "accent": (236, 198, 135, 255),
        "accent_dark": (124, 90, 56, 255),
        "white": (255, 245, 220, 255),
    },
}

_REGION_BOUNDS: Final[dict[RegionName, tuple[float, float, float, float]]] = {
    RegionName.TOP: (0.1, 0.05, 0.9, 0.32),
    RegionName.MIDDLE: (0.1, 0.33, 0.9, 0.66),
    RegionName.BOTTOM: (0.1, 0.68, 0.9, 0.93),
    RegionName.LEFT: (0.05, 0.15, 0.42, 0.85),
    RegionName.RIGHT: (0.58, 0.15, 0.95, 0.85),
    RegionName.CENTER: (0.2, 0.2, 0.8, 0.8),
}

_CREATURE_KEYWORDS: Final[tuple[str, ...]] = (
    "猫",
    "dog",
    "狗",
    "兔",
    "fox",
    "熊",
    "monster",
    "宠物",
    "dragon",
    "龙",
    "bird",
    "鸟",
)
_MACHINE_KEYWORDS: Final[tuple[str, ...]] = (
    "robot",
    "机器人",
    "机甲",
    "电脑",
    "screen",
    "monitor",
    "microwave",
    "tv",
    "console",
    "camera",
)
_CELESTIAL_KEYWORDS: Final[tuple[str, ...]] = (
    "star",
    "星",
    "sun",
    "moon",
    "planet",
    "comet",
    "太阳",
    "月亮",
)
_WEATHER_KEYWORDS: Final[tuple[str, ...]] = (
    "cloud",
    "云",
    "rain",
    "storm",
    "snow",
    "lightning",
    "风",
    "weather",
)
_PLANT_KEYWORDS: Final[tuple[str, ...]] = (
    "flower",
    "tree",
    "leaf",
    "plant",
    "mushroom",
    "草",
    "花",
    "树",
    "蘑菇",
)


class ObjectMotif(StrEnum):
    """High-level visual family for procedural objects."""

    ABSTRACT = "abstract"
    CELESTIAL = "celestial"
    CREATURE = "creature"
    MACHINE = "machine"
    PLANT = "plant"
    WEATHER = "weather"


class DetailPattern(StrEnum):
    """Surface pattern used to break up flat silhouettes."""

    BAND = "band"
    DOT = "dot"
    NONE = "none"
    STRIPE = "stripe"


@dataclass(frozen=True)
class ProceduralObjectSpec:
    """Deterministic prompt-derived blueprint for a rendered object."""

    label: str
    motif: ObjectMotif
    pattern: DetailPattern
    width: int
    height: int
    eye_count: int
    appendage_length: int
    bob_amplitude: int
    sway_pixels: int
    seed: int


class PixelRenderer:
    """Render scene specs into raster frames."""

    def __init__(self, planner: CompositionPlanner | None = None) -> None:
        """Initialize the renderer with an optional composition planner."""
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
        """Render all frames for a planner-produced render plan."""
        total_frames = max(1, int(fps * duration_seconds))
        frames: list[Image.Image] = []
        for frame_index in range(total_frames):
            frames.append(self._render_plan_frame(render_plan, frame_index, total_frames))
        return frames

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
        output_size = (
            render_plan.canvas_width * render_plan.output_scale,
            render_plan.canvas_height * render_plan.output_scale,
        )
        return image.resize(output_size, Image.Resampling.NEAREST)

    def _draw_background_from_plan(
        self,
        render_plan: RenderPlan,
        draw: ImageDraw.ImageDraw,
        palette: Palette,
        frame_index: int,
    ) -> None:
        """Draw the animated background selected by the planner."""
        if render_plan.background_policy.decoration_mode == BackgroundDecorationMode.SCANLINE:
            for y_coord in range(frame_index % 2, render_plan.canvas_height, 4):
                draw.line([0, y_coord, render_plan.canvas_width, y_coord], fill=(255, 255, 255, 18))
            return
        if render_plan.background_policy.decoration_mode != BackgroundDecorationMode.SPARKLE:
            return
        sparkle_x = (frame_index * 7) % render_plan.canvas_width
        sparkle_y = 12 + (frame_index * 3) % max(1, render_plan.canvas_height // 2)
        draw.point((sparkle_x, sparkle_y), fill=palette["white"])

    def _draw_render_element(
        self,
        draw: ImageDraw.ImageDraw,
        palette: Palette,
        element: RenderElementPlan,
        frame_index: int,
        total_frames: int,
    ) -> None:
        """Draw one element from the render plan."""
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
            self._draw_text_block(
                draw,
                bounds,
                palette,
                element.content,
                frame_index,
                element.motion,
            )
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

    def _draw_progress_bar(
        self,
        draw: ImageDraw.ImageDraw,
        bounds: Bounds,
        palette: Palette,
        frame_index: int,
        total_frames: int,
    ) -> None:
        """Draw a filling progress bar."""
        left, top, right, bottom = bounds
        draw.rectangle([left, top, right, bottom], outline=palette["accent_dark"], width=2)
        progress = frame_index / max(1, total_frames - 1)
        fill_width = int((right - left - 4) * progress)
        draw.rectangle(
            [left + 2, top + 2, left + 2 + fill_width, bottom - 2], fill=palette["accent"]
        )

    def _draw_text_block(
        self,
        draw: ImageDraw.ImageDraw,
        bounds: Bounds,
        palette: Palette,
        content: str,
        frame_index: int,
        motion: MotionName,
    ) -> None:
        """Draw a blocky text placeholder."""
        left, top, right, bottom = bounds
        draw.rectangle([left, top, right, bottom], outline=palette["accent_dark"], width=1)
        offset = (1 if motion == MotionName.BOUNCE else 0) + (1 if frame_index % 6 in {1, 2} else 0)
        text_y = top + 4 + offset
        for index, character in enumerate(content[:18]):
            if character == " ":
                continue
            char_x = left + 4 + index * 4
            draw.rectangle([char_x, text_y, char_x + 2, text_y + 3], fill=palette["white"])

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

    def _build_object_spec(self, content: str, motion: MotionName) -> ProceduralObjectSpec:
        """Convert free-form content into a deterministic rendering blueprint."""
        normalized_content = content.strip() or "object"
        seed = self._seed_from_text(normalized_content)
        motif = self._infer_object_motif(normalized_content)
        bob_amplitude = 2 if motion in {MotionName.BOUNCE, MotionName.RUN, MotionName.SPIN} else 1
        sway_pixels = 3 if motion == MotionName.RUN else 2 if motion == MotionName.SPIN else 1
        return ProceduralObjectSpec(
            label=normalized_content,
            motif=motif,
            pattern=self._pick_pattern(seed),
            width=8 + seed % 5,
            height=7 + (seed // 3) % 5,
            eye_count=2 if motif in {ObjectMotif.CREATURE, ObjectMotif.MACHINE} else 1,
            appendage_length=2 + (seed // 11) % 4,
            bob_amplitude=bob_amplitude,
            sway_pixels=sway_pixels,
            seed=seed,
        )

    def _seed_from_text(self, content: str) -> int:
        """Hash content into a stable positive integer seed."""
        digest = sha256(content.encode("utf-8")).hexdigest()
        return int(digest[:12], 16)

    def _infer_object_motif(self, content: str) -> ObjectMotif:
        """Infer a visual motif from prompt keywords."""
        lowered = content.lower()
        if self._contains_keyword(content, lowered, _CREATURE_KEYWORDS):
            return ObjectMotif.CREATURE
        if self._contains_keyword(content, lowered, _MACHINE_KEYWORDS):
            return ObjectMotif.MACHINE
        if self._contains_keyword(content, lowered, _CELESTIAL_KEYWORDS):
            return ObjectMotif.CELESTIAL
        if self._contains_keyword(content, lowered, _WEATHER_KEYWORDS):
            return ObjectMotif.WEATHER
        if self._contains_keyword(content, lowered, _PLANT_KEYWORDS):
            return ObjectMotif.PLANT
        return ObjectMotif.ABSTRACT

    def _contains_keyword(self, content: str, lowered: str, keywords: tuple[str, ...]) -> bool:
        """Return whether any motif keyword is present."""
        return any(keyword in content or keyword.lower() in lowered for keyword in keywords)

    def _pick_pattern(self, seed: int) -> DetailPattern:
        """Choose a repeatable surface pattern from the object seed."""
        patterns = (
            DetailPattern.NONE,
            DetailPattern.STRIPE,
            DetailPattern.DOT,
            DetailPattern.BAND,
        )
        return patterns[seed % len(patterns)]

    def _build_sprite_grid(self, spec: ProceduralObjectSpec) -> Grid:
        """Construct a pixel sprite grid for the given blueprint."""
        grid: Grid = [[0 for _ in range(18)] for _ in range(18)]
        if spec.motif == ObjectMotif.CREATURE:
            self._paint_creature(grid, spec)
        elif spec.motif == ObjectMotif.MACHINE:
            self._paint_machine(grid, spec)
        elif spec.motif == ObjectMotif.CELESTIAL:
            self._paint_celestial(grid, spec)
        elif spec.motif == ObjectMotif.WEATHER:
            self._paint_weather(grid, spec)
        elif spec.motif == ObjectMotif.PLANT:
            self._paint_plant(grid, spec)
        else:
            self._paint_abstract(grid, spec)
        self._apply_pattern(grid, spec.pattern)
        return grid

    def _paint_creature(self, grid: Grid, spec: ProceduralObjectSpec) -> None:
        """Paint a creature-like sprite with head, body, and limbs."""
        center_x = 9
        head_center_y = 6
        body_center_y = 10
        self._paint_ellipse(grid, center_x, body_center_y, spec.width // 2, spec.height // 2, 1)
        self._paint_ellipse(grid, center_x + 2, head_center_y, spec.width // 3, spec.height // 3, 1)
        ear_height = 2 + spec.seed % 2
        self._paint_line(
            grid,
            center_x + 1,
            head_center_y - 3,
            center_x,
            head_center_y - 3 - ear_height,
            2,
        )
        self._paint_line(
            grid,
            center_x + 4,
            head_center_y - 3,
            center_x + 5,
            head_center_y - 3 - ear_height,
            2,
        )
        for leg_offset in (-(spec.width // 3), 0, spec.width // 3):
            leg_x = center_x + leg_offset
            self._paint_line(grid, leg_x, body_center_y + spec.height // 2 - 1, leg_x, 16, 2)
        self._paint_line(
            grid,
            center_x - spec.width // 2 - 1,
            body_center_y,
            center_x - spec.width // 2 - 1 - spec.appendage_length,
            body_center_y - 1,
            2,
        )
        for eye_index in range(spec.eye_count):
            eye_x = center_x + eye_index * 2 + 1
            self._paint_point(grid, eye_x, head_center_y, 3)

    def _paint_machine(self, grid: Grid, spec: ProceduralObjectSpec) -> None:
        """Paint a machine-like sprite with a screen and antenna."""
        left = 9 - spec.width // 2
        top = 6
        right = left + spec.width
        bottom = top + spec.height
        self._paint_rect(grid, left, top, right, bottom, 1)
        self._paint_rect(grid, left + 2, top + 2, right - 2, bottom - 3, 2)
        self._paint_rect(grid, left + 3, top + 3, right - 3, top + 6, 3)
        antenna_height = 2 + spec.appendage_length
        self._paint_line(grid, 9, top - 1, 9, top - antenna_height, 2)
        self._paint_point(grid, 9, top - antenna_height - 1, 3)
        self._paint_line(grid, left - 1, top + 4, left - 3, top + 2, 2)
        self._paint_line(grid, right + 1, top + 4, right + 3, top + 2, 2)
        self._paint_line(grid, left + 2, bottom + 1, left + 1, bottom + 3, 2)
        self._paint_line(grid, right - 2, bottom + 1, right - 1, bottom + 3, 2)

    def _paint_celestial(self, grid: Grid, spec: ProceduralObjectSpec) -> None:
        """Paint a star, moon, or other celestial sprite."""
        center_x = 9
        center_y = 9
        radius = 3 + spec.seed % 3
        self._paint_ellipse(grid, center_x, center_y, radius, radius, 1)
        for delta in range(-radius - 1, radius + 2):
            if delta != 0:
                self._paint_point(grid, center_x + delta, center_y, 2)
                self._paint_point(grid, center_x, center_y + delta, 2)
        if spec.seed % 2 == 0:
            self._paint_line(grid, center_x - 4, center_y - 4, center_x + 4, center_y + 4, 2)
            self._paint_line(grid, center_x - 4, center_y + 4, center_x + 4, center_y - 4, 2)
        self._paint_point(grid, center_x, center_y, 3)

    def _paint_weather(self, grid: Grid, spec: ProceduralObjectSpec) -> None:
        """Paint a cloud-like or storm-like sprite."""
        self._paint_ellipse(grid, 6, 8, 3, 3, 3)
        self._paint_ellipse(grid, 10, 6, 4, 3, 3)
        self._paint_ellipse(grid, 13, 8, 3, 3, 3)
        self._paint_rect(grid, 5, 8, 14, 11, 3)
        if spec.seed % 2 == 0:
            self._paint_line(grid, 8, 12, 7, 15, 2)
            self._paint_line(grid, 11, 12, 10, 15, 2)
        else:
            self._paint_line(grid, 10, 11, 8, 14, 2)
            self._paint_line(grid, 8, 14, 11, 14, 2)
            self._paint_line(grid, 11, 14, 9, 17, 2)

    def _paint_plant(self, grid: Grid, spec: ProceduralObjectSpec) -> None:
        """Paint a plant-like sprite with stem and canopy."""
        stem_height = 5 + spec.seed % 3
        self._paint_line(grid, 9, 16, 9, 16 - stem_height, 2)
        self._paint_line(grid, 9, 12, 6, 10, 2)
        self._paint_line(grid, 9, 11, 12, 9, 2)
        cap_radius = 4 if "蘑菇" in spec.label or "mushroom" in spec.label.lower() else 3
        self._paint_ellipse(grid, 9, 7, cap_radius + 2, cap_radius, 1)
        self._paint_rect(grid, 5, 7, 13, 8, 1)
        self._paint_point(grid, 7, 7, 3)
        self._paint_point(grid, 11, 7, 3)

    def _paint_abstract(self, grid: Grid, spec: ProceduralObjectSpec) -> None:
        """Paint a generic prompt-derived abstract object."""
        center_x = 9
        center_y = 9
        radius_x = 3 + spec.width // 3
        radius_y = 3 + spec.height // 3
        self._paint_ellipse(grid, center_x, center_y, radius_x, radius_y, 1)
        if spec.seed % 2 == 0:
            self._paint_rect(grid, center_x - 2, center_y - 5, center_x + 2, center_y - 3, 2)
        else:
            self._paint_line(grid, center_x - 5, center_y, center_x + 5, center_y, 2)
            self._paint_line(grid, center_x, center_y - 5, center_x, center_y + 5, 2)
        self._paint_point(grid, center_x, center_y, 3)

    def _apply_pattern(self, grid: Grid, pattern: DetailPattern) -> None:
        """Overlay a simple internal pattern onto the filled sprite."""
        if pattern == DetailPattern.NONE:
            return
        for y_coord, row in enumerate(grid):
            for x_coord, value in enumerate(row):
                if value != 1:
                    continue
                if pattern == DetailPattern.STRIPE and (x_coord + y_coord) % 4 == 0:
                    row[x_coord] = 2
                elif pattern == DetailPattern.DOT and x_coord % 3 == 0 and y_coord % 3 == 0:
                    row[x_coord] = 3
                elif pattern == DetailPattern.BAND and 6 <= y_coord <= 8:
                    row[x_coord] = 2

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
            trail_width = 4 + spec.appendage_length
            start_x = max(left + 2, right // 2 - trail_width)
            trail_length = 3 if trail_mode == TrailRenderMode.SHORT else 6
            draw.line(
                [start_x, center_y + 4, start_x - trail_length, center_y + 2],
                fill=palette["accent_dark"],
                width=1 if trail_mode == TrailRenderMode.SOFT else 2,
            )
        elif motion == MotionName.SPIN:
            draw.arc(
                [left + 4, top + 4, right - 4, bottom - 4],
                start=20,
                end=320,
                fill=palette["accent_dark"],
            )
        elif motion == MotionName.PULSE and frame_index % 4 in {0, 1}:
            draw.rectangle(
                [left + 2, top + 2, right - 2, bottom - 2],
                outline=palette["accent"],
                width=1,
            )

    def _draw_grid_sprite(
        self,
        draw: ImageDraw.ImageDraw,
        bounds: Bounds,
        palette: Palette,
        grid: Grid,
        spec: ProceduralObjectSpec,
        frame_index: int,
    ) -> None:
        """Rasterize a low-resolution sprite grid into the region bounds."""
        left, top, right, bottom = bounds
        grid_height = len(grid)
        grid_width = len(grid[0]) if grid else 0
        usable_width = max(1, right - left - 4)
        usable_height = max(1, bottom - top - 4)
        cell_size = max(1, min(usable_width // grid_width, usable_height // grid_height))
        sprite_width = grid_width * cell_size
        sway = self._compute_horizontal_sway(spec, frame_index)
        bob = self._compute_vertical_bob(spec, frame_index)
        origin_x = left + (usable_width - sprite_width) // 2 + 2 + sway
        origin_y = top + bob
        color_map = {1: palette["accent"], 2: palette["accent_dark"], 3: palette["white"]}
        for y_coord, row in enumerate(grid):
            for x_coord, value in enumerate(row):
                if value == 0:
                    continue
                pixel_left = origin_x + x_coord * cell_size
                pixel_top = origin_y + y_coord * cell_size
                draw.rectangle(
                    [pixel_left, pixel_top, pixel_left + cell_size - 1, pixel_top + cell_size - 1],
                    fill=color_map[value],
                )

    def _compute_horizontal_sway(self, spec: ProceduralObjectSpec, frame_index: int) -> int:
        """Return the current frame's horizontal sway."""
        phase = frame_index % 6
        if phase in {0, 1}:
            return -spec.sway_pixels
        if phase in {3, 4}:
            return spec.sway_pixels
        return 0

    def _compute_vertical_bob(self, spec: ProceduralObjectSpec, frame_index: int) -> int:
        """Return the current frame's vertical bob offset."""
        phase = frame_index % 6
        if phase in {1, 2}:
            return -spec.bob_amplitude
        if phase in {4, 5}:
            return spec.bob_amplitude
        return 0

    def _paint_rect(
        self,
        grid: Grid,
        left: int,
        top: int,
        right: int,
        bottom: int,
        color: int,
    ) -> None:
        """Fill a rectangle on the sprite grid."""
        for y_coord in range(max(0, top), min(len(grid), bottom + 1)):
            row = grid[y_coord]
            for x_coord in range(max(0, left), min(len(row), right + 1)):
                row[x_coord] = color

    def _paint_ellipse(
        self,
        grid: Grid,
        center_x: int,
        center_y: int,
        radius_x: int,
        radius_y: int,
        color: int,
    ) -> None:
        """Fill an ellipse on the sprite grid."""
        safe_radius_x = max(1, radius_x)
        safe_radius_y = max(1, radius_y)
        for y_coord, row in enumerate(grid):
            for x_coord in range(len(row)):
                distance = ((x_coord - center_x) ** 2) / (safe_radius_x**2) + (
                    (y_coord - center_y) ** 2
                ) / (safe_radius_y**2)
                if distance <= 1:
                    row[x_coord] = color

    def _paint_line(
        self,
        grid: Grid,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        color: int,
    ) -> None:
        """Draw a Bresenham-style line on the sprite grid."""
        delta_x = abs(end_x - start_x)
        delta_y = -abs(end_y - start_y)
        step_x = 1 if start_x < end_x else -1
        step_y = 1 if start_y < end_y else -1
        error = delta_x + delta_y
        current_x = start_x
        current_y = start_y
        while True:
            self._paint_point(grid, current_x, current_y, color)
            if current_x == end_x and current_y == end_y:
                break
            doubled_error = 2 * error
            if doubled_error >= delta_y:
                error += delta_y
                current_x += step_x
            if doubled_error <= delta_x:
                error += delta_x
                current_y += step_y

    def _paint_point(self, grid: Grid, x_coord: int, y_coord: int, color: int) -> None:
        """Set a single pixel on the sprite grid if it is in bounds."""
        if y_coord < 0 or y_coord >= len(grid):
            return
        row = grid[y_coord]
        if x_coord < 0 or x_coord >= len(row):
            return
        row[x_coord] = color


class PixelExporter:
    """Write rendered frames as APNG."""

    def save_apng(self, frames: list[Image.Image], output_path: Path, fps: int) -> None:
        """Save an APNG animation."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration = int(1000 / fps)
        first_frame, *rest = frames
        first_frame.save(
            output_path,
            save_all=True,
            append_images=rest,
            format="PNG",
            duration=duration,
            loop=0,
            disposal=2,
        )
