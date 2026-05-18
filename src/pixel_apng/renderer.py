"""Local rendering helpers for pixel APNG animations."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw

from pixel_apng.models import (
    MotionName,
    PaletteName,
    RegionName,
    RegionSpec,
    SceneSpec,
    SubjectName,
)

Palette = dict[str, tuple[int, int, int, int]]
Bounds = tuple[int, int, int, int]

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


class PixelRenderer:
    """Render scene specs into raster frames."""

    def render_frames(self, scene: SceneSpec) -> list[Image.Image]:
        """Render all frames for a scene."""
        total_frames = max(1, int(scene.animation.fps * scene.animation.duration_seconds))
        frames: list[Image.Image] = []
        for frame_index in range(total_frames):
            frames.append(self._render_frame(scene, frame_index, total_frames))
        return frames

    def _render_frame(self, scene: SceneSpec, frame_index: int, total_frames: int) -> Image.Image:
        width = scene.canvas.width
        height = scene.canvas.height
        palette = PALETTES[scene.palette.name]
        image = Image.new("RGBA", (width, height), palette["bg"])
        draw = ImageDraw.Draw(image)
        self._draw_background(scene, draw, palette, frame_index)
        for region in scene.regions:
            self._draw_region(scene, draw, palette, region, frame_index, total_frames)
        output_size = (width * scene.canvas.scale, height * scene.canvas.scale)
        return image.resize(output_size, Image.Resampling.NEAREST)

    def _draw_background(
        self,
        scene: SceneSpec,
        draw: ImageDraw.ImageDraw,
        palette: Palette,
        frame_index: int,
    ) -> None:
        if not scene.canvas.transparent_background:
            draw.rectangle([0, 0, scene.canvas.width, scene.canvas.height], fill=palette["bg"])
        if scene.palette.name == PaletteName.RETRO:
            for y in range(frame_index % 2, scene.canvas.height, 4):
                draw.line([0, y, scene.canvas.width, y], fill=(255, 255, 255, 18))
        else:
            sparkle_x = (frame_index * 7) % scene.canvas.width
            sparkle_y = 12 + (frame_index * 3) % max(1, scene.canvas.height // 2)
            draw.point((sparkle_x, sparkle_y), fill=palette["white"])

    def _draw_region(
        self,
        scene: SceneSpec,
        draw: ImageDraw.ImageDraw,
        palette: Palette,
        region: RegionSpec,
        frame_index: int,
        total_frames: int,
    ) -> None:
        bounds = self._region_box(scene, region.name)
        if region.subject == SubjectName.PROGRESS_BAR:
            self._draw_progress_bar(draw, bounds, palette, frame_index, total_frames)
        elif region.subject == SubjectName.TEXT:
            self._draw_text_block(draw, bounds, palette, region.content, frame_index, region.motion)
        elif region.subject == SubjectName.CAT:
            self._draw_cat(draw, bounds, palette, frame_index, region.motion)
        elif region.subject == SubjectName.DOG:
            self._draw_dog(draw, bounds, palette, frame_index)
        elif region.subject == SubjectName.STAR:
            self._draw_star(draw, bounds, palette, frame_index)
        elif region.subject == SubjectName.CLOUD:
            self._draw_cloud(draw, bounds, palette, frame_index)
        elif region.subject == SubjectName.HEART:
            self._draw_heart(draw, bounds, palette, frame_index)
        elif region.subject == SubjectName.ARROW:
            self._draw_arrow(draw, bounds, palette, frame_index)
        else:
            self._draw_box(draw, bounds, palette, frame_index, region.motion)

    def _region_box(self, scene: SceneSpec, region_name: RegionName) -> Bounds:
        left_ratio, top_ratio, right_ratio, bottom_ratio = _REGION_BOUNDS[region_name]
        width = scene.canvas.width
        height = scene.canvas.height
        return (
            int(width * left_ratio),
            int(height * top_ratio),
            int(width * right_ratio),
            int(height * bottom_ratio),
        )

    def _draw_progress_bar(
        self,
        draw: ImageDraw.ImageDraw,
        bounds: Bounds,
        palette: Palette,
        frame_index: int,
        total_frames: int,
    ) -> None:
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
        left, top, right, bottom = bounds
        draw.rectangle([left, top, right, bottom], outline=palette["accent_dark"], width=1)
        offset = (1 if motion == MotionName.BOUNCE else 0) + (1 if frame_index % 6 in {1, 2} else 0)
        text_y = top + 4 + offset
        for index, character in enumerate(content[:18]):
            if character == " ":
                continue
            char_x = left + 4 + index * 4
            draw.rectangle([char_x, text_y, char_x + 2, text_y + 3], fill=palette["white"])

    def _draw_cat(
        self,
        draw: ImageDraw.ImageDraw,
        bounds: Bounds,
        palette: Palette,
        frame_index: int,
        motion: MotionName,
    ) -> None:
        left, top, right, bottom = bounds
        phase = frame_index % 4
        x = left + (right - left) // 4 + (frame_index % 3)
        y = top + (bottom - top) // 4 + (1 if phase in {1, 2} else 0)
        self._draw_moving_body(draw, [x, y, x + 18, y + 12], palette, phase, motion)

    def _draw_dog(
        self, draw: ImageDraw.ImageDraw, bounds: Bounds, palette: Palette, frame_index: int
    ) -> None:
        left, top, right, bottom = bounds
        bounce = 1 if frame_index % 4 in {0, 1} else 0
        x = left + (right - left) // 4
        y = top + (bottom - top) // 4 + bounce
        draw.rectangle([x, y + 4, x + 18, y + 12], fill=palette["accent"])
        draw.rectangle([x + 14, y + 5, x + 22, y + 11], fill=palette["accent"])
        draw.rectangle([x + 18, y + 8, x + 22, y + 14], fill=palette["accent_dark"])
        for leg_x in (x + 2, x + 8, x + 14):
            draw.rectangle([leg_x, y + 11, leg_x + 2, y + 16], fill=palette["accent_dark"])

    def _draw_star(
        self, draw: ImageDraw.ImageDraw, bounds: Bounds, palette: Palette, frame_index: int
    ) -> None:
        left, top, right, bottom = bounds
        center_x = (left + right) // 2
        center_y = (top + bottom) // 2
        radius = 4 + (frame_index % 3)
        points = [
            (center_x, center_y - radius),
            (center_x + radius // 2, center_y - radius // 2),
            (center_x + radius, center_y),
            (center_x + radius // 2, center_y + radius // 2),
            (center_x, center_y + radius),
            (center_x - radius // 2, center_y + radius // 2),
            (center_x - radius, center_y),
            (center_x - radius // 2, center_y - radius // 2),
        ]
        draw.polygon(points, fill=palette["accent"])

    def _draw_cloud(
        self, draw: ImageDraw.ImageDraw, bounds: Bounds, palette: Palette, frame_index: int
    ) -> None:
        left, top, _right, _bottom = bounds
        offset = 1 if frame_index % 6 in {2, 3} else 0
        cloud_parts = [
            [left + 6, top + 6 + offset, left + 18, top + 18 + offset],
            [left + 14, top + 2 + offset, left + 28, top + 16 + offset],
            [left + 26, top + 6 + offset, left + 40, top + 18 + offset],
        ]
        for part in cloud_parts:
            draw.ellipse(part, fill=palette["white"])
        draw.rectangle(
            [left + 10, top + 12 + offset, left + 36, top + 22 + offset], fill=palette["white"]
        )

    def _draw_heart(
        self, draw: ImageDraw.ImageDraw, bounds: Bounds, palette: Palette, frame_index: int
    ) -> None:
        left, top, right, bottom = bounds
        pulse = 1 if frame_index % 4 in {0, 1} else 0
        mid_x = (left + right) // 2
        mid_y = (top + bottom) // 2
        draw.polygon(
            [
                (mid_x, mid_y + 8 + pulse),
                (mid_x - 10, mid_y),
                (mid_x - 14, mid_y - 6),
                (mid_x - 8, mid_y - 12),
                (mid_x, mid_y - 6),
                (mid_x + 8, mid_y - 12),
                (mid_x + 14, mid_y - 6),
                (mid_x + 10, mid_y),
            ],
            fill=palette["accent"],
        )

    def _draw_arrow(
        self, draw: ImageDraw.ImageDraw, bounds: Bounds, palette: Palette, frame_index: int
    ) -> None:
        left, top, right, bottom = bounds
        center_y = (top + bottom) // 2
        offset = frame_index % 3
        draw.line(
            [left + 4 + offset, center_y, right - 10 + offset, center_y],
            fill=palette["accent"],
            width=3,
        )
        draw.polygon(
            [
                (right - 10 + offset, center_y),
                (right - 18 + offset, center_y - 6),
                (right - 18 + offset, center_y + 6),
            ],
            fill=palette["accent"],
        )

    def _draw_box(
        self,
        draw: ImageDraw.ImageDraw,
        bounds: Bounds,
        palette: Palette,
        frame_index: int,
        motion: MotionName,
    ) -> None:
        left, top, right, bottom = bounds
        draw.rectangle([left, top, right, bottom], outline=palette["accent_dark"], width=2)
        if motion == MotionName.PULSE:
            inset = 1 if frame_index % 4 in {0, 1} else 3
            draw.rectangle(
                [left + inset, top + inset, right - inset, bottom - inset],
                outline=palette["accent"],
            )

    def _draw_moving_body(
        self,
        draw: ImageDraw.ImageDraw,
        body: list[int],
        palette: Palette,
        phase: int,
        motion: MotionName,
    ) -> None:
        x1, y1, x2, y2 = body
        draw.rounded_rectangle(body, radius=4, fill=palette["accent"])
        draw.rectangle([x2 - 2, y1 + 2, x2 + 4, y1 + 8], fill=palette["accent"])
        draw.rectangle([x2, y1 - 2, x2 + 2, y1 + 2], fill=palette["accent_dark"])
        draw.rectangle([x2 + 3, y1 - 2, x2 + 5, y1 + 2], fill=palette["accent_dark"])
        leg_offset = 2 if phase in {0, 3} else 0
        leg_boxes = [
            [x1 + 2, y2 - 1, x1 + 4, y2 + 4 + leg_offset],
            [x1 + 8, y2 - 1, x1 + 10, y2 + 4 - leg_offset],
            [x1 + 14, y2 - 1, x1 + 16, y2 + 4 + leg_offset],
        ]
        for leg_box in leg_boxes:
            draw.rectangle(leg_box, fill=palette["accent_dark"])
        if motion == MotionName.RUN:
            draw.line([x1 - 3, y1 + 6, x1 - 8, y1 + 4], fill=palette["accent_dark"], width=2)
        elif motion == MotionName.BOUNCE:
            draw.line([x1 - 3, y1 + 6, x1 - 7, y1 + 8], fill=palette["accent_dark"], width=2)
        else:
            draw.line([x1 - 3, y1 + 6, x1 - 7, y1 + 6], fill=palette["accent_dark"], width=2)


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
