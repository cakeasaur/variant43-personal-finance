"""
Прототип главного экрана на Flet поверх существующих src/core и src/infra/db.

Запуск:
    py -3.12 -m pip install flet flet-charts
    py -3.12 prototypes/flet_overview.py

База: prototypes/.demo.sqlite3 (plaintext, без шифрования — это прототип).
При пустой БД автоматически создаются демо-категории и операции,
чтобы экран выглядел как на макете.
"""

from __future__ import annotations

import calendar
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import flet as ft
from flet_charts import (
    ChartAxis,
    ChartAxisLabel,
    LineChart,
    LineChartData,
    LineChartDataPoint,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.core.models import Transaction, TransactionType  # noqa: E402
from src.core.reporting import (  # noqa: E402
    expense_by_day,
    totals_for_period,
)
from src.infra.db.connection import connect, transaction  # noqa: E402
from src.infra.db.repositories import (  # noqa: E402
    CategoryRepository,
    GoalRepository,
    TransactionRepository,
)
from src.infra.db.schema import init_schema  # noqa: E402
from src.ui.formatting import format_rub, month_bounds_utc, month_title_ru  # noqa: E402

# ── палитра (примерно как на макете) ───────────────────────────────────────
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


@dataclass
class Repos:
    cat: CategoryRepository
    tx: TransactionRepository
    goal: GoalRepository


def card_bgcolor(page: ft.Page) -> str:
    return CARD_DARK if page.theme_mode == ft.ThemeMode.DARK else CARD_LIGHT


def page_bgcolor(page: ft.Page) -> str:
    return BG_DARK if page.theme_mode == ft.ThemeMode.DARK else BG_LIGHT


# ── демо-наполнение, если БД пустая ────────────────────────────────────────
def seed_if_empty(tx_repo: TransactionRepository, cats: CategoryRepository, goals: GoalRepository) -> None:
    now = datetime.now(UTC)
    start, end = month_bounds_utc(now)
    existing = tx_repo.list_between(start=start, end=end)
    if existing:
        return

    cats.ensure_defaults()
    name_to_id = {c.name: c.id for c in cats.list_all()}

    rng_day = 1
    demo = [
        ("income",  "Зарплата",       12000000, name_to_id["Дом"]),
        ("expense", "Супермаркет",      245000, name_to_id["Еда"]),
        ("expense", "Такси",             35000, name_to_id["Транспорт"]),
        ("expense", "Кафе",              68000, name_to_id["Развлечения"]),
        ("expense", "Аптека",            41000, name_to_id["Здоровье"]),
        ("expense", "Бензин",           320000, name_to_id["Транспорт"]),
        ("expense", "Кинотеатр",         55000, name_to_id["Развлечения"]),
    ]
    for kind, note, cents, cat_id in demo:
        occurred = now - timedelta(days=rng_day)
        rng_day += 2
        tx_repo.create(
            Transaction(
                type=TransactionType(kind),
                amount_cents=cents,
                occurred_at=occurred,
                category_id=cat_id,
                note=note,
            )
        )

    goals.create(name="Отпуск на море", target_cents=15000000, current_cents=7500000)
    goals.create(name="Новый ноутбук",  target_cents=9000000,  current_cents=4500000)


# ── переиспользуемые блоки UI ──────────────────────────────────────────────
def metric_card(
    page: ft.Page,
    title: str,
    value: str,
    delta: str,
    delta_color: str,
    icon: str,
    icon_bg: str,
) -> ft.Container:
    return ft.Container(
        bgcolor=card_bgcolor(page),
        border_radius=16,
        padding=20,
        expand=True,
        shadow=ft.BoxShadow(
            spread_radius=0, blur_radius=12,
            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        ),
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(title, color=TEXT_MUTED, size=13),
                        ft.Container(
                            bgcolor=icon_bg, border_radius=20,
                            width=32, height=32,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, color=delta_color, size=18),
                        ),
                    ],
                ),
                ft.Text(value, size=24, weight=ft.FontWeight.W_700),
                ft.Text(delta, color=delta_color, size=12, weight=ft.FontWeight.W_500),
            ],
        ),
    )


