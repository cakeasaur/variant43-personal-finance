from __future__ import annotations

import atexit
import glob
import os
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.graphics.vertex_instructions import RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from src.core.models import Transaction, TransactionType
from src.core.reporting import expense_by_category, expense_by_day, totals_for_period
from src.infra.db.connection import connect, transaction
from src.infra.db.repositories import (
    CategoryRepository,
    GoalRepository,
    ReminderRepository,
    TransactionRepository,
)
from src.infra.db.schema import init_schema
from src.infra.security.crypto import (
    InvalidPasswordError,
    decrypt_file_to_path,
    encrypt_file_to_path,
)


def _runtime_root() -> Path:
    """
    Project root at runtime.

    - Source run: repository root (parent of `src/`)
    - PyInstaller: temporary extract dir (`sys._MEIPASS`)
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _runtime_root()


def _runtime_data_dir() -> Path:
    """Writable data directory for the encrypted/plaintext DB files."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    return PROJECT_ROOT / "data"


DATA_DIR = _runtime_data_dir()
PLAINTEXT_DB_PATH = DATA_DIR / "personal_finance.sqlite3"
ENCRYPTED_DB_PATH = DATA_DIR / "personal_finance.sqlite3.enc"

ASSETS_DIR = PROJECT_ROOT / "assets"
ICON_REPORTS = str(ASSETS_DIR / "icon_reports.png")
ICON_GOALS = str(ASSETS_DIR / "icon_goals.png")
ICON_REMINDERS = str(ASSETS_DIR / "icon_reminders.png")


def encryption_enabled() -> bool:
    """
    Encryption is supported on desktop builds, but is optional on Android.

    - Android builds can disable encryption to keep the APK build reproducible
      (cryptography may be hard to compile under python-for-android).
    - Desktop remains encrypted by default.
    """
    if str(os.environ.get("PF_DISABLE_ENCRYPTION", "")).strip() in {"1", "true", "yes", "on"}:
        return False
    try:
        from kivy.utils import (
            platform,  # local import: Kivy may not be imported in some tooling contexts
        )

        if platform == "android":
            return False
    except Exception:
        pass
    return True


def _cleanup_orphaned_plaintext_dbs() -> None:
    """
    Remove plaintext DB files left behind by previous sessions that crashed
    before on_stop() could encrypt and delete them.
    """
    pattern = os.path.join(tempfile.gettempdir(), "pfm_*.sqlite3")
    for leftover in glob.glob(pattern):
        try:
            os.unlink(leftover)
        except Exception:
            pass


def _new_temp_plaintext_db_path() -> Path:
    """
    Create a unique temp path for a plaintext SQLite database.

    We keep plaintext out of `data/` to reduce the chance of leaving readable data
    behind (e.g. if the app crashes before `on_stop` runs).
    """
    fd, p = tempfile.mkstemp(prefix="pfm_", suffix=".sqlite3")
    try:
        os.close(fd)
    except Exception:
        pass
    path = Path(p)
    atexit.register(_remove_file_best_effort, path)
    return path


def _remove_file_best_effort(path: Path) -> None:
    """Delete a file ignoring any errors (used as atexit handler)."""
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass

# App-wide palette (dark “finance app” — closer to CoinKeeper / wallet UIs)
COL_BG = (0.06, 0.07, 0.09, 1)
COL_SURFACE = (0.11, 0.13, 0.17, 1)
COL_SURFACE_ELEV = (0.14, 0.16, 0.21, 1)
COL_BORDER = (0.22, 0.25, 0.32, 1)
COL_TEXT = (0.94, 0.95, 0.97, 1)
COL_MUTED = (0.62, 0.66, 0.74, 1)
COL_ACCENT = (0.18, 0.72, 0.62, 1)  # mint / teal
COL_ACCENT_DIM = (0.12, 0.48, 0.42, 1)
COL_INCOME = (0.35, 0.88, 0.55, 1)
COL_EXPENSE = (0.98, 0.52, 0.52, 1)
COL_DANGER = (0.96, 0.30, 0.30, 1)
# Toolbar / icon contrast (icons were nearly invisible on flat COL_SURFACE_ELEV)
COL_TOOLBAR_BTN = (0.22, 0.25, 0.32, 1)
ICON_TINT_DEFAULT = (0.82, 0.98, 0.96, 1)
ICON_TINT_PRESSED = (0.55, 0.92, 0.88, 1)
COL_MODAL_FACE = (0.125, 0.145, 0.185, 1)

FS_BODY = 14
FS_TITLE = 22
FS_SMALL = 12
FS_AMOUNT = 17

MONTH_NAMES_RU = (
    "",
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
)


def format_rub(cents: int) -> str:
    return f"{cents / 100:,.2f}".replace(",", " ")


def month_title_ru(dt: datetime) -> str:
    return f"{MONTH_NAMES_RU[dt.month]} {dt.year}".capitalize()


def ui_button(text: str, *, width: int | None = None, accent: bool = False) -> Button:
    b = Button(
        text=text,
        size_hint_x=None if width is not None else 1,
        width=width or 100,
        background_normal="",
        background_color=COL_ACCENT if accent else COL_SURFACE_ELEV,
        color=COL_TEXT,
    )
    return b


def ui_label(text: str, *, height: int = 24, muted: bool = False) -> Label:
    lbl = Label(
        text=text,
        color=COL_MUTED if muted else COL_TEXT,
        size_hint_y=None,
        height=height,
        halign="left",
        valign="middle",
        font_size=FS_BODY,
    )
    lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
    return lbl


def ui_error_label() -> Label:
    lbl = Label(
        text="",
        color=COL_DANGER,
        size_hint_y=None,
        height=24,
        halign="left",
        valign="middle",
        font_size=FS_BODY,
    )
    lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
    return lbl


def ui_text_input(hint: str, *, password: bool = False) -> TextInput:
    return TextInput(
        hint_text=hint,
        password=password,
        multiline=False,
        background_normal="",
        background_active="",
        background_color=COL_SURFACE,
        foreground_color=COL_TEXT,
        hint_text_color=COL_MUTED,
        cursor_color=COL_ACCENT,
        padding=(12, 12),
        font_size=FS_BODY,
    )


def ui_spinner(**kwargs) -> Spinner:
    return Spinner(
        background_normal="",
        background_color=COL_SURFACE_ELEV,
        color=COL_TEXT,
        font_size=FS_BODY,
        **kwargs,
    )


def style_popup(popup: Popup) -> None:
    """Tune Kivy Popup chrome so it matches our dark surfaces (avoids flat black sheets)."""
    popup.title_color = COL_TEXT
    popup.title_size = "17sp"
    popup.separator_color = COL_ACCENT_DIM
    popup.separator_height = 1
    popup.background_color = (*COL_TOOLBAR_BTN[:3], 1)
    popup.overlay_color = (0.02, 0.03, 0.05, 0.62)


