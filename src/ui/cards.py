from __future__ import annotations

from datetime import UTC, datetime

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.graphics.vertex_instructions import RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from src.ui.factories import ui_button
from src.ui.formatting import _ops_word, format_rub, recurrence_display
from src.ui.theme import (
    COL_ACCENT,
    COL_BORDER,
    COL_DANGER,
    COL_EXPENSE,
    COL_INCOME,
    COL_MUTED,
    COL_SIDEBAR,
    COL_SURFACE_ELEV,
    COL_TEXT,
    COL_TOOLBAR_BTN,
    FS_AMOUNT,
    FS_BODY,
    FS_SMALL,
    IC_BELL,
    IC_CHART,
    IC_EXIT,
    IC_FLAG,
    IC_HOME,
    ICON_TINT_DEFAULT,
    ICON_TINT_PRESSED,
)
from src.ui.widgets import BarTrack


class GoalCard(BoxLayout):
    def __init__(self, g, *, on_edit, on_delete, **kwargs) -> None:
        super().__init__(orientation="vertical", size_hint_y=None, height=108,
                         padding=12, spacing=8, **kwargs)
        with self.canvas.before:
            Color(*COL_SURFACE_ELEV)
            self._bg = RoundedRectangle(radius=[14, 14, 14, 14])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        head = BoxLayout(orientation="horizontal", size_hint_y=None, height=30, spacing=8)
        title = Label(text=g.name, color=COL_TEXT, bold=True, font_size=FS_BODY,
                      halign="left", valign="middle", size_hint_x=1)
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
            color=COL_MUTED, font_size=FS_SMALL, halign="left", valign="middle",
            size_hint_y=None, height=22)
        sub.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        self.add_widget(sub)
        self.add_widget(BarTrack(min(1.0, g.progress_ratio), COL_ACCENT))

    def _sync_bg(self, *_args) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size


class ReminderRowCard(BoxLayout):
    def __init__(self, r, *, now: datetime, on_done, on_delete, **kwargs) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None, height=86,
                         padding=10, spacing=10, **kwargs)
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
        l1 = Label(text=f"{when}  ·  {status}", color=COL_MUTED, font_size=FS_SMALL,
                   halign="left", valign="middle", size_hint_y=None, height=18)
        l1.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        l2 = Label(text=r.name, color=COL_TEXT, font_size=FS_BODY, bold=True,
                   halign="left", valign="middle", size_hint_y=None, height=24)
        l2.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        amt = format_rub(r.amount_cents) if r.amount_cents is not None else "—"
        l3 = Label(text=f"Сумма: {amt}  ·  {recurrence_display(r.recurrence)}",
                   color=COL_MUTED, font_size=FS_SMALL, halign="left", valign="middle",
                   size_hint_y=None, height=18)
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
    def __init__(self, *, icon: str | None = None, glyph: str | None = None,
                 text: str = "", width: int = 110, height: int = 44,
                 accent: bool = False, circle: bool = False, icon_size: int = 28,
                 glyph_font: str = "",
                 **kwargs) -> None:
        if (icon is None) == (glyph is None):
            raise ValueError("IconButton: set exactly one of icon= or glyph=")
        super().__init__(orientation="horizontal", spacing=6, padding=(8, 6, 10, 6),
                         size_hint_x=None, size_hint_y=None, width=width, height=height, **kwargs)
        self._accent = accent
        self._base_color = COL_ACCENT if accent else COL_TOOLBAR_BTN
        self._circle = circle
        self._mark: Image | Label
        with self.canvas.before:
            self._bg_color = Color(*self._base_color)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self.bind(pos=self._update_bg, size=self._update_bg)
        self.bind(state=self._on_state_change)

        well = BoxLayout(orientation="vertical", size_hint_x=None,
                         width=max(32, icon_size + 6), size_hint_y=1, padding=(0, 2, 2, 2))
        if glyph is not None:
            lbl_kwargs: dict = dict(
                text=glyph,
                font_size=icon_size + (10 if circle else 4),
                bold=not glyph_font,
                color=(1, 1, 1, 1) if accent else ICON_TINT_DEFAULT,
                halign="center", valign="middle",
            )
            if glyph_font:
                lbl_kwargs["font_name"] = glyph_font
            self._mark = Label(**lbl_kwargs)
            self._mark.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, inst.height)))
        else:
            if icon is None:
                raise ValueError("IconButton: icon path is required when glyph is not set")
            self._mark = Image(source=icon, color=(1, 1, 1, 1) if accent else ICON_TINT_DEFAULT,
                               size_hint=(1, 1), allow_stretch=True, keep_ratio=True, mipmap=True)
        well.add_widget(self._mark)
        self.add_widget(well)

        if text:
            line_h = FS_BODY * 1.38
            self._label = Label(text=text, color=COL_TEXT, halign="left", valign="middle",
                                font_size=FS_BODY, size_hint_x=1, max_lines=1)
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
    def __init__(self, **kwargs) -> None:
        super().__init__(orientation="vertical", size_hint_y=None, height=118,
                         spacing=8, padding=(14, 12), **kwargs)
        with self.canvas.before:
            Color(*COL_SURFACE_ELEV)
            self._bg = RoundedRectangle(radius=[18, 18, 18, 18])
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self._title = Label(text="", color=COL_MUTED, font_size=FS_SMALL, halign="left",
                            valign="middle", size_hint_x=1, size_hint_y=None, height=34, max_lines=2)
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
        t = Label(text=title, color=COL_MUTED, font_size=FS_SMALL, halign="left", bold=True)
        t.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        v = Label(text="—", color=value_color, font_size=FS_AMOUNT, halign="left", bold=True)
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


