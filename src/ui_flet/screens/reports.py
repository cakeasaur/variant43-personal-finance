from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import flet as ft

from ...core.reporting import expense_by_category, expense_by_day, totals_for_period
from ...ui.formatting import format_rub, month_bounds_utc, month_title_ru
from ..components import build_sidebar, card_container, empty_state, metric_card
from ..state import Repos
from ..theme import GREEN, GREEN_SOFT, RED, RED_SOFT, TEXT_MUTED, page_bgcolor

_PALETTE = [
    "#EF4444", "#F97316", "#F59E0B", "#3B82F6",
    "#8B5CF6", "#EC4899", "#14B8A6", "#64748B",
]

_MAX_BAR_WIDTH = 560


def _category_chart(cat_items: list[tuple[str, int]], total: int) -> ft.Container:
    rows: list[ft.Control] = []
    for i, (name, cents) in enumerate(cat_items):
        ratio = cents / total if total > 0 else 0
        color = _PALETTE[i % len(_PALETTE)]
        rows.append(
            ft.Container(
                padding=ft.Padding(0, 6, 0, 6),
                content=ft.Column(
                    spacing=5,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Container(
                                    width=10, height=10, border_radius=5,
                                    bgcolor=color,
                                    margin=ft.Margin(0, 1, 0, 0),
                                ),
                                ft.Text(name, size=13, expand=True),
                                ft.Text(
                                    f"{int(ratio * 100)}%",
                                    size=12, color=TEXT_MUTED,
                                    width=36,
                                    text_align=ft.TextAlign.RIGHT,
                                ),
                                ft.Text(
                                    f"{format_rub(cents)} ₽",
                                    size=12, color=TEXT_MUTED,
                                    width=110,
                                    text_align=ft.TextAlign.RIGHT,
                                ),
                            ],
                        ),
                        ft.ProgressBar(
                            value=ratio,
                            color=color,
                            bgcolor=ft.Colors.with_opacity(0.1, color),
                            bar_height=8,
                            border_radius=4,
                        ),
                    ],
                ),
            )
        )
    return ft.Container(
        width=_MAX_BAR_WIDTH,
        content=ft.Column(spacing=0, controls=rows),
    )


def _day_chart(day_items: list[tuple], max_cents: int) -> ft.Container:
    rows: list[ft.Control] = []
    for d, cents in day_items:
        ratio = cents / max_cents if max_cents > 0 else 0
        rows.append(
            ft.Container(
                padding=ft.Padding(0, 4, 0, 4),
                content=ft.Column(
                    spacing=4,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Text(
                                    d.strftime("%d.%m"),
                                    size=12, weight=ft.FontWeight.W_500,
                                    width=40,
                                ),
                                ft.Text(
                                    f"{format_rub(cents)} ₽",
                                    size=11, color=TEXT_MUTED,
                                ),
                            ],
                        ),
                        ft.ProgressBar(
                            value=ratio,
                            color="#3B82F6",
                            bgcolor=ft.Colors.with_opacity(0.1, "#3B82F6"),
                            bar_height=8,
                            border_radius=4,
                        ),
                    ],
                ),
            )
        )
    return ft.Container(
        width=_MAX_BAR_WIDTH,
        content=ft.Column(spacing=0, controls=rows),
    )