def sidebar_item(label: str, icon: str, selected: bool = False) -> ft.Container:
    return ft.Container(
        padding=ft.Padding(12, 10, 12, 10),
        border_radius=10,
        bgcolor=GREEN_SOFT if selected else None,
        content=ft.Row(
            spacing=12,
            controls=[
                ft.Icon(icon, color=GREEN if selected else TEXT_MUTED, size=18),
                ft.Text(label, color=GREEN if selected else TEXT_MUTED,
                        weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_400, size=14),
            ],
        ),
    )


def build_sidebar(page: ft.Page, repos: Repos) -> ft.Container:
    def toggle_theme(_e: ft.ControlEvent) -> None:
        page.theme_mode = (
            ft.ThemeMode.DARK if page.theme_mode == ft.ThemeMode.LIGHT else ft.ThemeMode.LIGHT
        )
        page.update()
        # пересобираем экран целиком, чтобы цвета карточек подхватились
        rebuild(page, repos)

    return ft.Container(
        width=220,
        bgcolor=card_bgcolor(page),
        padding=16,
        content=ft.Column(
            spacing=4,
            controls=[
                ft.Container(
                    padding=ft.Padding(12, 12, 12, 20),
                    content=ft.Row(
                        spacing=10,
                        controls=[
                            ft.Container(
                                bgcolor=GREEN, border_radius=10, width=32, height=32,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, color=ft.Colors.WHITE, size=18),
                            ),
                            ft.Text("Finance", size=18, weight=ft.FontWeight.W_700),
                        ],
                    ),
                ),
                sidebar_item("Главная",   ft.Icons.HOME_OUTLINED, selected=True),
                sidebar_item("Операции",  ft.Icons.SWAP_HORIZ),
                sidebar_item("Аналитика", ft.Icons.PIE_CHART_OUTLINE),
                sidebar_item("Цели",      ft.Icons.FLAG_OUTLINED),
                sidebar_item("Категории", ft.Icons.LABEL_OUTLINE),
                sidebar_item("Настройки", ft.Icons.SETTINGS_OUTLINED),
                ft.Container(expand=True),
                ft.Container(
                    padding=ft.Padding(12, 10, 12, 10),
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DARK_MODE_OUTLINED, color=TEXT_MUTED, size=18),
                            ft.Text("Тёмная тема", color=TEXT_MUTED, size=13, expand=True),
                            ft.Switch(
                                value=page.theme_mode == ft.ThemeMode.DARK,
                                on_change=toggle_theme,
                                active_color=GREEN,
                                scale=0.8,
                            ),
                        ],
                    ),
                ),
            ],
        ),
    )


def build_dynamics_chart(by_day: dict, days_in_month: int) -> LineChart:
    income_points = [LineChartDataPoint(x=d, y=0) for d in range(1, days_in_month + 1)]
    expense_points = [
        LineChartDataPoint(x=d, y=by_day.get(d, 0) / 100)
        for d in range(1, days_in_month + 1)
    ]
    return LineChart(
        data_series=[
            LineChartData(
                points=income_points,
                stroke_width=2, color=GREEN, curved=True,
                below_line_bgcolor=ft.Colors.with_opacity(0.1, GREEN),
            ),
            LineChartData(
                points=expense_points,
                stroke_width=2, color=RED, curved=True,
                below_line_bgcolor=ft.Colors.with_opacity(0.1, RED),
            ),
        ],
        border=ft.Border(
            bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.2, TEXT_MUTED)),
        ),
        left_axis=ChartAxis(label_size=40),
        bottom_axis=ChartAxis(
            label_size=20,
            labels=[
                ChartAxisLabel(value=d, label=ft.Text(str(d), size=10, color=TEXT_MUTED))
                for d in (1, 8, 15, 22, days_in_month)
            ],
        ),
        min_y=0, expand=True,
    )


