from __future__ import annotations

import sys
from pathlib import Path


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

ASSETS_DIR = PROJECT_ROOT / "assets"
FONT_ICONS = str(ASSETS_DIR / "fonts" / "MaterialIcons-Regular.ttf")
ICON_REPORTS = str(ASSETS_DIR / "icon_reports.png")
ICON_GOALS = str(ASSETS_DIR / "icon_goals.png")
ICON_REMINDERS = str(ASSETS_DIR / "icon_reminders.png")

# Material Icons codepoints (Unicode private-use area; rendered via MaterialIcons font)
IC_HOME     = ""  # home
IC_SWAP     = ""  # swap_horiz       -> Operations
IC_CHART    = ""  # bar_chart        -> Reports
IC_FLAG     = ""  # flag             -> Goals
IC_BELL     = ""  # notifications    -> Reminders
IC_SETTINGS = ""  # settings
IC_EXIT     = ""  # exit_to_app
IC_INCOME   = ""  # arrow_downward
IC_EXPENSE  = ""  # arrow_upward
IC_WALLET   = ""  # account_balance_wallet
IC_INFO     = ""  # info
IC_INBOX    = ""  # inbox  (empty state)
IC_EXPAND   = ""  # expand_more (chevron down)
IC_ADD      = ""  # add (+)

# ── Palette ───────────────────────────────────────────────────────────────────
COL_BG           = (0.06, 0.07, 0.09, 1)
COL_SIDEBAR      = (0.07, 0.08, 0.11, 1)
COL_SURFACE      = (0.11, 0.13, 0.17, 1)
COL_SURFACE_ELEV = (0.14, 0.16, 0.21, 1)
COL_BORDER       = (0.22, 0.25, 0.32, 1)
COL_TEXT         = (0.94, 0.95, 0.97, 1)
COL_MUTED        = (0.62, 0.66, 0.74, 1)
COL_ACCENT       = (0.18, 0.72, 0.62, 1)
COL_ACCENT_DIM   = (0.12, 0.48, 0.42, 1)
COL_INCOME       = (0.35, 0.88, 0.55, 1)
COL_EXPENSE      = (0.98, 0.52, 0.52, 1)
COL_DANGER       = (0.96, 0.30, 0.30, 1)
COL_TOOLBAR_BTN  = (0.22, 0.25, 0.32, 1)
ICON_TINT_DEFAULT = (0.82, 0.98, 0.96, 1)
ICON_TINT_PRESSED = (0.55, 0.92, 0.88, 1)
COL_MODAL_FACE   = (0.125, 0.145, 0.185, 1)

FS_BODY   = 14
FS_TITLE  = 22
FS_SMALL  = 12
FS_AMOUNT = 17
