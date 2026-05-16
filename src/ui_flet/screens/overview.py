from __future__ import annotations

import calendar
import io
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import flet as ft
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

matplotlib.use("Agg")

from ...core.reporting import expense_by_category, expense_by_day, income_by_day, totals_for_period
from ...ui.formatting import format_rub, month_bounds_utc
from ..components import build_sidebar, card_container, tx_row
from ..state import Repos
from ..theme import (
    BLUE_SOFT,
    GREEN,
    GREEN_SOFT,
    PURPLE,
    RED,
    RED_SOFT,
    TEXT_MUTED,
    card_bgcolor,
    page_bgcolor,
)

__all__ = ["build_overview"]

_MONTH_SHORT = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "мая", 6: "июн",
    7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}

_GOAL_ICONS = {
    "море": ft.Icons.BEACH_ACCESS, "ноутбук": ft.Icons.LAPTOP_MAC,
    "машин": ft.Icons.DIRECTIONS_CAR, "квартир": ft.Icons.HOME,
    "телефон": ft.Icons.PHONE_ANDROID, "отпуск": ft.Icons.BEACH_ACCESS,
}

_CAT_COLORS = [PURPLE, "#3B82F6", "#F59E0B", "#EC4899", "#14B8A6"]


# ── helpers ───────────────────────────────────────────────────────────────────

def _pct_delta(current: int, previous: int) -> tuple[str, str]:
    if previous == 0:
        return "", TEXT_MUTED
    diff = (current - previous) / previous * 100
    arrow = "↑" if diff >= 0 else "↓"
    color = GREEN if diff >= 0 else RED
    return f"{arrow} {abs(diff):.1f}%", color


def _days_word(n: int) -> str:
    if 11 <= n % 100 <= 19:
        return "дней"
    r = n % 10
    if r == 1:
        return "день"
    if 2 <= r <= 4:
        return "дня"
    return "дней"


def _smooth_gaussian(arr: list[float], sigma: float = 2.5) -> list[float]:
    import numpy as np
    a = np.array(arr, dtype=float)
    if a.max() == 0:
        return arr
    radius = max(1, int(3 * sigma))
    x = np.arange(-radius, radius + 1, dtype=float)
    kernel = np.exp(-x * x / (2 * sigma * sigma))
    kernel /= kernel.sum()
    padded = np.concatenate([np.zeros(radius), a, np.zeros(radius)])
    return np.convolve(padded, kernel, mode="valid").tolist()


# ── chart ─────────────────────────────────────────────────────────────────────

