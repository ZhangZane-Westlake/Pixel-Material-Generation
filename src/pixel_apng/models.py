"""Typed scene specification models for pixel APNG generation."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PaletteName(StrEnum):
    """Supported palette names."""

    GREEN = "green"
    BLUE = "blue"
    RED = "red"
    PINK = "pink"
    YELLOW = "yellow"
    PURPLE = "purple"
    RETRO = "retro"


class RegionName(StrEnum):
    """Supported layout regions."""

    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"


class MotionName(StrEnum):
    """Supported animation motions."""

    RUN = "run"
    BOUNCE = "bounce"
    BLINK = "blink"
    FILL = "fill"
    PULSE = "pulse"
    SPIN = "spin"
    NONE = "none"


class SubjectName(StrEnum):
    """Supported subject templates."""

    CAT = "cat"
    DOG = "dog"
    TEXT = "text"
    PROGRESS_BAR = "progress_bar"
    STAR = "star"
    CLOUD = "cloud"
    HEART = "heart"
    ARROW = "arrow"
    BOX = "box"
    MICROWAVE = "microwave"
    UNKNOWN = "unknown"


class AnimationSpec(BaseModel):
    """Animation timing and looping settings."""

    fps: int = Field(default=12, ge=1, le=60)
    duration_seconds: float = Field(default=2.0, gt=0)
    loop: bool = True


class PaletteSpec(BaseModel):
    """Palette selection for the generated animation."""

    name: PaletteName = PaletteName.GREEN


class RegionSpec(BaseModel):
    """A positioned scene region."""

    name: RegionName
    content: str
    subject: SubjectName = SubjectName.UNKNOWN
    motion: MotionName = MotionName.NONE


class CanvasSpec(BaseModel):
    """Canvas size for internal rasterization."""

    width: int = Field(default=128, ge=32)
    height: int = Field(default=128, ge=32)
    scale: int = Field(default=4, ge=1)
    transparent_background: bool = True


class SceneSpec(BaseModel):
    """Complete scene spec returned by the LLM parser."""

    prompt: str
    canvas: CanvasSpec = Field(default_factory=CanvasSpec)
    palette: PaletteSpec = Field(default_factory=PaletteSpec)
    animation: AnimationSpec = Field(default_factory=AnimationSpec)
    regions: list[RegionSpec] = Field(default_factory=list)
    title: str | None = None