class StatCard(BoxLayout):
    def __init__(self, *, title: str, glyph: str, amount_color: tuple, **kwargs) -> None:
        super().__init__(orientation="vertical", size_hint_y=None, height=110,
                         padding=(14, 12, 14, 12), spacing=6, **kwargs)
        with self.canvas.before:
            Color(*COL_SURFACE_ELEV)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[14] * 4)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        r, g, b, _a = amount_color
        top_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=28, spacing=10)

        icon_lbl = Label(
            text=glyph, font_size=15, font_name="MaterialIcons",
            color=amount_color,
            size_hint=(None, None), size=(28, 28),
            halign="center", valign="middle",
        )
        icon_lbl.text_size = icon_lbl.size

        with icon_lbl.canvas.before:
            Color(r * 0.22, g * 0.22, b * 0.22, 1)
            self._pill = RoundedRectangle(
                pos=icon_lbl.pos, size=icon_lbl.size, radius=[8] * 4,
            )

        def _sync_pill(_inst, _val) -> None:
            self._pill.pos = icon_lbl.pos
            self._pill.size = icon_lbl.size

        icon_lbl.bind(pos=_sync_pill, size=_sync_pill)
        top_row.add_widget(icon_lbl)

        title_lbl = Label(
            text=title, color=COL_MUTED, font_size=FS_SMALL,
            halign="left", valign="middle", size_hint_x=1,
        )
        title_lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        top_row.add_widget(title_lbl)
        self.add_widget(top_row)

        self._amount_lbl = Label(
            text="0.00", color=amount_color, font_size=22, bold=True,
            halign="left", valign="middle",
            size_hint_y=None, height=28,
        )
        self._amount_lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        self.add_widget(self._amount_lbl)

        self._count_lbl = Label(
            text="0 операций", color=COL_MUTED, font_size=FS_SMALL,
            halign="left", valign="middle",
            size_hint_y=None, height=18,
        )
        self._count_lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        self.add_widget(self._count_lbl)

    def _sync_bg(self, *_args) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size

    def update(self, *, amount_cents: int, count: int,
               color_override: tuple | None = None) -> None:
        self._amount_lbl.text = format_rub(amount_cents)
        if color_override is not None:
            self._amount_lbl.color = color_override
        self._count_lbl.text = f"{count} {_ops_word(count)}"


class NavItem(ButtonBehavior, BoxLayout):
    def __init__(self, *, glyph: str, text: str, active: bool = False, **kwargs) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None, height=46,
                         padding=(0, 0, 8, 0), spacing=8, **kwargs)

        self._stripe = Widget(size_hint_x=None, width=3)
        with self._stripe.canvas:
            self._stripe_clr = Color(*(COL_ACCENT if active else (0, 0, 0, 0)))
            self._stripe_rect = Rectangle()
        self._stripe.bind(pos=self._sync_stripe, size=self._sync_stripe)
        self.add_widget(self._stripe)

        with self.canvas.before:
            self._bg_clr = Color(*((0.14, 0.17, 0.22, 1) if active else (0, 0, 0, 0)))
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

        self._icon = Label(text=glyph, font_size=18, font_name="MaterialIcons",
                           color=COL_ACCENT if active else COL_MUTED,
                           size_hint_x=None, width=26, halign="center", valign="middle")
        self._icon.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, inst.height)))
        self.add_widget(self._icon)

        self._lbl = Label(text=text, font_size=FS_BODY,
                          color=COL_TEXT if active else COL_MUTED,
                          halign="left", valign="middle", size_hint_x=1)
        self._lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, inst.height)))
        self.add_widget(self._lbl)

    def _sync_bg(self, *_) -> None:
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _sync_stripe(self, *_) -> None:
        self._stripe_rect.pos = self._stripe.pos
        self._stripe_rect.size = self._stripe.size

    def set_active(self, active: bool) -> None:
        if active:
            self._bg_clr.rgba = (0.14, 0.17, 0.22, 1)
            self._stripe_clr.rgba = COL_ACCENT
            self._icon.color = COL_ACCENT
            self._lbl.color = COL_TEXT
        else:
            self._bg_clr.rgba = (0, 0, 0, 0)
            self._stripe_clr.rgba = (0, 0, 0, 0)
            self._icon.color = COL_MUTED
            self._lbl.color = COL_MUTED


