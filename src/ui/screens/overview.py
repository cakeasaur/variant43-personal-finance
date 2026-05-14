from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.graphics.vertex_instructions import RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from src.core.models import Transaction, TransactionType
from src.core.reporting import totals_for_period
from src.infra.db.connection import transaction
from src.infra.db.repositories import (
    CategoryRepository,
    GoalRepository,
    ReminderRepository,
    TransactionRepository,
)
from src.ui.cards import IconButton, Sidebar, StatCard, TransactionCard
from src.ui.factories import style_popup, ui_label, ui_spinner
from src.ui.formatting import (
    FILTER_UI_TO_KIND,
    KIND_UI_TO_KIND,
    kind_to_ui,
    month_bounds_utc,
    month_title_ru,
    parse_money,
)
from src.ui.forms import AddTransactionForm
from src.ui.theme import (
    COL_ACCENT,
    COL_BORDER,
    COL_EXPENSE,
    COL_INCOME,
    COL_MUTED,
    COL_SURFACE_ELEV,
    COL_TEXT,
    FS_BODY,
    FS_TITLE,
    IC_ADD,
    IC_EXPENSE,
    IC_INBOX,
    IC_INCOME,
    IC_INFO,
    IC_WALLET,
)
from src.ui.widgets import ModalSheet


@dataclass
class AppState:
    selected_type: str
    current_month: datetime = field(default_factory=lambda: datetime.now(UTC))


