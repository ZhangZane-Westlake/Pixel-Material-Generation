"""Tests for GUI and packaging helpers."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_gui_module_exists() -> None:
    """Ensure the GUI entrypoint module is present."""
    assert (PROJECT_ROOT / "src" / "pixel_apng" / "gui.py").exists()


def test_mac_packaging_files_exist() -> None:
    """Ensure macOS packaging scripts are present."""
    assert (PROJECT_ROOT / "mac" / "build.sh").exists()
    assert (PROJECT_ROOT / "mac" / "generate_icon.py").exists()