class Sidebar(BoxLayout):
    def __init__(self, *, on_overview, on_reports,
                 on_goals, on_reminders, on_exit, **kwargs) -> None:
        super().__init__(orientation="vertical", size_hint_x=None, width=158,
                         padding=(0, 10, 0, 10), spacing=0, **kwargs)
        with self.canvas.before:
            Color(*COL_SIDEBAR)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos),
                  size=lambda *_: setattr(self._bg, "size", self.size))

        logo = Label(text="[b]Финансы[/b]", markup=True, color=COL_TEXT, font_size=16,
                     size_hint_y=None, height=52, halign="left", valign="middle")
        logo.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width - 16, inst.height)))
        self.add_widget(logo)
        self._add_sep()

        self._nav_items: list[NavItem] = []

        def _nav(glyph: str, text: str, cb, active: bool = False) -> NavItem:
            item = NavItem(glyph=glyph, text=text, active=active)
            item.bind(on_release=lambda *_: (self._activate(item), cb()))
            self._nav_items.append(item)
            self.add_widget(item)
            return item

        _nav(IC_HOME,  "Обзор",       on_overview, active=True)
        _nav(IC_CHART, "Отчёты",      on_reports)
        _nav(IC_FLAG,  "Цели",        on_goals)
        _nav(IC_BELL,  "Напоминания", on_reminders)

        self.add_widget(Widget(size_hint_y=1))
        self._add_sep()

        exit_item = NavItem(glyph=IC_EXIT, text="Выйти", active=False)
        exit_item.bind(on_release=lambda *_: on_exit())
        self.add_widget(exit_item)

    def _add_sep(self) -> None:
        sep = Widget(size_hint_y=None, height=1)
        with sep.canvas:
            Color(*COL_BORDER)
            _r = Rectangle()
        sep.bind(pos=lambda inst, _v: setattr(_r, "pos", inst.pos),
                 size=lambda inst, _v: setattr(_r, "size", inst.size))
        self.add_widget(sep)

    def _activate(self, active_item: NavItem) -> None:
        for item in self._nav_items:
            item.set_active(item is active_item)


class TransactionCard(BoxLayout):
    def __init__(self, *, income: bool, when: str, kind_ui: str, note: str,
                 category: str | None, amount_cents: int, tx_id: int | None = None,
                 on_delete=None, **kwargs) -> None:
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=96 if on_delete else 86, spacing=12,
                         padding=(10, 10, 14, 10), **kwargs)
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
        top = Label(text=when, color=COL_MUTED, font_size=FS_SMALL, halign="left", valign="middle")
        top.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        title = note or "Без описания"
        main = Label(text=title, color=COL_TEXT, font_size=FS_BODY, halign="left",
                     valign="middle", bold=True)
        main.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        cat_line = f"{kind_ui} · {category}" if category else kind_ui
        sub = Label(text=cat_line, color=COL_MUTED, font_size=FS_SMALL, halign="left", valign="middle")
        sub.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        mid.add_widget(top)
        mid.add_widget(main)
        mid.add_widget(sub)

        sign = "+" if income else "−"
        right = BoxLayout(orientation="vertical", size_hint_x=None, width=120, spacing=4)
        amt = Label(text=f"{sign}{format_rub(amount_cents)}", color=stripe_rgb,
                    font_size=FS_AMOUNT, bold=True, halign="right", valign="middle", size_hint_y=1)
        amt.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        right.add_widget(amt)
        if on_delete is not None and tx_id is not None:
            del_btn = Button(text="Удалить", size_hint_y=None, height=24,
                             background_normal="", background_color=(*COL_DANGER[:3], 0.75),
                             color=COL_TEXT, font_size=FS_SMALL)
            del_btn.bind(on_release=lambda *_a, tid=tx_id: on_delete(tid))
            right.add_widget(del_btn)

        self.add_widget(stripe)
        self.add_widget(mid)
        self.add_widget(right)

    def _sync_bg(self, *_args) -> None:
        m = 4
        self._bg.pos = (self.x + m, self.y + 3)
        self._bg.size = (self.width - 2 * m, self.height - 6)
