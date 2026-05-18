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
        """Return the horizontal center of the box."""
        return self.left + self.width // 2

    @property
    def center_y(self) -> int:
        """Return the vertical center of the box."""
        return self.top + self.height // 2


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
