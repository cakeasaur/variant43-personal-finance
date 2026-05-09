from __future__ import annotations

from datetime import datetime

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from src.core.reporting import expense_by_category, expense_by_day, totals_for_period
from src.infra.db.repositories import CategoryRepository, TransactionRepository
from src.ui.cards import SummaryCard
from src.ui.factories import empty_state_label, palette_color, style_popup
from src.ui.formatting import month_bounds_utc
from src.ui.theme import COL_BORDER
from src.ui.widgets import ModalSheet, ReportBarRow, SectionCard


def build_reports_popup(
    *,
    tx_repo: TransactionRepository,
    cat_repo: CategoryRepository,
    current_month: datetime,
) -> None:
    start, end = month_bounds_utc(current_month)
    stored = tx_repo.list_between(start=start, end=end)
    tx = [s.transaction for s in stored]

    cats = {c.id: c.name for c in cat_repo.list_all()}
    cats[None] = "Без категории"

    totals = totals_for_period(tx, start=start, end=end)
    by_cat = expense_by_category(tx, start=start, end=end)
    by_day = expense_by_day(tx, start=start, end=end)

    shell = ModalSheet(size_hint=(1, 1))
    scroll = ScrollView(size_hint=(1, 1), bar_width=5,
                        bar_color=(*COL_BORDER[:3], 0.45),
                        bar_inactive_color=(*COL_BORDER[:3], 0.15),
                        scroll_type=["bars", "content"])
    inner = BoxLayout(orientation="vertical", spacing=16, size_hint_y=None, padding=(0, 4))
    inner.bind(minimum_height=inner.setter("height"))

    summary = SummaryCard()
    summary.set_header(
        f"{start.date().strftime('%d.%m.%Y')} — {end.date().strftime('%d.%m.%Y')} · UTC"
    )
    summary.set_values(income_cents=totals.income_cents, expense_cents=totals.expense_cents,
                       balance_cents=totals.balance_cents)
    inner.add_widget(summary)

    cat_items = sorted(
        ((cats.get(cid, str(cid)), v) for cid, v in by_cat.items()),
        key=lambda x: x[1], reverse=True,
    )
    max_cat = max((v for _, v in cat_items), default=0)
    cat_section = SectionCard(
        "Расходы по категориям",
        subtitle="Сравнение долей расходов. Если в месяце только доходы — блок будет пустым.",
    )
    if not cat_items or max_cat <= 0:
        cat_section.body.add_widget(empty_state_label(
            "За этот месяц нет расходов, поэтому разбивки по категориям пока нет. "
            "Добавьте хотя бы одну операцию «Расход» — здесь появятся цветные столбики."
        ))
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
    day_section = SectionCard("Расходы по дням",
                              subtitle="Динамика по календарным дням (только расходы).")
    if not day_items or max_day <= 0:
        day_section.body.add_widget(empty_state_label(
            "Нет расходов по дням за выбранный месяц — график появится после расходных операций."
        ))
    else:
        day_bar_color = (0.52, 0.62, 0.86, 1)
        for d, cents in day_items:
            if cents <= 0:
                continue
            day_section.body.add_widget(
                ReportBarRow(d.strftime("%d.%m"), cents, max_cents=max_day,
                             bar_color=day_bar_color)
            )
    inner.add_widget(day_section)

    scroll.add_widget(inner)
    shell.add_widget(scroll)
    popup = Popup(title="Отчёты за месяц", content=shell, size_hint=(0.94, 0.9))
    style_popup(popup)
    popup.open()