def palette_color(key: str) -> tuple[float, float, float, float]:
    colors = (
        COL_ACCENT,
        (0.45, 0.58, 0.98, 1),
        (0.96, 0.62, 0.34, 1),
        (0.74, 0.56, 0.96, 1),
        (0.52, 0.86, 0.48, 1),
        (0.98, 0.48, 0.62, 1),
    )
    return colors[abs(hash(key)) % len(colors)]


RECURRENCE_LABELS = ["Не повторять", "Ежедневно", "Еженедельно", "Ежемесячно"]
RECURRENCE_VALUES = ["none", "daily", "weekly", "monthly"]
RECURRENCE_UI_TO_VALUE = dict(zip(RECURRENCE_LABELS, RECURRENCE_VALUES, strict=True))
RECURRENCE_VALUE_TO_UI = {v: k for k, v in RECURRENCE_UI_TO_VALUE.items()}


def recurrence_display(value: str) -> str:
    return RECURRENCE_VALUE_TO_UI.get(value, value)


def parse_money(text: str) -> int:
    """Convert a user-entered money string to integer cents using Decimal to avoid float rounding."""
    try:
        cents = (Decimal(text.strip().replace(",", ".")) * 100).to_integral_value()
        return int(cents)
    except InvalidOperation as exc:
        raise ValueError("Некорректная сумма") from exc


class ModalSheet(BoxLayout):
    """Root widget for Popup content: solid themed panel behind all children."""

    def __init__(self, **kwargs) -> None:
        super().__init__(orientation="vertical", padding=18, spacing=14, **kwargs)
        with self.canvas.before:
            Color(*COL_BORDER)
            self._bg_outer = RoundedRectangle(radius=[24, 24, 24, 24])
            Color(*COL_MODAL_FACE)
            self._bg = RoundedRectangle(radius=[22, 22, 22, 22])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

    def _sync_bg(self, *_args) -> None:
        o = 1.5
        self._bg_outer.pos = (self.x - o, self.y - o)
        self._bg_outer.size = (self.width + 2 * o, self.height + 2 * o)
        self._bg.pos = self.pos
        self._bg.size = self.size


class BarTrack(Widget):
    """Horizontal bar 0..ratio (for mini-charts in reports / goal progress)."""

    def __init__(self, ratio: float, fill_color: tuple[float, float, float, float], **kwargs) -> None:
        super().__init__(size_hint_y=None, height=12, **kwargs)
        self.ratio = max(0.0, min(1.0, ratio))
        self.fill_color = fill_color
        with self.canvas.before:
            Color(*COL_BG)
            self._track = RoundedRectangle(radius=[6, 6, 6, 6])
            Color(*fill_color)
            self._fill = Rectangle()
        self.bind(pos=self.redraw, size=self.redraw)
        self.redraw()

    def redraw(self, *_args) -> None:
        self._track.pos = self.pos
        self._track.size = self.size
        fill_w = max(0.0, self.width * self.ratio)
        self._fill.pos = self.pos
        self._fill.size = (fill_w, self.height)


class ReportBarRow(BoxLayout):
    """One named metric with value + bar (CoinKeeper-style row)."""

    def __init__(
        self,
        name: str,
        value_cents: int,
        *,
        max_cents: int,
        bar_color: tuple[float, float, float, float],
        **kwargs,
    ) -> None:
        super().__init__(orientation="vertical", spacing=6, size_hint_y=None, height=52, **kwargs)
        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=22, spacing=8)
        nm = Label(
            text=name,
            color=COL_TEXT,
            font_size=FS_BODY,
            halign="left",
            valign="middle",
            size_hint_x=0.62,
            shorten=True,
            shorten_from="right",
        )
        nm.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        val = Label(
            text=format_rub(value_cents),
            color=COL_MUTED,
            font_size=FS_SMALL,
            bold=True,
            halign="right",
            valign="middle",
            size_hint_x=0.38,
        )
        val.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        top.add_widget(nm)
        top.add_widget(val)
        self.add_widget(top)
        denom = max_cents if max_cents > 0 else 1
        self.add_widget(BarTrack(value_cents / denom, bar_color))


class SectionCard(BoxLayout):
    """Titled block with optional subtitle and vertical body (report / list sections)."""

    def __init__(self, title: str, *, subtitle: str | None = None, **kwargs) -> None:
        super().__init__(orientation="vertical", spacing=10, padding=16, size_hint_y=None, **kwargs)
        with self.canvas.before:
            Color(*COL_SURFACE_ELEV)
            self._bg = RoundedRectangle(radius=[18, 18, 18, 18])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self._heading = Label(
            text=title,
            color=COL_TEXT,
            font_size=FS_BODY,
            bold=True,
            halign="left",
            valign="middle",
            size_hint_x=1,
            size_hint_y=None,
            height=28,
            max_lines=2,
        )
        self.add_widget(self._heading)
        self.bind(width=self._sync_heading_width)
        self._heading.bind(texture_size=self._reflow_height)

        self._subtitle: Label | None = None
        if subtitle:
            self._subtitle = Label(
                text=subtitle,
                color=COL_MUTED,
                font_size=FS_SMALL,
                halign="left",
                valign="top",
                size_hint_x=1,
                size_hint_y=None,
                height=44,
                max_lines=4,
            )
            self._subtitle.bind(size=self._sync_subtitle_size)
            self._subtitle.bind(texture_size=self._reflow_height)
            self.add_widget(self._subtitle)

        self.body = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None)
        self.body.bind(minimum_height=self._reflow_height)
        self.add_widget(self.body)
        Clock.schedule_once(lambda *_: (self._sync_heading_width(), self._reflow_height()), 0)

    def _pad_lr(self) -> tuple[float, float]:
        p = self.padding
        if isinstance(p, (int, float)):
            v = float(p)
            return v, v
        if len(p) == 4:
            return float(p[0]), float(p[2])
        return float(p[0]), float(p[0])

    def _sync_heading_width(self, *_args) -> None:
        pl, pr = self._pad_lr()
        w = max(1.0, self.width - pl - pr)
        line_h = FS_BODY * 1.45
        self._heading.text_size = (w, line_h * self._heading.max_lines + 2)

    def _sync_subtitle_size(self, inst: Label, size: tuple) -> None:
        inst.text_size = (max(1.0, size[0]), None)

    def _sync_bg(self, *_args) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _reflow_height(self, *_args) -> None:
        sp = self.spacing
        p = self.padding
        if isinstance(p, (int, float)):
            pt = pb = float(p)
        else:
            pt, pb = float(p[1]), float(p[3])
        head_h = max(28.0, float(self._heading.texture_size[1]))
        sub_block = 0.0
        if self._subtitle is not None:
            sub_block = max(44.0, float(self._subtitle.texture_size[1]) + 4.0) + sp
        self.height = pt + head_h + sp + sub_block + float(self.body.minimum_height) + pb


