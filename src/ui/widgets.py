from __future__ import annotations

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.graphics.vertex_instructions import RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from src.ui.formatting import format_rub
from src.ui.theme import (
    COL_BG,
    COL_BORDER,
    COL_MODAL_FACE,
    COL_MUTED,
    COL_SURFACE_ELEV,
    COL_TEXT,
    FS_BODY,
    FS_SMALL,
)


class ModalSheet(BoxLayout):
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
    def __init__(self, name: str, value_cents: int, *, max_cents: int,
                 bar_color: tuple[float, float, float, float], **kwargs) -> None:
        super().__init__(orientation="vertical", spacing=6, size_hint_y=None, height=52, **kwargs)
        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=22, spacing=8)
        nm = Label(text=name, color=COL_TEXT, font_size=FS_BODY, halign="left", valign="middle",
                   size_hint_x=0.62, shorten=True, shorten_from="right")
        nm.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        val = Label(text=format_rub(value_cents), color=COL_MUTED, font_size=FS_SMALL, bold=True,
                    halign="right", valign="middle", size_hint_x=0.38)
        val.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        top.add_widget(nm)
        top.add_widget(val)
        self.add_widget(top)
        denom = max_cents if max_cents > 0 else 1
        self.add_widget(BarTrack(value_cents / denom, bar_color))


class SectionCard(BoxLayout):
    def __init__(self, title: str, *, subtitle: str | None = None, **kwargs) -> None:
        super().__init__(orientation="vertical", spacing=10, padding=16, size_hint_y=None, **kwargs)
        with self.canvas.before:
            Color(*COL_SURFACE_ELEV)
            self._bg = RoundedRectangle(radius=[18, 18, 18, 18])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self._heading = Label(text=title, color=COL_TEXT, font_size=FS_BODY, bold=True,
                              halign="left", valign="middle", size_hint_x=1,
                              size_hint_y=None, height=28, max_lines=2)
        self.add_widget(self._heading)
        self.bind(width=self._sync_heading_width)
        self._heading.bind(texture_size=self._reflow_height)

        self._subtitle: Label | None = None
        if subtitle:
            self._subtitle = Label(text=subtitle, color=COL_MUTED, font_size=FS_SMALL,
                                   halign="left", valign="top", size_hint_x=1,
                                   size_hint_y=None, height=44, max_lines=4)
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
