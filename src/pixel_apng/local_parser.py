"""Local deterministic parser for tests and offline demos."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from pixel_apng.models import (
    AnimationSpec,
    CanvasSpec,
    MotionName,
    PaletteName,
    PaletteSpec,
    RegionName,
    RegionSpec,
    SceneSpec,
    SubjectName,
)
from pixel_apng.providers import PromptParser

_REGION_KEYWORDS: dict[RegionName, tuple[str, ...]] = {
    RegionName.TOP: ("上方", "顶部", "上面", "top"),
    RegionName.BOTTOM: ("下方", "底部", "下面", "bottom"),
    RegionName.LEFT: ("左侧", "左边", "left"),
    RegionName.RIGHT: ("右侧", "右边", "right"),
    RegionName.CENTER: ("中间", "中央", "居中", "center"),
    RegionName.MIDDLE: ("中部", "middle"),
}

_PALETTE_KEYWORDS: dict[PaletteName, tuple[str, ...]] = {
    PaletteName.GREEN: ("绿色", "绿", "green"),
    PaletteName.BLUE: ("蓝色", "蓝", "blue"),
    PaletteName.RED: ("红色", "红", "red"),
    PaletteName.PINK: ("粉色", "粉", "pink"),
    PaletteName.YELLOW: ("黄色", "黄", "yellow", "gold"),
    PaletteName.PURPLE: ("紫色", "紫", "purple"),
    PaletteName.RETRO: ("复古", "retro", "像素复古"),
}

_SUBJECT_KEYWORDS: dict[SubjectName, tuple[str, ...]] = {
    SubjectName.PROGRESS_BAR: ("进度条", "加载条", "progress bar", "loading bar"),
    SubjectName.TEXT: ("文字", "文本", "字幕", "text", "label"),
}

_MOTION_KEYWORDS: dict[MotionName, tuple[str, ...]] = {
    MotionName.RUN: ("奔跑", "跑", "running", "run"),
    MotionName.BOUNCE: ("跳动", "弹跳", "bounce", "jump"),
    MotionName.BLINK: ("闪烁", "blink", "flash"),
    MotionName.FILL: ("填充", "加载", "fill", "loading"),
    MotionName.PULSE: ("脉冲", "呼吸", "pulse"),
    MotionName.SPIN: ("旋转", "spin", "rotate"),
}


class LocalPromptParser(PromptParser):
    """Parse common prompts without calling an external model."""

    def parse(self, prompt: str) -> SceneSpec:
        """Parse a prompt into a scene spec."""
        lower_prompt = prompt.lower()
        palette = self._match_palette(prompt, lower_prompt)
        regions = self._parse_regions(prompt, lower_prompt)
        if not regions:
            regions = self._fallback_regions(prompt, lower_prompt)
        return SceneSpec(
            prompt=prompt,
            canvas=CanvasSpec(),
            palette=PaletteSpec(name=palette),
            animation=AnimationSpec(),
            regions=regions,
            title="Pixel APNG",
        )

    def _parse_regions(self, prompt: str, lower_prompt: str) -> list[RegionSpec]:
        """Parse explicit layout clauses into typed regions."""
        clauses = self._split_clauses(prompt, ("，", ",", "；", ";", "。", "."))
        regions: list[RegionSpec] = []
        for clause in clauses:
            lower_clause = clause.lower()
            region_name = self._match_region(clause, lower_clause)
            if region_name is None:
                continue
            subject = self._match_subject(clause, lower_clause)
            motion = self._match_motion(clause, lower_clause)
            if subject == SubjectName.PROGRESS_BAR:
                motion = MotionName.FILL
            regions.append(
                RegionSpec(
                    name=region_name,
                    content=self._clean_content(clause),
                    subject=subject,
                    motion=motion,
                )
            )
        return self._deduplicate_regions(regions)

    def _fallback_regions(self, prompt: str, lower_prompt: str) -> list[RegionSpec]:
        """Build a default centered scene when no layout keywords are present."""
        subject = self._match_subject(prompt, lower_prompt)
        motion = self._match_motion(prompt, lower_prompt)
        if subject == SubjectName.PROGRESS_BAR:
            motion = MotionName.FILL
        regions = [
            RegionSpec(
                name=RegionName.CENTER,
                content=prompt,
                subject=subject,
                motion=motion,
            )
        ]
        if "进度" in prompt or "progress" in lower_prompt or "loading" in lower_prompt:
            regions.append(
                RegionSpec(
                    name=RegionName.BOTTOM,
                    content="progress bar",
                    subject=SubjectName.PROGRESS_BAR,
                    motion=MotionName.FILL,
                )
            )
        return regions

    def _match_palette(self, prompt: str, lower_prompt: str) -> PaletteName:
        """Return the first palette keyword match in the prompt."""
        for palette_name, keywords in _PALETTE_KEYWORDS.items():
            if self._contains_any(prompt, lower_prompt, keywords):
                return palette_name
        return PaletteName.GREEN

    def _match_region(self, prompt: str, lower_prompt: str) -> RegionName | None:
        """Return the first layout region match in a clause."""
        for region_name, keywords in _REGION_KEYWORDS.items():
            if self._contains_any(prompt, lower_prompt, keywords):
                return region_name
        return None

    def _match_subject(self, prompt: str, lower_prompt: str) -> SubjectName:
        """Classify a clause as UI text, progress bar, or a generic object."""
        for subject_name, keywords in _SUBJECT_KEYWORDS.items():
            if self._contains_any(prompt, lower_prompt, keywords):
                return subject_name
        return SubjectName.OBJECT

    def _match_motion(self, prompt: str, lower_prompt: str) -> MotionName:
        """Return the first supported animation motion found in a clause."""
        for motion_name, keywords in _MOTION_KEYWORDS.items():
            if self._contains_any(prompt, lower_prompt, keywords):
                return motion_name
        return MotionName.NONE

    def _contains_any(self, prompt: str, lower_prompt: str, keywords: Sequence[str]) -> bool:
        """Return whether any keyword matches the original or lowered clause."""
        return any(keyword in prompt or keyword.lower() in lower_prompt for keyword in keywords)

    def _split_clauses(self, prompt: str, separators: Iterable[str]) -> list[str]:
        """Split a prompt into clauses using multilingual punctuation."""
        clauses = [prompt]
        for separator in separators:
            next_clauses: list[str] = []
            for clause in clauses:
                next_clauses.extend(clause.split(separator))
            clauses = next_clauses
        return [clause.strip() for clause in clauses if clause.strip()]

    def _clean_content(self, clause: str) -> str:
        """Remove layout boilerplate while preserving the object description."""
        content = clause
        for keywords in _REGION_KEYWORDS.values():
            for keyword in keywords:
                content = content.replace(keyword, "")
        for keywords in _SUBJECT_KEYWORDS.values():
            for keyword in keywords:
                content = content.replace(keyword, "")
        for removable in (
            "一只",
            "一个",
            "一台",
            "一朵",
            "是一",
            "是",
            "有",
            "为",
            "色调",
            "tone",
            "palette",
        ):
            content = content.replace(removable, "")
        return content.strip() or clause.strip()

    def _deduplicate_regions(self, regions: list[RegionSpec]) -> list[RegionSpec]:
        """Keep the last region definition for each layout slot."""
        deduplicated: dict[RegionName, RegionSpec] = {}
        for region in regions:
            deduplicated[region.name] = region
        return list(deduplicated.values())