def empty_state_label(text: str) -> Label:
    lbl = Label(
        text=text,
        color=COL_MUTED,
        font_size=FS_BODY,
        halign="left",
        valign="top",
        size_hint_y=None,
        height=96,
    )
    lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width - 4, None)))
    return lbl


class GoalCard(BoxLayout):
    """Goal row as a compact card with progress bar."""

    def __init__(self, g, *, on_edit, on_delete, **kwargs) -> None:
        super().__init__(orientation="vertical", size_hint_y=None, height=108, padding=12, spacing=8, **kwargs)
        with self.canvas.before:
            Color(*COL_SURFACE_ELEV)
            self._bg = RoundedRectangle(radius=[14, 14, 14, 14])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        head = BoxLayout(orientation="horizontal", size_hint_y=None, height=30, spacing=8)
        title = Label(
            text=g.name,
            color=COL_TEXT,
            bold=True,
            font_size=FS_BODY,
            halign="left",
            valign="middle",
            size_hint_x=1,
        )
        title.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        head.add_widget(title)
        edit_btn = ui_button("Изменить", width=100)
        del_btn = ui_button("Удалить", width=100)
        edit_btn.bind(on_release=lambda *_a, gg=g: on_edit(gg))
        del_btn.bind(on_release=lambda *_a, gid=g.id: on_delete(gid))
        head.add_widget(edit_btn)
        head.add_widget(del_btn)
        self.add_widget(head)

        pct = round(g.progress_ratio * 100)
        sub = Label(
            text=f"{format_rub(g.current_cents)} из {format_rub(g.target_cents)}  ·  {pct}%",
            color=COL_MUTED,
            font_size=FS_SMALL,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=22,
        )
        sub.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        self.add_widget(sub)
        self.add_widget(BarTrack(min(1.0, g.progress_ratio), COL_ACCENT))

    def _sync_bg(self, *_args) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size


class ReminderRowCard(BoxLayout):
    """One reminder as a card with status accent and actions."""

    def __init__(self, r, *, now: datetime, on_done, on_delete, **kwargs) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None, height=86, padding=10, spacing=10, **kwargs)
        overdue = r.due_at < now
        stripe_rgb = COL_DANGER if overdue else COL_ACCENT
        stripe = BoxLayout(size_hint_x=None, width=4, size_hint_y=1)
        with stripe.canvas.before:
            Color(*stripe_rgb)
            sr = Rectangle()

        def _stripe(*_a: object) -> None:
            sr.pos = stripe.pos
            sr.size = stripe.size

        stripe.bind(pos=_stripe, size=_stripe)
        _stripe()

        with self.canvas.before:
            Color(*COL_SURFACE_ELEV)
            self._bg = RoundedRectangle(radius=[14, 14, 14, 14])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        mid = BoxLayout(orientation="vertical", spacing=4, size_hint_x=1)
        when = r.due_at.astimezone(UTC).strftime("%d.%m.%Y · %H:%M")
        status = "Просрочено" if overdue else "По плану"
        l1 = Label(
            text=f"{when}  ·  {status}",
            color=COL_MUTED,
            font_size=FS_SMALL,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=18,
        )
        l1.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        l2 = Label(
            text=r.name,
            color=COL_TEXT,
            font_size=FS_BODY,
            bold=True,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=24,
        )
        l2.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        amt = format_rub(r.amount_cents) if r.amount_cents is not None else "—"
        l3 = Label(
            text=f"Сумма: {amt}  ·  {recurrence_display(r.recurrence)}",
            color=COL_MUTED,
            font_size=FS_SMALL,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=18,
        )
        l3.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        mid.add_widget(l1)
        mid.add_widget(l2)
        mid.add_widget(l3)

        actions = BoxLayout(orientation="vertical", spacing=6, size_hint_x=None, width=108)
        done_btn = ui_button("Готово", width=104, accent=True)
        del_btn = ui_button("Удалить", width=104)
        done_btn.bind(on_release=lambda *_a, rid=r.id: on_done(rid))
        del_btn.bind(on_release=lambda *_a, rid=r.id: on_delete(rid))
        actions.add_widget(done_btn)
        actions.add_widget(del_btn)

        self.add_widget(stripe)
        self.add_widget(mid)
        self.add_widget(actions)

    def _sync_bg(self, *_args) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size


class IconButton(ButtonBehavior, BoxLayout):
    """Rounded pill / FAB: PNG icon (tinted for contrast) or vector ``glyph`` label."""

    def __init__(
        self,
        *,
        icon: str | None = None,
        glyph: str | None = None,
        text: str = "",
        width: int = 110,
        height: int = 44,
        accent: bool = False,
        circle: bool = False,
        icon_size: int = 28,
        **kwargs,
    ) -> None:
        if (icon is None) == (glyph is None):
            raise ValueError("IconButton: set exactly one of icon= or glyph=")
        super().__init__(
            orientation="horizontal",
            spacing=6,
            padding=(8, 6, 10, 6),
            size_hint_x=None,
            size_hint_y=None,
            width=width,
            height=height,
            **kwargs,
        )
        self._accent = accent
        self._base_color = COL_ACCENT if accent else COL_TOOLBAR_BTN
        self._circle = circle
        self._mark: Image | Label
        with self.canvas.before:
            self._bg_color = Color(*self._base_color)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self.bind(pos=self._update_bg, size=self._update_bg)
        self.bind(state=self._on_state_change)

        well = BoxLayout(
            orientation="vertical",
            size_hint_x=None,
            width=max(32, icon_size + 6),
            size_hint_y=1,
            padding=(0, 2, 2, 2),
        )
        if glyph is not None:
            self._mark = Label(
                text=glyph,
                font_size=icon_size + (10 if circle else 4),
                bold=True,
                color=(1, 1, 1, 1) if accent else ICON_TINT_DEFAULT,
                halign="center",
                valign="middle",
            )
            self._mark.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, inst.height)))
        else:
            if icon is None:
                raise ValueError("IconButton: icon path is required when glyph is not set")
            self._mark = Image(
                source=icon,
                color=(1, 1, 1, 1) if accent else ICON_TINT_DEFAULT,
                size_hint=(1, 1),
                allow_stretch=True,
                keep_ratio=True,
                mipmap=True,
            )
        well.add_widget(self._mark)
        self.add_widget(well)

        if text:
            line_h = FS_BODY * 1.38
            self._label = Label(
                text=text,
                color=COL_TEXT,
                halign="left",
                valign="middle",
                font_size=FS_BODY,
                size_hint_x=1,
                max_lines=1,
            )
            self._label.bind(
                size=lambda inst, _v: setattr(inst, "text_size", (max(1, inst.width - 2), line_h))
            )
            self.add_widget(self._label)
        else:
            self._label = None
            well.size_hint_x = 1

    def _update_bg(self, *_args) -> None:
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        if self._circle:
            r = 0.5 * min(self.width, self.height)
            self._bg_rect.radius = [r, r, r, r]
        else:
            self._bg_rect.radius = [min(18, self.height / 2)] * 4

    def _on_state_change(self, _inst, value: str) -> None:
        if value == "down":
            r, g, b, a = self._base_color
            self._bg_color.rgba = (min(r + 0.08, 1.0), min(g + 0.08, 1.0), min(b + 0.08, 1.0), a)
            if isinstance(self._mark, Image):
                self._mark.color = ICON_TINT_PRESSED if not self._accent else (0.92, 1, 1, 1)
            else:
                self._mark.color = (0.85, 1, 1, 1) if self._accent else ICON_TINT_PRESSED
        else:
            self._bg_color.rgba = self._base_color
            if isinstance(self._mark, Image):
                self._mark.color = (1, 1, 1, 1) if self._accent else ICON_TINT_DEFAULT
            else:
                self._mark.color = (1, 1, 1, 1) if self._accent else ICON_TINT_DEFAULT


