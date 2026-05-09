from __future__ import annotations

from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from src.ui.theme import (
    COL_ACCENT,
    COL_ACCENT_DIM,
    COL_BORDER,
    COL_DANGER,
    COL_MUTED,
    COL_SURFACE,
    COL_SURFACE_ELEV,
    COL_TEXT,
    COL_TOOLBAR_BTN,
    FS_BODY,
    FS_SMALL,
)


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


def empty_state_label(text: str) -> Label:
    lbl = Label(text=text, color=COL_MUTED, font_size=FS_BODY, halign="left", valign="top",
                size_hint_y=None, height=96)
    lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width - 4, None)))
    return lbl