class RootView(BoxLayout):
    def __init__(self, conn, repo: TransactionRepository,
                 cat_repo: CategoryRepository, **kwargs):
        super().__init__(orientation="horizontal", spacing=0, padding=0, **kwargs)
        self.conn = conn
        self.repo = repo
        self.cat_repo = cat_repo
        self.goal_repo = GoalRepository(conn)
        self.reminder_repo = ReminderRepository(conn)
        self.state = AppState(selected_type="all")

        self.sidebar = Sidebar(
            on_overview=self._show_overview,
            on_reports=self.open_reports_popup,
            on_goals=self.open_goals_popup,
            on_reminders=self.open_reminders_popup,
            on_exit=self._exit_app,
        )
        self.add_widget(self.sidebar)

        _div = Widget(size_hint_x=None, width=1)
        with _div.canvas:
            Color(*COL_BORDER)
            _dr = Rectangle()
        _div.bind(pos=lambda w, _: setattr(_dr, "pos", w.pos),
                  size=lambda w, _: setattr(_dr, "size", w.size))
        self.add_widget(_div)

        self._content = BoxLayout(orientation="vertical", spacing=10, padding=(16, 12, 16, 12))
        self.add_widget(self._content)
        self._build_content()
        Clock.schedule_once(lambda *_: self.refresh(), 0)

    def _exit_app(self) -> None:
        App.get_running_app().stop()

    def _show_overview(self) -> None:
        self.refresh()

    def _build_content(self) -> None:
        c = self._content

        RIGHT_SIDE_W = 52

        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=52, spacing=8)
        top.add_widget(Widget(size_hint_x=None, width=RIGHT_SIDE_W))

        nav = BoxLayout(orientation="horizontal", size_hint_x=1, spacing=0)
        nav.add_widget(Widget(size_hint_x=1))

        def _make_arrow(codepoint: int, on_press) -> ButtonBehavior:
            btn = type("_Arrow", (ButtonBehavior, BoxLayout), {})(
                orientation="horizontal",
                size_hint=(None, None), width=32, height=32,
            )
            with btn.canvas.before:
                Color(*COL_SURFACE_ELEV)
                _bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[8] * 4)

            def _sb(_inst, _val) -> None:
                _bg.pos = btn.pos
                _bg.size = btn.size

            btn.bind(pos=_sb, size=_sb)
            lbl = Label(
                text=chr(codepoint), font_name="MaterialIcons",
                font_size=18, color=COL_TEXT,
                halign="center", valign="middle",
            )
            lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", inst.size))
            btn.add_widget(lbl)
            btn.bind(on_release=lambda *_: on_press())
            return btn

        nav.add_widget(_make_arrow(0xE5CB, self._go_prev_month))

        self.month_label = Label(
            text=month_title_ru(datetime.now(UTC)),
            font_size=FS_TITLE, bold=True, color=COL_TEXT,
            halign="center", valign="middle",
            size_hint=(None, None), width=200, height=32,
            text_size=(200, 32),
        )
        nav.add_widget(self.month_label)

        nav.add_widget(_make_arrow(0xE5CC, self._go_next_month))

        nav.add_widget(Widget(size_hint_x=1))
        top.add_widget(nav)

        add_fab = IconButton(
            glyph=IC_ADD, glyph_font="MaterialIcons",
            width=52, height=52, accent=True, circle=True, icon_size=22,
        )
        add_fab.bind(on_release=lambda *_: self.open_add_popup())
        top.add_widget(add_fab)
        c.add_widget(top)

        filter_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=28, spacing=10)
        self.period_label = ui_label("Период: текущий месяц (UTC)", height=28, muted=True)
        self.period_label.size_hint_x = 1
        filter_row.add_widget(self.period_label)
        self.type_filter = ui_spinner(text="Все", values=["Все", "Расходы", "Доходы"],
                                      size_hint_x=None, width=130)
        self.type_filter.bind(text=lambda *_: self.refresh())
        filter_row.add_widget(self.type_filter)
        c.add_widget(filter_row)

        sum_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=24)
        sum_lbl = Label(text="Сводка за месяц (с учётом фильтра)", color=COL_MUTED,
                        font_size=FS_BODY, halign="left", valign="middle", size_hint_x=1)
        sum_lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        sum_row.add_widget(sum_lbl)
        info_lbl = Label(text=IC_INFO, font_name="MaterialIcons", color=COL_MUTED,
                         font_size=16, size_hint_x=None, width=24,
                         halign="center", valign="middle")
        info_lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, inst.height)))
        sum_row.add_widget(info_lbl)
        c.add_widget(sum_row)

        stats_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=110, spacing=10)
        self._card_income = StatCard(title="Доходы", glyph=IC_INCOME, amount_color=COL_INCOME)
        self._card_expense = StatCard(title="Расходы", glyph=IC_EXPENSE, amount_color=COL_EXPENSE)
        self._card_balance = StatCard(title="Баланс", glyph=IC_WALLET, amount_color=COL_TEXT)
        stats_row.add_widget(self._card_income)
        stats_row.add_widget(self._card_expense)
        stats_row.add_widget(self._card_balance)
        c.add_widget(stats_row)

        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=10)
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll = ScrollView(bar_width=5, bar_color=(*COL_BORDER[:3], 0.45),
                            bar_inactive_color=(*COL_BORDER[:3], 0.15),
                            scroll_type=["bars", "content"])
        scroll.add_widget(self.list_box)
        c.add_widget(scroll)

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

        income_count = sum(1 for t in tx if t.transaction.type == TransactionType.INCOME)
        expense_count = sum(1 for t in tx if t.transaction.type == TransactionType.EXPENSE)

        self._card_income.update(amount_cents=totals.income_cents, count=income_count)
        self._card_expense.update(amount_cents=totals.expense_cents, count=expense_count)
        bal_color = COL_INCOME if totals.balance_cents >= 0 else COL_EXPENSE
        self._card_balance.update(
            amount_cents=totals.balance_cents,
            count=len(tx),
            color_override=bal_color,
        )

        self.list_box.clear_widgets()
        if not tx:
            self._render_empty_state()
            return

        cats = {c.id: c.name for c in self.cat_repo.list_all()}

        def delete_transaction(tx_id: int) -> None:
            try:
                with transaction(self.conn):
                    self.repo.delete(tx_id=tx_id)
            except Exception as exc:
                from kivy.uix.popup import Popup

                from src.ui.factories import style_popup, ui_label
                from src.ui.widgets import ModalSheet
                sheet = ModalSheet(size_hint=(1, 1))
                sheet.add_widget(ui_label(f"Ошибка удаления: {exc}", height=48))
                p = Popup(title="Ошибка", content=sheet, size_hint=(0.8, 0.3))
                style_popup(p)
                p.open()
                return
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

    def _render_empty_state(self) -> None:
        empty = BoxLayout(orientation="vertical", size_hint_y=None, spacing=14,
                          padding=(0, 28, 0, 0))

        icon_lbl = Label(text=IC_INBOX, font_size=76, font_name="MaterialIcons",
                         color=(*COL_BORDER[:3], 0.55),
                         size_hint_y=None, height=100, halign="center", valign="middle")
        icon_lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, inst.height)))
        empty.add_widget(icon_lbl)

        title_lbl = Label(text="Пока нет операций за этот месяц", color=COL_TEXT,
                          font_size=18, bold=True, halign="center", valign="middle",
                          size_hint_y=None, height=28)
        title_lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        empty.add_widget(title_lbl)

        sub_lbl = Label(text="Нажмите «+», чтобы добавить доход или расход.",
                        color=COL_MUTED, font_size=FS_BODY, halign="center", valign="middle",
                        size_hint_y=None, height=22)
        sub_lbl.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
        empty.add_widget(sub_lbl)

        cta_wrap = BoxLayout(size_hint_y=None, height=50)
        cta_wrap.add_widget(Widget())
        cta_btn = Button(text="+ Добавить операцию", size_hint_x=None, width=230,
                         size_hint_y=None, height=46, background_normal="",
                         background_color=COL_ACCENT, color=(0.06, 0.07, 0.09, 1),
                         font_size=FS_BODY, bold=True)
        cta_btn.bind(on_release=lambda *_: self.open_add_popup())
        cta_wrap.add_widget(cta_btn)
        cta_wrap.add_widget(Widget())
        empty.add_widget(cta_wrap)

        empty.height = 28 + 100 + 14 + 28 + 14 + 22 + 14 + 50
        self.list_box.add_widget(empty)

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
        from src.ui.screens.reports import build_reports_popup
        build_reports_popup(tx_repo=self.repo, cat_repo=self.cat_repo,
                            current_month=self.state.current_month)

    def open_goals_popup(self) -> None:
        from src.ui.screens.goals import build_goals_popup
        build_goals_popup(conn=self.conn, goal_repo=self.goal_repo)

    def open_reminders_popup(self) -> None:
        from src.ui.screens.reminders import build_reminders_popup
        build_reminders_popup(conn=self.conn, reminder_repo=self.reminder_repo)