def _dynamics_chart(
    by_day_income: dict,
    by_day_expense: dict,
    days_in_month: int,
    month_num: int,
    is_dark: bool,
) -> ft.Image:
    plt.close("all")
    bg       = "#1E293B" if is_dark else "#FFFFFF"
    fg       = "#CBD5E1" if is_dark else "#64748B"
    grid_col = "#334155" if is_dark else "#F1F5F9"
    mon      = _MONTH_SHORT.get(month_num, "")
    days     = list(range(1, days_in_month + 1))

    smooth_inc = _smooth_gaussian([by_day_income.get(d, 0) / 100 for d in days])
    smooth_exp = _smooth_gaussian([by_day_expense.get(d, 0) / 100 for d in days])

    marker_days = list(range(1, days_in_month + 1, 3))
    if marker_days[-1] != days_in_month:
        marker_days.append(days_in_month)

    fig, ax = plt.subplots(figsize=(10, 3.0))
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)

    ax.fill_between(days, smooth_inc, alpha=0.13, color=GREEN, zorder=1)
    ax.fill_between(days, smooth_exp, alpha=0.13, color=RED, zorder=1)
    ax.plot(days, smooth_inc, color=GREEN, linewidth=2.2, zorder=3)
    ax.plot(days, smooth_exp, color=RED, linewidth=2.2, zorder=3)

    for d in marker_days:
        idx = d - 1
        ax.plot(d, smooth_inc[idx], "o", color=GREEN, markersize=5, markeredgewidth=0, zorder=4)
        ax.plot(d, smooth_exp[idx], "o", color=RED, markersize=5, markeredgewidth=0, zorder=4)

    ticks = [1, 8, 15, 22, days_in_month]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{d} {mon}" for d in ticks], color=fg, fontsize=8.5)
    ax.set_xlim(0.5, days_in_month + 0.5)

    def _fmt_y(val: float, _pos: int) -> str:
        if val >= 1_000_000:
            return f"{val/1_000_000:.1f}М".rstrip("0").rstrip(".")
        if val >= 1_000:
            n = val / 1_000
            return f"{int(n)}К" if n == int(n) else f"{n:.1f}К"
        return str(int(val)) if val > 0 else "0"

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_y))
    ax.tick_params(axis="y", colors=fg, labelsize=8.5, length=0)
    ax.tick_params(axis="x", colors=fg, length=0)
    ax.set_ylim(bottom=0)
    ax.yaxis.grid(True, color=grid_col, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color("#334155" if is_dark else "#E2E8F0")
    ax.spines["bottom"].set_linewidth(0.8)

    fig.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return ft.Image(src=buf.read(), fit=ft.BoxFit.CONTAIN, expand=True)


# ── sub-widgets ───────────────────────────────────────────────────────────────

def _metric_card(
    page: ft.Page,
    title: str,
    value: str,
    delta: str,
    delta_color: str,
    icon: str,
    icon_bg: str,
) -> ft.Container:
    controls: list[ft.Control] = [
        ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Text(title, color=TEXT_MUTED, size=13),
                ft.Container(
                    bgcolor=icon_bg, border_radius=20, width=32, height=32,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, color=delta_color, size=18),
                ),
            ],
        ),
        ft.Text(value, size=22, weight=ft.FontWeight.W_700),
    ]
    if delta:
        controls.append(
            ft.Text(delta, color=delta_color, size=12, weight=ft.FontWeight.W_500)
        )
    return card_container(page, ft.Column(spacing=8, controls=controls))


def _cat_row(
    name: str,
    amount_cents: int,
    total_cents: int,
    color: str,
) -> ft.Container:
    ratio = min(1.0, amount_cents / total_cents) if total_cents else 0.0
    return ft.Container(
        padding=ft.Padding(0, 8, 0, 8),
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            bgcolor=ft.Colors.with_opacity(0.12, color),
                            border_radius=6, width=10, height=10,
                        ),
                        ft.Container(width=8),
                        ft.Text(name, expand=True, size=13, weight=ft.FontWeight.W_500),
                        ft.Text(
                            f"{format_rub(amount_cents)} ₽",
                            color=TEXT_MUTED, size=12,
                        ),
                        ft.Container(width=8),
                        ft.Text(
                            f"{int(ratio * 100)}%",
                            color=color, size=12, weight=ft.FontWeight.W_600,
                            width=32, text_align=ft.TextAlign.RIGHT,
                        ),
                    ],
                ),
                ft.ProgressBar(
                    value=ratio, color=color,
                    bgcolor=ft.Colors.with_opacity(0.12, color),
                    bar_height=5, border_radius=3,
                ),
            ],
        ),
    )


def _goal_icon(name: str) -> str:
    nl = name.lower()
    for kw, ico in _GOAL_ICONS.items():
        if kw in nl:
            return ico
    return ft.Icons.FLAG_OUTLINED


# ── main builder ──────────────────────────────────────────────────────────────

