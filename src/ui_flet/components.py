from __future__ import annotations

from collections.abc import Callable
from typing import Any

import flet as ft

from ..core.models import Transaction, TransactionType
from ..ui.formatting import format_rub
from .theme import (
    GREEN,
    GREEN_SOFT,
    RED,
    RED_SOFT,
    TEXT_MUTED,
    card_bgcolor,
    card_shadow,
)

# ── диалоги ───────────────────────────────────────────────────────────────

def open_dialog(page: ft.Page, dlg: ft.AlertDialog) -> None:
    page.show_dialog(dlg)


def close_dialog(page: ft.Page, _dlg: ft.AlertDialog) -> None:
    page.pop_dialog()


# ── заглушка пустого состояния ─────────────────────────────────────────────

def empty_state(message: str, icon: str = ft.Icons.INBOX) -> ft.Container:
    return ft.Container(
        expand=True,
        alignment=ft.Alignment(0, 0),
        padding=40,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.Icon(icon, size=64, color=ft.Colors.with_opacity(0.3, TEXT_MUTED)),
                ft.Text(message, color=TEXT_MUTED, size=14, text_align=ft.TextAlign.CENTER),
            ],
        ),
    )


# ── общие карточки ─────────────────────────────────────────────────────────

def card_container(
    page: ft.Page,
    content: ft.Control,
    *,
    expand: bool | int = True,
    padding: int = 20,
) -> ft.Container:
    return ft.Container(
        bgcolor=card_bgcolor(page),
        border_radius=16,
        padding=padding,
        expand=expand,
        shadow=card_shadow(),
        content=content,
    )


def metric_card(
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
                    bgcolor=icon_bg, border_radius=20,
                    width=32, height=32,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icon, color=delta_color, size=18),
                ),
            ],
        ),
        ft.Text(value, size=24, weight=ft.FontWeight.W_700),
    ]
    if delta:
        controls.append(
            ft.Text(delta, color=delta_color, size=12, weight=ft.FontWeight.W_500)
        )
    return card_container(page, ft.Column(spacing=8, controls=controls))


def section_card(
    page: ft.Page,
    title: str,
    controls: list[ft.Control],
    *,
    action_text: str | None = None,
    on_action: Callable[[], None] | None = None,
) -> ft.Container:
    header_controls: list[ft.Control] = [
        ft.Text(title, weight=ft.FontWeight.W_700, size=14)
    ]
    if action_text and on_action:
        header_controls.append(
            ft.TextButton(
                action_text,
                style=ft.ButtonStyle(color=GREEN),
                on_click=lambda _: on_action(),
            )
        )
    return card_container(
        page,
        ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=header_controls,
                ),
                *controls,
            ],
        ),
    )


def progress_row(
    name: str,
    icon: str,
    icon_color: str,
    current_cents: int,
    target_cents: int,
) -> ft.Container:
    ratio = min(1.0, current_cents / target_cents) if target_cents else 0.0
    return ft.Container(
        padding=ft.Padding(0, 6, 0, 6),
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            bgcolor=ft.Colors.with_opacity(0.1, icon_color),
                            border_radius=8, width=28, height=28,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, size=16, color=icon_color),
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
                ft.ProgressBar(
                    value=ratio, color=icon_color,
                    bgcolor=ft.Colors.with_opacity(0.15, icon_color),
                    bar_height=6, border_radius=3,
                ),
            ],
        ),
    )


def tx_row(tx: Transaction, cat_name: str | None) -> ft.Container:
    is_income = tx.type == TransactionType.INCOME
    sign = "+" if is_income else "−"
    color = GREEN if is_income else RED
    icon = ft.Icons.ARROW_UPWARD if is_income else ft.Icons.ARROW_DOWNWARD
    icon_bg = GREEN_SOFT if is_income else RED_SOFT

    left: ft.Control = (
        ft.Column(
            spacing=2, expand=True,
            controls=[
                ft.Text(tx.note or "Без описания", weight=ft.FontWeight.W_600, size=13),
                ft.Text(cat_name, color=TEXT_MUTED, size=11),
            ],
        ) if cat_name else
        ft.Text(
            tx.note or "Без описания",
            weight=ft.FontWeight.W_600, size=13, expand=True,
        )
    )

    return ft.Container(
        padding=ft.Padding(0, 10, 0, 10),
        content=ft.Row(
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    bgcolor=icon_bg, border_radius=8, width=32, height=32,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Icon(icon, size=16, color=color),
                ),
                ft.Container(width=10),
                left,
                ft.Container(width=10),
                ft.Column(
                    spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END,
                    controls=[
                        ft.Text(
                            f"{sign}{format_rub(tx.amount_cents)} ₽",
                            weight=ft.FontWeight.W_700, color=color, size=13,
                        ),
                        ft.Text(tx.occurred_at.strftime("%d.%m"), color=TEXT_MUTED, size=11),
                    ],
                ),
            ],
        ),
    )


# ── сайдбар ────────────────────────────────────────────────────────────────

_NAV_ITEMS = [
    ("overview",    "Главная",      ft.Icons.HOME_OUTLINED),
    ("operations",  "Операции",     ft.Icons.SWAP_HORIZ),
    ("reports",     "Аналитика",    ft.Icons.PIE_CHART_OUTLINE),
    ("goals",       "Цели",         ft.Icons.FLAG_OUTLINED),
    ("reminders",   "Напоминания",  ft.Icons.NOTIFICATIONS_OUTLINED),
    ("categories",  "Категории",    ft.Icons.LABEL_OUTLINE),
    ("settings",    "Настройки",    ft.Icons.SETTINGS_OUTLINED),
]


def sidebar_item(
    label: str,
    icon: str,
    *,
    selected: bool = False,
    on_click: Callable[[Any], None] | None = None,
) -> ft.Container:
    return ft.Container(
        padding=ft.Padding(12, 10, 12, 10),
        border_radius=10,
        bgcolor=GREEN_SOFT if selected else None,
        on_click=on_click,
        ink=on_click is not None,
        content=ft.Row(
            spacing=12,
            controls=[
                ft.Icon(icon, color=GREEN if selected else TEXT_MUTED, size=18),
                ft.Text(
                    label,
                    color=GREEN if selected else TEXT_MUTED,
                    weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_400,
                    size=14,
                ),
            ],
        ),
    )


def build_sidebar(
    page: ft.Page,
    current_route: str,
    navigate: Callable[[str], None],
    on_theme_toggle: Callable[[Any], None],
) -> ft.Container:
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
                                content=ft.Icon(
                                    ft.Icons.ACCOUNT_BALANCE_WALLET,
                                    color=ft.Colors.WHITE, size=18,
                                ),
                            ),
                            ft.Text("Finance", size=18, weight=ft.FontWeight.W_700),
                        ],
                    ),
                ),
                *[
                    sidebar_item(
                        label, icon,
                        selected=(current_route == route),
                        on_click=lambda _, r=route: navigate(r),
                    )
                    for route, label, icon in _NAV_ITEMS
                ],
                ft.Container(expand=True),
                ft.Container(
                    padding=ft.Padding(12, 10, 12, 10),
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DARK_MODE_OUTLINED, color=TEXT_MUTED, size=18),
                            ft.Text("Тёмная тема", color=TEXT_MUTED, size=13, expand=True),
                            ft.Switch(
                                value=page.theme_mode == ft.ThemeMode.DARK,
                                on_change=on_theme_toggle,
                                active_color=GREEN,
                                scale=0.8,
                            ),
                        ],
                    ),
                ),
            ],
        ),
    )