def goal_row(page: ft.Page, icon: str, name: str, current_cents: int, target_cents: int) -> ft.Container:
    ratio = min(1.0, current_cents / target_cents) if target_cents else 0.0
    return ft.Container(
        padding=ft.Padding(0, 8, 0, 8),
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            bgcolor=ft.Colors.with_opacity(0.1, PURPLE), border_radius=8,
                            width=28, height=28, alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, size=16, color=PURPLE),
                        ),
                        ft.Column(
                            spacing=2, expand=True,
                            controls=[
                                ft.Text(name, weight=ft.FontWeight.W_600, size=13),
                                ft.Text(
                                    f"{format_rub(current_cents)} / {format_rub(target_cents)} ₽",
                                    color=TEXT_MUTED, size=11,
                                ),
                            ],
                        ),
                        ft.Text(f"{int(ratio * 100)}%", color=TEXT_MUTED, size=12),
                    ],
                ),
                ft.ProgressBar(value=ratio, color=PURPLE,
                               bgcolor=ft.Colors.with_opacity(0.15, PURPLE),
                               bar_height=6, border_radius=3),
            ],
        ),
    )


def tx_row(page: ft.Page, tx: Transaction, cat_name: str | None) -> ft.Container:
    is_income = tx.type == TransactionType.INCOME
    sign = "+" if is_income else "−"
    color = GREEN if is_income else RED
    icon = ft.Icons.ARROW_UPWARD if is_income else ft.Icons.ARROW_DOWNWARD
    icon_bg = GREEN_SOFT if is_income else RED_SOFT
    return ft.Container(
        padding=ft.Padding(0, 10, 0, 10),
        content=ft.Row(
            controls=[
                ft.Container(
                    bgcolor=icon_bg, border_radius=8, width=32, height=32,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, size=16, color=color),
                ),
                ft.Column(
                    spacing=2, expand=True,
                    controls=[
                        ft.Text(tx.note or "Без описания", weight=ft.FontWeight.W_600, size=13),
                        ft.Text(f"{cat_name or '—'}", color=TEXT_MUTED, size=11),
                    ],
                ),
                ft.Column(
                    spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END,
                    controls=[
                        ft.Text(f"{sign}{format_rub(tx.amount_cents)} ₽",
                                weight=ft.FontWeight.W_700, color=color, size=13),
                        ft.Text(tx.occurred_at.strftime("%d.%m"), color=TEXT_MUTED, size=11),
                    ],
                ),
            ],
        ),
    )