class SummaryCard(BoxLayout):
    """Three-column month totals (income / expense / balance)."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            orientation="vertical",
            size_hint_y=None,
            height=118,
            spacing=8,
            padding=(14, 12),
            **kwargs,
        )
        with self.canvas.before:
            Color(*COL_SURFACE_ELEV)
            self._bg = RoundedRectangle(radius=[18, 18, 18, 18])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self._title = Label(
            text="",
            color=COL_MUTED,
            font_size=FS_SMALL,
            halign="left",
            valign="middle",
            size_hint_x=1,
            size_hint_y=None,
            height=34,
            max_lines=2,
        )
        self._title.bind(size=self._sync_title_size)
        self._title.bind(texture_size=self._reflow_summary_height)
        self.add_widget(self._title)

        row = BoxLayout(orientation="horizontal", spacing=12, size_hint_y=None, height=52)
        self._lbl_in = self._money_column("Доходы", COL_INCOME)
        self._lbl_out = self._money_column("Расходы", COL_EXPENSE)
        self._lbl_bal = self._money_column("Баланс", COL_TEXT)
        row.add_widget(self._lbl_in["box"])
        row.add_widget(self._lbl_out["box"])
        row.add_widget(self._lbl_bal["box"])
        self.add_widget(row)
        Clock.schedule_once(lambda *_: self._reflow_summary_height(), 0)

    def _sync_title_size(self, inst: Label, size: tuple) -> None:
        inst.text_size = (max(1.0, size[0]), FS_SMALL * 1.5 * 2 + 4)

    def _reflow_summary_height(self, *_args) -> None:
        th = max(34.0, float(self._title.texture_size[1]))
        self.height = 12 + th + 8 + 52 + 12

    @staticmethod
    def _money_column(title: str, value_color: tuple[float, float, float, float]) -> dict:
        box = BoxLayout(orientation="vertical", spacing=2)
        t = Label(
            text=title,
            color=COL_MUTED,
            font_size=FS_SMALL,
            halign="left",
            bold=True,
        )
        t.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        v = Label(
            text="—",
            color=value_color,
            font_size=FS_AMOUNT,
            halign="left",
            bold=True,
        )
        v.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        box.add_widget(t)
        box.add_widget(v)
        return {"box": box, "value": v}

    def _sync_bg(self, *_args) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size

    def set_header(self, text: str) -> None:
        self._title.text = text
        Clock.schedule_once(lambda *_: self._reflow_summary_height(), 0)

    def set_values(self, *, income_cents: int, expense_cents: int, balance_cents: int) -> None:
        self._lbl_in["value"].text = format_rub(income_cents)
        self._lbl_out["value"].text = format_rub(expense_cents)
        bal_color = COL_INCOME if balance_cents >= 0 else COL_EXPENSE
        self._lbl_bal["value"].text = format_rub(balance_cents)
        self._lbl_bal["value"].color = bal_color


class TransactionCard(BoxLayout):
    """One operation as a raised card with income/expense accent stripe."""

    def __init__(
        self,
        *,
        income: bool,
        when: str,
        kind_ui: str,
        note: str,
        category: str | None,
        amount_cents: int,
        tx_id: int | None = None,
        on_delete=None,
        **kwargs,
    ) -> None:
        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            height=96 if on_delete else 86,
            spacing=12,
            padding=(10, 10, 14, 10),
            **kwargs,
        )
        stripe_rgb = COL_INCOME if income else COL_EXPENSE
        stripe = BoxLayout(size_hint_x=None, width=4, size_hint_y=1)
        with stripe.canvas.before:
            Color(*stripe_rgb)
            sr = Rectangle()
        def _stripe_rect(*_a) -> None:
            sr.pos = stripe.pos
            sr.size = stripe.size

        stripe.bind(pos=_stripe_rect, size=_stripe_rect)
        _stripe_rect()

        with self.canvas.before:
            Color(*COL_SURFACE_ELEV)
            self._bg = RoundedRectangle(radius=[16, 16, 16, 16])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        mid = BoxLayout(orientation="vertical", spacing=2, size_hint_x=1)
        top = Label(
            text=when,
            color=COL_MUTED,
            font_size=FS_SMALL,
            halign="left",
            valign="middle",
        )
        top.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        title = note or "Без описания"
        main = Label(
            text=title,
            color=COL_TEXT,
            font_size=FS_BODY,
            halign="left",
            valign="middle",
            bold=True,
        )
        main.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        cat_line = f"{kind_ui} · {category}" if category else kind_ui
        sub = Label(
            text=cat_line,
            color=COL_MUTED,
            font_size=FS_SMALL,
            halign="left",
            valign="middle",
        )
        sub.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        mid.add_widget(top)
        mid.add_widget(main)
        mid.add_widget(sub)

        sign = "+" if income else "−"
        right = BoxLayout(
            orientation="vertical",
            size_hint_x=None,
            width=120,
            spacing=4,
        )
        amt = Label(
            text=f"{sign}{format_rub(amount_cents)}",
            color=stripe_rgb,
            font_size=FS_AMOUNT,
            bold=True,
            halign="right",
            valign="middle",
            size_hint_y=1,
        )
        amt.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        right.add_widget(amt)
        if on_delete is not None and tx_id is not None:
            del_btn = Button(
                text="Удалить",
                size_hint_y=None,
                height=24,
                background_normal="",
                background_color=(*COL_DANGER[:3], 0.75),
                color=COL_TEXT,
                font_size=FS_SMALL,
            )
            del_btn.bind(on_release=lambda *_a, tid=tx_id: on_delete(tid))
            right.add_widget(del_btn)

        self.add_widget(stripe)
        self.add_widget(mid)
        self.add_widget(right)

    def _sync_bg(self, *_args) -> None:
        m = 4
        self._bg.pos = (self.x + m, self.y + 3)
        self._bg.size = (self.width - 2 * m, self.height - 6)


def month_bounds_utc(dt: datetime) -> tuple[datetime, datetime]:
    start = datetime(dt.year, dt.month, 1, tzinfo=UTC)
    if dt.month == 12:
        next_month = datetime(dt.year + 1, 1, 1, tzinfo=UTC)
    else:
        next_month = datetime(dt.year, dt.month + 1, 1, tzinfo=UTC)
    inclusive_end = next_month - timedelta(seconds=1)
    return start, inclusive_end


@dataclass
class AppState:
    selected_type: str  # "all" | "income" | "expense"
    current_month: datetime = field(default_factory=lambda: datetime.now(UTC))


FILTER_UI_TO_KIND = {"Все": "all", "Расходы": "expense", "Доходы": "income"}
KIND_UI_TO_KIND = {"Расход": "expense", "Доход": "income"}
KIND_KIND_TO_UI = {v: k for k, v in KIND_UI_TO_KIND.items()}


def kind_to_ui(kind: str) -> str:
    return KIND_KIND_TO_UI.get(kind, kind)


class AddTransactionForm(BoxLayout):
    def __init__(self, on_submit, categories: list[tuple[int, str]], **kwargs):
        super().__init__(orientation="vertical", spacing=10, padding=12, **kwargs)
        self._on_submit = on_submit

        self.amount = ui_text_input("Сумма (например 199.90)")
        self.add_widget(self.amount)

        self.kind = ui_spinner(text="Расход", values=["Расход", "Доход"])
        self.add_widget(self.kind)

        self.category = ui_spinner(
            text="Без категории",
            values=["Без категории"] + [name for _, name in categories],
        )
        self._category_map = {name: cid for cid, name in categories}
        self.add_widget(self.category)

        self.note = ui_text_input("Заметка (опционально)")
        self.add_widget(self.note)

        self.error_label = ui_error_label()
        self.add_widget(self.error_label)

        submit = ui_button("Сохранить", accent=True)
        submit.bind(on_release=lambda *_: self._submit())
        self.add_widget(submit)

    def set_error(self, text: str) -> None:
        self.error_label.text = text

    def _submit(self) -> None:
        self._on_submit(
            amount_text=self.amount.text.strip(),
            kind=self.kind.text,
            category_name=self.category.text,
            note=self.note.text.strip() or None,
            occurred_at=datetime.now(UTC),
        )


class RootView(BoxLayout):
    def __init__(
        self,
        conn,
        repo: TransactionRepository,
        cat_repo: CategoryRepository,
        **kwargs,
    ):
        super().__init__(orientation="vertical", spacing=14, padding=(16, 12, 16, 14), **kwargs)
        self.conn = conn
        self.repo = repo
        self.cat_repo = cat_repo
        self.goal_repo = GoalRepository(conn)
        self.reminder_repo = ReminderRepository(conn)
        self.state = AppState(selected_type="all")

        title_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=8)
        prev_btn = Button(
            text="‹",
            size_hint_x=None,
            width=36,
            background_normal="",
            background_color=COL_SURFACE_ELEV,
            color=COL_TEXT,
            font_size=22,
        )
        prev_btn.bind(on_release=lambda *_: self._go_prev_month())
        title_row.add_widget(prev_btn)
        self.month_label = Label(
            text=month_title_ru(datetime.now(UTC)),
            font_size=FS_TITLE,
            bold=True,
            color=COL_TEXT,
            halign="center",
            valign="middle",
            size_hint_x=1,
        )
        self.month_label.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        title_row.add_widget(self.month_label)
        next_btn = Button(
            text="›",
            size_hint_x=None,
            width=36,
            background_normal="",
            background_color=COL_SURFACE_ELEV,
            color=COL_TEXT,
            font_size=22,
        )
        next_btn.bind(on_release=lambda *_: self._go_next_month())
        title_row.add_widget(next_btn)

        self.type_filter = ui_spinner(
            text="Все",
            values=["Все", "Расходы", "Доходы"],
            size_hint_x=None,
            width=152,
        )
        self.type_filter.bind(text=lambda *_: self.refresh())
        title_row.add_widget(self.type_filter)
        self.add_widget(title_row)

        actions = BoxLayout(orientation="horizontal", size_hint_y=None, height=50, spacing=10)
        self.period_label = ui_label("Период: текущий месяц (UTC)", height=50, muted=True)
        self.period_label.size_hint_x = 1
        actions.add_widget(self.period_label)

        reports_btn = IconButton(icon=ICON_REPORTS, text="Отчёты", width=142, height=44)
        reports_btn.bind(on_release=lambda *_: self.open_reports_popup())
        actions.add_widget(reports_btn)

        goals_btn = IconButton(icon=ICON_GOALS, text="Цели", width=108, height=44)
        goals_btn.bind(on_release=lambda *_: self.open_goals_popup())
        actions.add_widget(goals_btn)

        reminders_btn = IconButton(icon=ICON_REMINDERS, text="Напом.", width=132, height=44)
        reminders_btn.bind(on_release=lambda *_: self.open_reminders_popup())
        actions.add_widget(reminders_btn)

        add_btn = IconButton(
            glyph="+",
            width=58,
            height=58,
            accent=True,
            circle=True,
            icon_size=30,
        )
        add_btn.bind(on_release=lambda *_: self.open_add_popup())
        actions.add_widget(add_btn)
        self.add_widget(actions)

        self.summary = SummaryCard()
        self.summary.set_header("Сводка за месяц (с учётом фильтра)")
        self.summary.set_values(income_cents=0, expense_cents=0, balance_cents=0)
        self.add_widget(self.summary)

        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=10)
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll = ScrollView(
            bar_width=5,
            bar_color=(*COL_BORDER[:3], 0.45),
            bar_inactive_color=(*COL_BORDER[:3], 0.15),
            scroll_type=["bars", "content"],
        )
        scroll.add_widget(self.list_box)
        self.add_widget(scroll)

        Clock.schedule_once(lambda *_: self.refresh(), 0)

    def _go_prev_month(self) -> None:
        dt = self.state.current_month
        if dt.month == 1:
            self.state.current_month = datetime(dt.year - 1, 12, 1, tzinfo=UTC)
        else:
            self.state.current_month = datetime(dt.year, dt.month - 1, 1, tzinfo=UTC)
        self.refresh()

    def _go_next_month(self) -> None:
        dt = self.state.current_month
        if dt.month == 12:
            self.state.current_month = datetime(dt.year + 1, 1, 1, tzinfo=UTC)
        else:
            self.state.current_month = datetime(dt.year, dt.month + 1, 1, tzinfo=UTC)
        self.refresh()

    def _load_transactions_for_current_month(self) -> list:
        start, end = month_bounds_utc(self.state.current_month)
        tx = self.repo.list_between(start=start, end=end)

        kind_ui = self.type_filter.text
        kind = FILTER_UI_TO_KIND.get(kind_ui, "all")
        if kind != "all":
            tx = [t for t in tx if str(t.transaction.type) == kind]
        return tx

    def refresh(self) -> None:
        self.month_label.text = month_title_ru(self.state.current_month)
        tx = self._load_transactions_for_current_month()
        start, end = month_bounds_utc(self.state.current_month)
        totals = totals_for_period([t.transaction for t in tx], start=start, end=end)
        self.summary.set_values(
            income_cents=totals.income_cents,
            expense_cents=totals.expense_cents,
            balance_cents=totals.balance_cents,
        )

        self.list_box.clear_widgets()
        if not tx:
            empty = BoxLayout(orientation="vertical", size_hint_y=None, height=120, padding=(8, 24))
            msg = Label(
                text="Пока нет операций за этот месяц.\nНажмите «+», чтобы добавить доход или расход.",
                color=COL_MUTED,
                font_size=FS_BODY,
                halign="center",
                valign="middle",
            )
            msg.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
            empty.add_widget(msg)
            self.list_box.add_widget(empty)
            return

        cats = {c.id: c.name for c in self.cat_repo.list_all()}

        def delete_transaction(tx_id: int) -> None:
            with transaction(self.conn):
                self.repo.delete(tx_id=tx_id)
            self.refresh()

        for item in tx:
            t = item.transaction
            when = t.occurred_at.astimezone(UTC).strftime("%d.%m.%Y · %H:%M")
            income = t.type == TransactionType.INCOME
            cat = cats.get(t.category_id) if t.category_id is not None else None
            self.list_box.add_widget(
                TransactionCard(
                    income=income,
                    when=when,
                    kind_ui=kind_to_ui(str(t.type)),
                    note=(t.note or "").strip(),
                    category=cat,
                    amount_cents=t.amount_cents,
                    tx_id=item.id,
                    on_delete=delete_transaction,
                )
            )

    def open_add_popup(self) -> None:
        cats = self.cat_repo.list_all()
        cat_pairs = [(c.id, c.name) for c in cats]

        def on_submit(*, amount_text, kind, category_name, note, occurred_at):
            try:
                amount_cents = parse_money(amount_text)
                if amount_cents <= 0:
                    raise ValueError("Сумма должна быть больше 0")
            except ValueError as exc:
                form.set_error(str(exc))
                return

            category_id = None
            if category_name != "Без категории":
                category_id = form._category_map.get(category_name)

            try:
                kind_internal = KIND_UI_TO_KIND.get(kind, kind)
                tx = Transaction(
                    type=TransactionType(kind_internal),
                    amount_cents=amount_cents,
                    occurred_at=occurred_at,
                    category_id=category_id,
                    note=note,
                )
                with transaction(self.conn):
                    self.repo.create(tx)
            except Exception as exc:
                form.set_error(f"Ошибка сохранения: {exc}")
                return

            popup.dismiss()
            self.refresh()

        form = AddTransactionForm(on_submit=on_submit, categories=cat_pairs)
        sheet = ModalSheet(size_hint=(1, 1))
        sheet.add_widget(form)
        popup = Popup(title="Добавить транзакцию", content=sheet, size_hint=(0.9, 0.82))
        style_popup(popup)
        popup.open()

    def open_reports_popup(self) -> None:
        start, end = month_bounds_utc(datetime.now(UTC))
        stored = self.repo.list_between(start=start, end=end)
        tx = [s.transaction for s in stored]

        cats = {c.id: c.name for c in self.cat_repo.list_all()}
        cats[None] = "Без категории"

        totals = totals_for_period(tx, start=start, end=end)
        by_cat = expense_by_category(tx, start=start, end=end)
        by_day = expense_by_day(tx, start=start, end=end)

        shell = ModalSheet(size_hint=(1, 1))
        scroll = ScrollView(
            size_hint=(1, 1),
            bar_width=5,
            bar_color=(*COL_BORDER[:3], 0.45),
            bar_inactive_color=(*COL_BORDER[:3], 0.15),
            scroll_type=["bars", "content"],
        )
        inner = BoxLayout(orientation="vertical", spacing=16, size_hint_y=None, padding=(0, 4))
        inner.bind(minimum_height=inner.setter("height"))

        summary = SummaryCard()
        summary.set_header(
            f"{start.date().strftime('%d.%m.%Y')} — {end.date().strftime('%d.%m.%Y')} · UTC"
        )
        summary.set_values(
            income_cents=totals.income_cents,
            expense_cents=totals.expense_cents,
            balance_cents=totals.balance_cents,
        )
        inner.add_widget(summary)

        cat_items = sorted(
            ((cats.get(cid, str(cid)), v) for cid, v in by_cat.items()),
            key=lambda x: x[1],
            reverse=True,
        )
        max_cat = max((v for _, v in cat_items), default=0)
        cat_section = SectionCard(
            "Расходы по категориям",
            subtitle="Сравнение долей расходов. Если в месяце только доходы — блок будет пустым.",
        )
        if not cat_items or max_cat <= 0:
            cat_section.body.add_widget(
                empty_state_label(
                    "За этот месяц нет расходов, поэтому разбивки по категориям пока нет. "
                    "Добавьте хотя бы одну операцию «Расход» — здесь появятся цветные столбики."
                )
            )
        else:
            for name, cents in cat_items:
                if cents <= 0:
                    continue
                cat_section.body.add_widget(
                    ReportBarRow(name, cents, max_cents=max_cat, bar_color=palette_color(name))
                )
        inner.add_widget(cat_section)

        day_items = sorted(by_day.items(), key=lambda x: x[0])
        max_day = max((v for _, v in day_items), default=0)
        day_section = SectionCard(
            "Расходы по дням",
            subtitle="Динамика по календарным дням (только расходы).",
        )
        if not day_items or max_day <= 0:
            day_section.body.add_widget(
                empty_state_label(
                    "Нет расходов по дням за выбранный месяц — график появится после расходных операций."
                )
            )
        else:
            day_bar_color = (0.52, 0.62, 0.86, 1)
            for d, cents in day_items:
                if cents <= 0:
                    continue
                label = d.strftime("%d.%m")
                day_section.body.add_widget(
                    ReportBarRow(label, cents, max_cents=max_day, bar_color=day_bar_color)
                )
        inner.add_widget(day_section)

        scroll.add_widget(inner)
        shell.add_widget(scroll)

        popup = Popup(title="Отчёты за месяц", content=shell, size_hint=(0.94, 0.9))
        style_popup(popup)
        popup.open()

    def open_goals_popup(self) -> None:
        shell = ModalSheet(size_hint=(1, 1))
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=48, spacing=10)
        title = Label(
            text="Финансовые цели",
            color=COL_TEXT,
            font_size=FS_TITLE - 2,
            bold=True,
            halign="left",
            valign="middle",
            size_hint_x=1,
        )
        title.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        header.add_widget(title)
        add_btn = ui_button("Новая цель", width=132, accent=True)
        header.add_widget(add_btn)
        shell.add_widget(header)

        list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=10)
        list_box.bind(minimum_height=list_box.setter("height"))

        def refresh_list() -> None:
            list_box.clear_widgets()
            current = self.goal_repo.list_all()
            if not current:
                list_box.add_widget(
                    empty_state_label(
                        "Целей пока нет. Нажмите «Новая цель», задайте сумму и следите за полосой прогресса."
                    )
                )
                return
            for g in current:
                list_box.add_widget(
                    GoalCard(
                        g,
                        on_edit=lambda goal: open_goal_editor(existing=goal),
                        on_delete=delete_goal,
                    )
                )

        def delete_goal(goal_id: int) -> None:
            with transaction(self.conn):
                self.goal_repo.delete(goal_id=goal_id)
            refresh_list()

        def open_goal_editor(*, existing=None) -> None:
            form = BoxLayout(orientation="vertical", spacing=10, padding=(2, 4))
            name_in = ui_text_input("Название")
            target_in = ui_text_input("Цель (сумма)")
            current_in = ui_text_input("Текущий прогресс (0 если пусто)")
            deadline_in = ui_text_input("Дедлайн YYYY-MM-DD (необязательно)")
            note_in = ui_text_input("Заметка (необязательно)")
            err = ui_error_label()

            if existing is not None:
                name_in.text = existing.name
                target_in.text = f"{existing.target_cents/100:.2f}"
                current_in.text = f"{existing.current_cents/100:.2f}"
                deadline_in.text = existing.deadline_at.date().isoformat() if existing.deadline_at else ""
                note_in.text = existing.note or ""

            form.add_widget(name_in)
            form.add_widget(target_in)
            form.add_widget(current_in)
            form.add_widget(deadline_in)
            form.add_widget(note_in)
            form.add_widget(err)

            def on_save(*_a) -> None:
                try:
                    name = name_in.text.strip()
                    if not name:
                        raise ValueError("Введите название")
                    target_cents = parse_money(target_in.text)
                    current_cents = parse_money(current_in.text or "0")
                    if target_cents <= 0:
                        raise ValueError("Цель должна быть > 0")
                    if current_cents < 0:
                        raise ValueError("Прогресс должен быть >= 0")
                    deadline_text = deadline_in.text.strip()
                    deadline_dt = None
                    if deadline_text:
                        d = date.fromisoformat(deadline_text)
                        deadline_dt = datetime(d.year, d.month, d.day, 0, 0, tzinfo=UTC)
                    note = note_in.text.strip() or None

                    with transaction(self.conn):
                        if existing is None:
                            self.goal_repo.create(
                                name=name,
                                target_cents=target_cents,
                                current_cents=current_cents,
                                deadline_at=deadline_dt,
                                note=note,
                            )
                        else:
                            self.goal_repo.update(
                                goal_id=existing.id,
                                name=name,
                                target_cents=target_cents,
                                current_cents=current_cents,
                                deadline_at=deadline_dt,
                                note=note,
                            )
                    editor.dismiss()
                    refresh_list()
                except Exception as exc:
                    err.text = str(exc)

            save_btn = ui_button("Сохранить", accent=True)
            save_btn.bind(on_release=on_save)
            form.add_widget(save_btn)

            editor_sheet = ModalSheet(size_hint=(1, 1))
            editor_sheet.add_widget(form)
            title = "Новая цель" if existing is None else "Редактировать цель"
            editor = Popup(title=title, content=editor_sheet, size_hint=(0.9, 0.88))
            style_popup(editor)
            editor.open()

        add_btn.bind(on_release=lambda *_: open_goal_editor(existing=None))
        refresh_list()

        scroll = ScrollView(
            size_hint=(1, 1),
            bar_width=5,
            bar_color=(*COL_BORDER[:3], 0.45),
            bar_inactive_color=(*COL_BORDER[:3], 0.15),
            scroll_type=["bars", "content"],
        )
        scroll.add_widget(list_box)
        shell.add_widget(scroll)

        popup = Popup(title="Цели", content=shell, size_hint=(0.94, 0.9))
        style_popup(popup)
        popup.open()

    def open_reminders_popup(self) -> None:
        shell = ModalSheet(size_hint=(1, 1))
        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=48, spacing=10)
        title = Label(
            text="Напоминания о платежах",
            color=COL_TEXT,
            font_size=FS_TITLE - 2,
            bold=True,
            halign="left",
            valign="middle",
            size_hint_x=1,
        )
        title.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        header.add_widget(title)
        add_btn = ui_button("Новое", width=110, accent=True)
        header.add_widget(add_btn)
        shell.add_widget(header)

        list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=10)
        list_box.bind(minimum_height=list_box.setter("height"))

        def refresh_list() -> None:
            list_box.clear_widgets()
            items = self.reminder_repo.list_due_sorted()
            if not items:
                list_box.add_widget(
                    empty_state_label(
                        "Список пуст. Добавьте дату платежа и при необходимости повтор — приложение "
                        "подсветит просроченные записи."
                    )
                )
                return
            now = datetime.now(UTC)
            for r in items:
                list_box.add_widget(
                    ReminderRowCard(
                        r,
                        now=now,
                        on_done=mark_done,
                        on_delete=delete_reminder,
                    )
                )

        def mark_done(reminder_id: int) -> None:
            with transaction(self.conn):
                self.reminder_repo.mark_done(reminder_id=reminder_id)
            refresh_list()

        def delete_reminder(reminder_id: int) -> None:
            with transaction(self.conn):
                self.reminder_repo.delete(reminder_id=reminder_id)
            refresh_list()

        def open_editor() -> None:
            form = BoxLayout(orientation="vertical", spacing=10, padding=(2, 4))
            name_in = ui_text_input("Название")
            due_in = ui_text_input("Дата и время: YYYY-MM-DD HH:MM")
            recurrence_in = ui_spinner(text=RECURRENCE_LABELS[0], values=list(RECURRENCE_LABELS))
            amount_in = ui_text_input("Сумма (необязательно)")
            note_in = ui_text_input("Заметка (необязательно)")
            err = ui_error_label()

            form.add_widget(name_in)
            form.add_widget(due_in)
            form.add_widget(recurrence_in)
            form.add_widget(amount_in)
            form.add_widget(note_in)
            form.add_widget(err)

            def on_save(*_a) -> None:
                try:
                    name = name_in.text.strip()
                    if not name:
                        raise ValueError("Введите название")
                    due_text = due_in.text.strip()
                    if not due_text:
                        raise ValueError("Введите дату/время")
                    due_dt = datetime.strptime(due_text, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
                    recurrence = RECURRENCE_UI_TO_VALUE.get(recurrence_in.text, "none")
                    amount_text = amount_in.text.strip()
                    amount_cents = parse_money(amount_text) if amount_text else None
                    note = note_in.text.strip() or None

                    with transaction(self.conn):
                        self.reminder_repo.create(
                            name=name,
                            due_at=due_dt,
                            recurrence=recurrence,
                            amount_cents=amount_cents,
                            note=note,
                        )
                    editor.dismiss()
                    refresh_list()
                except Exception as exc:
                    err.text = str(exc)

            save_btn = ui_button("Сохранить", accent=True)
            save_btn.bind(on_release=on_save)
            form.add_widget(save_btn)

            editor_sheet = ModalSheet(size_hint=(1, 1))
            editor_sheet.add_widget(form)
            editor = Popup(title="Новое напоминание", content=editor_sheet, size_hint=(0.9, 0.88))
            style_popup(editor)
            editor.open()

        add_btn.bind(on_release=lambda *_: open_editor())
        refresh_list()

        scroll = ScrollView(
            size_hint=(1, 1),
            bar_width=5,
            bar_color=(*COL_BORDER[:3], 0.45),
            bar_inactive_color=(*COL_BORDER[:3], 0.15),
            scroll_type=["bars", "content"],
        )
        scroll.add_widget(list_box)
        shell.add_widget(scroll)

        popup = Popup(title="Напоминания", content=shell, size_hint=(0.94, 0.9))
        style_popup(popup)
        popup.open()


class PersonalFinanceApp(App):
    title = "Личные финансы"

    def build(self):
        Window.clearcolor = COL_BG
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _cleanup_orphaned_plaintext_dbs()
        # Build a placeholder root; we will prompt for a password and then
        # initialize the actual app UI once DB is decrypted.
        self._passphrase: str | None = None
        self._conn = None
        self._runtime_db_path: Path | None = None

        root = BoxLayout(orientation="vertical", padding=12, spacing=8)
        root.add_widget(Label(text="Загрузка…", size_hint_y=None, height=40))

        Clock.schedule_once(lambda *_: self._prompt_password_and_unlock(root), 0)
        return root

    def _prompt_password_and_unlock(self, root: BoxLayout) -> None:
        first_run = not ENCRYPTED_DB_PATH.exists()

        content = BoxLayout(orientation="vertical", spacing=10, padding=12)
        err = ui_error_label()

        if first_run:
            content.add_widget(
                ui_label(
                    "Первый запуск: придумайте пароль для шифрования локальной БД.\n"
                    "Пароль не восстанавливается — сохраните его.",
                    height=56,
                    muted=True,
                )
            )
            pwd = ui_text_input("Новый пароль", password=True)
            pwd2 = ui_text_input("Повторите пароль", password=True)
            content.add_widget(pwd)
            content.add_widget(pwd2)
        else:
            content.add_widget(ui_label("Введите пароль для шифрования локальной БД.", height=40, muted=True))
            pwd = ui_text_input("Пароль для БД", password=True)
            pwd2 = None
            content.add_widget(pwd)

        content.add_widget(err)

        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=40, spacing=8)
        unlock_btn = ui_button("Открыть", accent=True)
        exit_btn = ui_button("Выход")
        btn_row.add_widget(unlock_btn)
        btn_row.add_widget(exit_btn)
        content.add_widget(btn_row)

        sheet = ModalSheet(size_hint=(1, 1))
        sheet.add_widget(content)
        popup = Popup(
            title="Создание пароля" if first_run else "Разблокировка БД",
            content=sheet,
            size_hint=(0.9, 0.62 if first_run else 0.52),
            auto_dismiss=False,
        )
        style_popup(popup)

        def do_exit(*_a) -> None:
            popup.dismiss()
            self.stop()

        def do_unlock(*_a) -> None:
            try:
                passphrase = pwd.text
                if encryption_enabled():
                    if not passphrase:
                        raise ValueError("Введите пароль")
                    if first_run:
                        if pwd2 is None:
                            raise ValueError("Повторите пароль")
                        if pwd2.text != passphrase:
                            raise ValueError("Пароли не совпадают")
                        if len(passphrase) < 4:
                            raise ValueError("Слишком короткий пароль (минимум 4 символа)")

                    # Keep plaintext DB in a unique temp location.
                    runtime_db = _new_temp_plaintext_db_path()
                    self._runtime_db_path = runtime_db

                    # If encrypted DB exists -> decrypt into temp plaintext path.
                    if ENCRYPTED_DB_PATH.exists():
                        decrypt_file_to_path(
                            encrypted_path=ENCRYPTED_DB_PATH,
                            passphrase=passphrase,
                            out_path=runtime_db,
                        )
                else:
                    # Android / reproducible build mode: use plaintext DB only.
                    passphrase = ""
                    runtime_db = PLAINTEXT_DB_PATH
                    self._runtime_db_path = runtime_db

                conn = connect(runtime_db)
                init_schema(conn)
                cat_repo = CategoryRepository(conn)
                tx_repo = TransactionRepository(conn)
                with transaction(conn):
                    cat_repo.ensure_defaults()

                self._passphrase = passphrase
                self._conn = conn

                root.clear_widgets()
                root.add_widget(RootView(conn, tx_repo, cat_repo))
                popup.dismiss()
            except InvalidPasswordError:
                err.text = "Неверный пароль (или файл БД повреждён)."
                # Cleanup temp plaintext on failure.
                try:
                    if self._runtime_db_path and self._runtime_db_path != PLAINTEXT_DB_PATH:
                        self._runtime_db_path.unlink(missing_ok=True)
                except Exception:
                    pass
            except Exception as exc:
                err.text = str(exc)
                try:
                    if self._runtime_db_path and self._runtime_db_path != PLAINTEXT_DB_PATH:
                        self._runtime_db_path.unlink(missing_ok=True)
                except Exception:
                    pass

        unlock_btn.bind(on_release=do_unlock)
        exit_btn.bind(on_release=do_exit)
        popup.open()

    def on_stop(self):
        conn = getattr(self, "_conn", None)
        passphrase = getattr(self, "_passphrase", None)
        runtime_db = getattr(self, "_runtime_db_path", None) or PLAINTEXT_DB_PATH
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        # Best-effort: seal plaintext DB into encrypted file and remove plaintext.
        if encryption_enabled() and passphrase and runtime_db.exists():
            try:
                encrypt_file_to_path(
                    plaintext_path=runtime_db,
                    passphrase=passphrase,
                    out_path=ENCRYPTED_DB_PATH,
                )
                runtime_db.unlink(missing_ok=True)
            except Exception:
                # Do not crash app shutdown.
                pass


if __name__ == "__main__":
    PersonalFinanceApp().run()
