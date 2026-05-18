"""Persistent local settings for the pixel APNG GUI."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Final

APP_DIR: Final[Path] = Path.home() / ".pixel-material-generator"
SETTINGS_DB: Final[Path] = APP_DIR / "settings.db"

_DEFAULT_SETTINGS: Final[dict[str, str]] = {
    "openai_api_key": "",
    "openai_base_url": "",
    "anthropic_api_key": "",
    "anthropic_base_url": "",
}


def _connect() -> sqlite3.Connection:
    """Open the local settings database."""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(SETTINGS_DB))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


def load_settings() -> dict[str, str]:
    """Load persisted GUI settings."""
    settings = dict(_DEFAULT_SETTINGS)
    connection = _connect()
    rows = connection.execute("SELECT key, value FROM settings").fetchall()
    connection.close()
    for row in rows:
        key = str(row["key"])
        if key in settings:
            settings[key] = str(row["value"])
    return settings


def save_settings(settings: dict[str, str]) -> None:
    """Persist GUI settings to the local SQLite database."""
    connection = _connect()
    for key, value in settings.items():
        if key not in _DEFAULT_SETTINGS:
            continue
        connection.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
    connection.commit()
    connection.close()


def export_settings() -> str:
    """Return the current settings as formatted JSON."""
    return json.dumps(load_settings(), ensure_ascii=False, indent=2)


def import_settings(content: str) -> None:
    """Replace stored settings with JSON content."""
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("设置文件必须是对象")
    normalized = {
        key: str(data.get(key, default))
        for key, default in _DEFAULT_SETTINGS.items()
    }
    save_settings(normalized)