# ── сборка экрана ──────────────────────────────────────────────────────────
def build_main(page: ft.Page, repos: Repos) -> ft.Control:
    now = datetime.now(UTC)
    start, end = month_bounds_utc(now)
    days_in_month = calendar.monthrange(now.year, now.month)[1]

    stored = repos.tx.list_between(start=start, end=end)
    txs = [s.transaction for s in stored]
    tx_ids_to_obj = [(s.id, s.transaction) for s in stored]

    totals = totals_for_period(txs, start=start, end=end)
    by_day_dt = expense_by_day(txs, start=start, end=end)
    by_day = {dt.day: cents for dt, cents in by_day_dt.items()}

    categories = {c.id: c.name for c in repos.cat.list_all()}
    goals = repos.goal.list_all()

    income_delta = "↑ 8.2%"   # для прототипа — статические подписи
    expense_delta = "↓ 3.4%"
    balance_delta = "↑ 11.0%"

    metric_row = ft.Row(
        spacing=16,
        controls=[
            metric_card(page, "Баланс",  f"{format_rub(totals.balance_cents)} ₽",
                        balance_delta, GREEN, ft.Icons.ACCOUNT_BALANCE_WALLET, GREEN_SOFT),
            metric_card(page, "Доходы",  f"{format_rub(totals.income_cents)} ₽",
                        income_delta,  GREEN, ft.Icons.TRENDING_UP, GREEN_SOFT),
            metric_card(page, "Расходы", f"{format_rub(totals.expense_cents)} ₽",
                        expense_delta, RED,   ft.Icons.TRENDING_DOWN, RED_SOFT),
            metric_card(page, "Дней до зарплаты", "12 дней",
                        "следующая 1 числа", PURPLE, ft.Icons.CALENDAR_TODAY, BLUE_SOFT),
        ],
    )

    chart_card = ft.Container(
        bgcolor=card_bgcolor(page), border_radius=16, padding=20, expand=2,
        shadow=ft.BoxShadow(blur_radius=12,
                            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                            offset=ft.Offset(0, 4)),
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Динамика за период", weight=ft.FontWeight.W_700, size=14),
                        ft.Row(
                            spacing=14,
                            controls=[
                                ft.Row(spacing=4, controls=[
                                    ft.Container(width=8, height=8, bgcolor=GREEN, border_radius=4),
                                    ft.Text("Доходы", size=11, color=TEXT_MUTED)]),
                                ft.Row(spacing=4, controls=[
                                    ft.Container(width=8, height=8, bgcolor=RED, border_radius=4),
                                    ft.Text("Расходы", size=11, color=TEXT_MUTED)]),
                            ],
                        ),
                    ],
                ),
                ft.Container(content=build_dynamics_chart(by_day, days_in_month),
                             height=240, expand=True),
            ],
        ),
    )

    goals_card = ft.Container(
        bgcolor=card_bgcolor(page), border_radius=16, padding=20, expand=1,
        shadow=ft.BoxShadow(blur_radius=12,
                            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                            offset=ft.Offset(0, 4)),
        content=ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Цели", weight=ft.FontWeight.W_700, size=14),
                        ft.Text("Все цели", color=GREEN, size=12, weight=ft.FontWeight.W_500),
                    ],
                ),
                *[goal_row(page,
                           ft.Icons.BEACH_ACCESS if "море" in g.name.lower() else ft.Icons.LAPTOP_MAC,
                           g.name, g.current_cents, g.target_cents)
                  for g in goals[:3]],
                ft.Container(
                    padding=ft.Padding(0, 8, 0, 0),
                    content=ft.TextButton(
                        "+ Новая цель",
                        style=ft.ButtonStyle(color=GREEN),
                    ),
                ),
            ],
        ),
    )

    recent_card = ft.Container(
        bgcolor=card_bgcolor(page), border_radius=16, padding=20, expand=True,
        shadow=ft.BoxShadow(blur_radius=12,
                            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                            offset=ft.Offset(0, 4)),
        content=ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Последние операции", weight=ft.FontWeight.W_700, size=14),
                        ft.Text("Показать все", color=GREEN, size=12, weight=ft.FontWeight.W_500),
                    ],
                ),
                *[tx_row(page, t, categories.get(t.category_id))
                  for _id, t in tx_ids_to_obj[:5]],
            ],
        ),
    )

    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("Главная", size=22, weight=ft.FontWeight.W_700),
            ft.Row(
                spacing=10,
                controls=[
                    ft.Container(
                        bgcolor=card_bgcolor(page), border_radius=8,
                        padding=ft.Padding(12, 6, 12, 6),
                        content=ft.Row(
                            spacing=6,
                            controls=[
                                ft.Text(month_title_ru(now), size=12),
                                ft.Icon(ft.Icons.CALENDAR_MONTH, size=14, color=TEXT_MUTED),
                            ],
                        ),
                    ),
                    ft.IconButton(ft.Icons.FILTER_LIST, icon_color=TEXT_MUTED),
                ],
            ),
        ],
    )

    content = ft.Column(
        spacing=16, expand=True,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            header,
            metric_row,
            ft.Row(spacing=16, controls=[chart_card, goals_card]),
            recent_card,
        ],
    )

    return ft.Row(
        expand=True,
        controls=[
            build_sidebar(page, repos),
            ft.Container(
                content=content, expand=True, padding=24,
                bgcolor=page_bgcolor(page),
            ),
        ],
    )


def rebuild(page: ft.Page, repos: Repos) -> None:
    page.controls.clear()
    page.bgcolor = page_bgcolor(page)
    page.add(build_main(page, repos))
    page.update()


def main(page: ft.Page) -> None:
    page.title = "Finance — прототип (Flet)"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window.width = 1280
    page.window.height = 820
    page.fonts = {"Inter": "https://rsms.me/inter/inter.css"}
    page.theme = ft.Theme(font_family="Inter")

    db_path = Path(tempfile.gettempdir()) / "flet_finance_demo.sqlite3"
    conn = connect(db_path)
    init_schema(conn)

    repos = Repos(
        cat=CategoryRepository(conn),
        tx=TransactionRepository(conn),
        goal=GoalRepository(conn),
    )

    with transaction(conn):
        seed_if_empty(repos.tx, repos.cat, repos.goal)

    rebuild(page, repos)


if __name__ == "__main__":
    ft.app(target=main)