def build_overview(
    page: ft.Page,
    repos: Repos,
    navigate: Callable[[str], None],
    on_theme_toggle: Callable[[Any], None],
) -> ft.Control:
    now = datetime.now(UTC)
    start, end = month_bounds_utc(now)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    is_dark = page.theme_mode == ft.ThemeMode.DARK

    # current month
    stored = repos.tx.list_between(start=start, end=end)
    txs = [s.transaction for s in stored]
    totals = totals_for_period(txs, start=start, end=end)
    by_day_exp = {dt.day: c for dt, c in expense_by_day(txs, start=start, end=end).items()}
    by_day_inc = {dt.day: c for dt, c in income_by_day(txs, start=start, end=end).items()}
    categories = {c.id: c.name for c in repos.cat.list_all()}
    goals = repos.goal.list_all()

    # previous month for deltas
    prev_end_dt = start - timedelta(seconds=1)
    prev_start, prev_end = month_bounds_utc(prev_end_dt)
    prev_txs = [s.transaction for s in repos.tx.list_between(start=prev_start, end=prev_end)]
    prev_totals = totals_for_period(prev_txs, start=prev_start, end=prev_end)

    # top-3 expense categories
    cat_spending = expense_by_category(txs, start=start, end=end)
    top_cats = sorted(cat_spending.items(), key=lambda x: x[1], reverse=True)[:3]

    # deltas
    bal_delta, bal_color = _pct_delta(totals.balance_cents, prev_totals.balance_cents)
    inc_delta, inc_color = _pct_delta(totals.income_cents, prev_totals.income_cents)
    exp_delta, exp_color = _pct_delta(totals.expense_cents, prev_totals.expense_cents)
    balance_color = GREEN if totals.balance_cents >= 0 else RED

    days_left = days_in_month - now.day

    # ── header ────────────────────────────────────────────────────────────────
    mon = _MONTH_SHORT[now.month]
    date_range = f"{start.day}–{end.day} {mon} {now.year}"

    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("Главная", size=22, weight=ft.FontWeight.W_700),
            ft.Row(spacing=8, controls=[
                ft.Container(
                    bgcolor=card_bgcolor(page), border_radius=8,
                    padding=ft.Padding(12, 6, 12, 6),
                    content=ft.Row(spacing=6, controls=[
                        ft.Text(date_range, size=12, color=TEXT_MUTED),
                        ft.Icon(ft.Icons.CALENDAR_MONTH_OUTLINED, size=14, color=TEXT_MUTED),
                    ]),
                ),
                ft.Container(
                    bgcolor=card_bgcolor(page), border_radius=8,
                    width=34, height=34,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.TUNE, size=16, color=TEXT_MUTED),
                ),
            ]),
        ],
    )

    # ── metric row ────────────────────────────────────────────────────────────
    metric_row = ft.Row(
        spacing=16,
        controls=[
            _metric_card(page, "Баланс",
                         f"{format_rub(totals.balance_cents)} ₽",
                         bal_delta, balance_color,
                         ft.Icons.ACCOUNT_BALANCE_WALLET, GREEN_SOFT),
            _metric_card(page, "Доходы",
                         f"{format_rub(totals.income_cents)} ₽",
                         inc_delta, inc_color,
                         ft.Icons.TRENDING_UP, GREEN_SOFT),
            _metric_card(page, "Расходы",
                         f"{format_rub(totals.expense_cents)} ₽",
                         exp_delta, exp_color,
                         ft.Icons.TRENDING_DOWN, RED_SOFT),
            _metric_card(page, "До конца месяца",
                         f"{days_left} {_days_word(days_left)}",
                         f"из {days_in_month} дней в месяце", "#3B82F6",
                         ft.Icons.CALENDAR_TODAY, BLUE_SOFT),
        ],
    )

    # ── chart card ────────────────────────────────────────────────────────────
    chart_card = card_container(
        page,
        ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Динамика за период", weight=ft.FontWeight.W_700, size=14),
                        ft.Row(spacing=14, controls=[
                            ft.Row(spacing=6, controls=[
                                ft.Container(width=10, height=10, bgcolor=GREEN, border_radius=5),
                                ft.Text("Доходы", size=12, color=TEXT_MUTED),
                            ]),
                            ft.Row(spacing=6, controls=[
                                ft.Container(width=10, height=10, bgcolor=RED, border_radius=5),
                                ft.Text("Расходы", size=12, color=TEXT_MUTED),
                            ]),
                        ]),
                    ],
                ),
                ft.Container(
                    content=_dynamics_chart(by_day_inc, by_day_exp,
                                            days_in_month, now.month, is_dark),
                    height=200, expand=True,
                ),
            ],
        ),
    )

    # ── recent operations card ─────────────────────────────────────────────
    recent_card = card_container(
        page,
        ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Последние операции", weight=ft.FontWeight.W_700, size=14),
                        ft.TextButton("Показать все",
                                      style=ft.ButtonStyle(color=GREEN),
                                      on_click=lambda _: navigate("operations")),
                    ],
                ),
                *(
                    [ft.Text("Операций пока нет", color=TEXT_MUTED, size=13)]
                    if not stored else
                    [tx_row(s.transaction, categories.get(s.transaction.category_id))
                     for s in stored[:5]]
                ),
            ],
        ),
    )

    # ── top categories card ────────────────────────────────────────────────
    if top_cats:
        cat_controls: list[ft.Control] = [
            _cat_row(
                categories.get(cat_id, "Без категории"),
                amount,
                totals.expense_cents,
                _CAT_COLORS[i % len(_CAT_COLORS)],
            )
            for i, (cat_id, amount) in enumerate(top_cats)
        ]
    else:
        cat_controls = [ft.Text("Расходов пока нет", color=TEXT_MUTED, size=13)]

    categories_card = card_container(
        page,
        ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Расходы по категориям", weight=ft.FontWeight.W_700, size=14),
                        ft.TextButton("Аналитика",
                                      style=ft.ButtonStyle(color=GREEN),
                                      on_click=lambda _: navigate("reports")),
                    ],
                ),
                *cat_controls,
            ],
        ),
    )

    # ── goals card ────────────────────────────────────────────────────────────
    goals_card = card_container(
        page,
        ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Цели", weight=ft.FontWeight.W_700, size=14),
                        ft.TextButton("Все цели",
                                      style=ft.ButtonStyle(color=GREEN),
                                      on_click=lambda _: navigate("goals")),
                    ],
                ),
                *(
                    [ft.Text("Целей пока нет", color=TEXT_MUTED, size=13)]
                    if not goals else
                    [
                        ft.Container(
                            padding=ft.Padding(0, 6, 0, 6),
                            content=ft.Row(
                                spacing=12,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        bgcolor=ft.Colors.with_opacity(0.1, PURPLE),
                                        border_radius=8, width=32, height=32,
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(_goal_icon(g.name), size=16, color=PURPLE),
                                    ),
                                    ft.Column(
                                        spacing=3, expand=True,
                                        controls=[
                                            ft.Text(g.name, size=13, weight=ft.FontWeight.W_600),
                                            ft.Text(
                                                f"{format_rub(g.current_cents)} / "
                                                f"{format_rub(g.target_cents)} ₽",
                                                size=11, color=TEXT_MUTED,
                                            ),
                                            ft.ProgressBar(
                                                value=g.progress_ratio, color=PURPLE,
                                                bgcolor=ft.Colors.with_opacity(0.12, PURPLE),
                                                bar_height=4, border_radius=2,
                                            ),
                                        ],
                                    ),
                                    ft.Text(
                                        f"{int(g.progress_ratio * 100)}%",
                                        size=12, color=TEXT_MUTED,
                                    ),
                                ],
                            ),
                        )
                        for g in goals[:3]
                    ]
                ),
                ft.TextButton("+ Новая цель",
                              style=ft.ButtonStyle(color=GREEN),
                              on_click=lambda _: navigate("goals")),
            ],
        ),
    )

    # ── layout ────────────────────────────────────────────────────────────────
    content = ft.Column(
        spacing=16, expand=True, scroll=ft.ScrollMode.AUTO,
        controls=[
            header,
            metric_row,
            ft.Row(
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Column(spacing=16, expand=3,
                              controls=[chart_card, recent_card]),
                    ft.Column(spacing=16, expand=2,
                              controls=[categories_card, goals_card]),
                ],
            ),
        ],
    )

    return ft.Row(
        expand=True,
        controls=[
            build_sidebar(page, "overview", navigate, on_theme_toggle),
            ft.Container(content=content, expand=True, padding=24,
                         bgcolor=page_bgcolor(page)),
        ],
    )
