from __future__ import annotations

import sys
from pathlib import Path

import flet as ft


def _runtime_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent.parent


def _runtime_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    return _runtime_root() / "data"


PROJECT_ROOT = _runtime_root()
DATA_DIR = _runtime_data_dir()
PLAINTEXT_DB_PATH = DATA_DIR / "personal_finance.sqlite3"
ENCRYPTED_DB_PATH = DATA_DIR / "personal_finance.sqlite3.enc"

GREEN = "#22C55E"
GREEN_SOFT = "#DCFCE7"
RED = "#EF4444"
RED_SOFT = "#FEE2E2"
BLUE_SOFT = "#DBEAFE"
PURPLE = "#8B5CF6"
TEXT_MUTED = "#64748B"
CARD_LIGHT = "#FFFFFF"
BG_LIGHT = "#F8FAFC"
CARD_DARK = "#1E293B"
BG_DARK = "#0F172A"


def card_bgcolor(page: ft.Page) -> str:
    return CARD_DARK if page.theme_mode == ft.ThemeMode.DARK else CARD_LIGHT


def page_bgcolor(page: ft.Page) -> str:
    return BG_DARK if page.theme_mode == ft.ThemeMode.DARK else BG_LIGHT


def card_shadow() -> ft.BoxShadow:
    return ft.BoxShadow(
        spread_radius=0,
        blur_radius=12,
        color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
        offset=ft.Offset(0, 4),
    )