def build_reports(
    page: ft.Page,
    repos: Repos,
    state: dict,
    navigate: Callable[[str], None],
    rebuild: Callable[[], None],
    on_theme_toggle: Callable[[Any], None],
) -> ft.Control:
    current_month: datetime = state.get("ops_month", datetime.now(UTC))
    start, end = month_bounds_utc(current_month)
    stored = repos.tx.list_between(start=start, end=end)
    txs = [s.transaction for s in stored]

    totals = totals_for_period(txs, start=start, end=end)
    by_cat = expense_by_category(txs, start=start, end=end)
    by_day = expense_by_day(txs, start=start, end=end)
    cats = {c.id: c.name for c in repos.cat.list_all()}
    cats[None] = "Без категории"

    def prev_month(_: ft.ControlEvent) -> None:
        dt = state.get("ops_month", datetime.now(UTC))
        state["ops_month"] = (
            datetime(dt.year - 1, 12, 1, tzinfo=UTC) if dt.month == 1
            else datetime(dt.year, dt.month - 1, 1, tzinfo=UTC)
        )
        rebuild()

    def next_month(_: ft.ControlEvent) -> None:
        dt = state.get("ops_month", datetime.now(UTC))
        state["ops_month"] = (
            datetime(dt.year + 1, 1, 1, tzinfo=UTC) if dt.month == 12
            else datetime(dt.year, dt.month + 1, 1, tzinfo=UTC)
        )
        rebuild()

    balance_color = GREEN if totals.balance_cents >= 0 else RED

    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("Аналитика", size=22, weight=ft.FontWeight.W_700),
            ft.Row(spacing=8, controls=[
                ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=prev_month,
                              icon_color=TEXT_MUTED),
                ft.Text(month_title_ru(current_month), size=14,
                        weight=ft.FontWeight.W_600),
                ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=next_month,
                              icon_color=TEXT_MUTED),
            ]),
        ],
    )

    summary_row = ft.Row(
        spacing=16,
        controls=[
            metric_card(page, "Доходы", f"{format_rub(totals.income_cents)} ₽",
                        "", GREEN, ft.Icons.TRENDING_UP, GREEN_SOFT),
            metric_card(page, "Расходы", f"{format_rub(totals.expense_cents)} ₽",
                        "", RED, ft.Icons.TRENDING_DOWN, RED_SOFT),
            metric_card(page, "Баланс", f"{format_rub(totals.balance_cents)} ₽",
                        "", balance_color, ft.Icons.ACCOUNT_BALANCE_WALLET, GREEN_SOFT),
        ],
    )

    # ── расходы по категориям ─────────────────────────────────────────────
    cat_items = sorted(
        ((cats.get(cid, str(cid)), v) for cid, v in by_cat.items()),
        key=lambda x: x[1], reverse=True,
    )
    cat_items = [(n, v) for n, v in cat_items if v > 0]
    total_expense = sum(v for _, v in cat_items)

    cat_card = card_container(
        page,
        ft.Column(
            spacing=16,
            controls=[
                ft.Row(spacing=8, controls=[
                    ft.Icon(ft.Icons.DONUT_LARGE, color=TEXT_MUTED, size=16),
                    ft.Text("Расходы по категориям",
                            weight=ft.FontWeight.W_700, size=14),
                    ft.Container(expand=True),
                    ft.Text(
                        f"Всего: {format_rub(total_expense)} ₽",
                        size=12, color=TEXT_MUTED,
                    ) if cat_items else ft.Container(),
                ]),
                _category_chart(cat_items, total_expense)
                if cat_items else
                empty_state("Расходов за этот месяц нет.",
                            ft.Icons.PIE_CHART_OUTLINE),
            ],
        ),
    )

    # ── расходы по дням ───────────────────────────────────────────────────
    day_items = [(d, v) for d, v in sorted(by_day.items()) if v > 0]
    max_day = max((v for _, v in day_items), default=0)

    day_card = card_container(
        page,
        ft.Column(
            spacing=16,
            controls=[
                ft.Row(spacing=8, controls=[
                    ft.Icon(ft.Icons.CALENDAR_TODAY, color=TEXT_MUTED, size=16),
                    ft.Text("Расходы по дням",
                            weight=ft.FontWeight.W_700, size=14),
                ]),
                _day_chart(day_items, max_day)
                if day_items else
                empty_state("Расходов по дням нет.", ft.Icons.CALENDAR_TODAY),
            ],
        ),
    )

    content = ft.Column(
        spacing=16, expand=True, scroll=ft.ScrollMode.AUTO,
        controls=[header, summary_row, cat_card, day_card],
    )

    return ft.Row(
        expand=True,
        controls=[
            build_sidebar(page, "reports", navigate, on_theme_toggle),
            ft.Container(content=content, expand=True, padding=24,
                         bgcolor=page_bgcolor(page)),
        ],
    )
