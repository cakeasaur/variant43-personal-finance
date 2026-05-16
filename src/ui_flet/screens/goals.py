from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import flet as ft

from ...infra.db.connection import transaction as db_tx
from ...infra.db.repositories import Goal
from ...ui.formatting import format_rub, parse_money
from ..components import (
    build_sidebar,
    close_dialog,
    empty_state,
    open_dialog,
)
from ..state import Repos
from ..theme import GREEN, GREEN_SOFT, PURPLE, RED, TEXT_MUTED, page_bgcolor


def _goal_dialog(
    page: ft.Page,
    repos: Repos,
    on_saved: Callable[[], None],
    existing: Goal | None = None,
) -> None:
    name_f = ft.TextField(
        label="Название", autofocus=True, border_radius=10,
        value=existing.name if existing else "",
    )
    target_f = ft.TextField(
        label="Цель (₽)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=10,
        value=f"{existing.target_cents / 100:.2f}" if existing else "",
    )
    current_f = ft.TextField(
        label="Текущий прогресс (₽)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=10,
        value=f"{existing.current_cents / 100:.2f}" if existing else "0",
    )
    deadline_f = ft.TextField(
        label="Дедлайн ГГГГ-ММ-ДД (необязательно)", border_radius=10,
        value=(existing.deadline_at.date().isoformat()
               if existing and existing.deadline_at else ""),
    )
    note_f = ft.TextField(
        label="Заметка (необязательно)", border_radius=10,
        value=existing.note or "" if existing else "",
    )
    err = ft.Text("", color=RED, size=12)

    def do_save(_: ft.ControlEvent) -> None:
        err.value = ""
        try:
            name = name_f.value.strip()
            if not name:
                raise ValueError("Введите название")
            target_cents = parse_money(target_f.value or "")
            current_cents = parse_money(current_f.value or "0")
            if target_cents <= 0:
                raise ValueError("Цель должна быть > 0")
            if current_cents < 0:
                raise ValueError("Прогресс >= 0")
            deadline_dt: datetime | None = None
            if deadline_f.value.strip():
                d = date.fromisoformat(deadline_f.value.strip())
                deadline_dt = datetime(d.year, d.month, d.day, tzinfo=UTC)
            note = note_f.value.strip() or None
            with db_tx(repos.goal.conn):
                if existing is None:
                    repos.goal.create(name=name, target_cents=target_cents,
                                      current_cents=current_cents,
                                      deadline_at=deadline_dt, note=note)
                else:
                    repos.goal.update(goal_id=existing.id, name=name,
                                      target_cents=target_cents, current_cents=current_cents,
                                      deadline_at=deadline_dt, note=note)
            close_dialog(page, dlg)
            on_saved()
        except ValueError as exc:
            err.value = str(exc)
            page.update()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Новая цель" if existing is None else "Редактировать цель"),
        content=ft.Container(
            width=400,
            content=ft.Column(tight=True, spacing=12,
                               controls=[name_f, target_f, current_f,
                                         deadline_f, note_f, err]),
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda _: close_dialog(page, dlg)),
            ft.FilledButton("Сохранить", on_click=do_save),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    open_dialog(page, dlg)


def _deposit_dialog(
    page: ft.Page,
    repos: Repos,
    goal: Goal,
    on_saved: Callable[[], None],
) -> None:
    remaining = goal.target_cents - goal.current_cents
    amount_f = ft.TextField(
        label=f"Сумма пополнения (осталось {format_rub(remaining)} ₽)",
        keyboard_type=ft.KeyboardType.NUMBER, autofocus=True, border_radius=10,
    )
    err = ft.Text("", color=RED, size=12)

    def do_deposit(_: ft.ControlEvent) -> None:
        err.value = ""
        try:
            cents = parse_money(amount_f.value or "")
            if cents <= 0:
                raise ValueError("Сумма должна быть > 0")
            with db_tx(repos.goal.conn):
                repos.goal.deposit(goal_id=goal.id, amount_cents=cents)
            close_dialog(page, dlg)
            on_saved()
        except ValueError as exc:
            err.value = str(exc)
            page.update()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"Пополнить «{goal.name}»"),
        content=ft.Container(
            width=360,
            content=ft.Column(tight=True, spacing=12, controls=[amount_f, err]),
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda _: close_dialog(page, dlg)),
            ft.FilledButton("Пополнить", on_click=do_deposit),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    open_dialog(page, dlg)


def _ring_progress(ratio: float, color: str, size: int = 56) -> ft.Stack:
    pct = ft.Text(
        f"{int(ratio * 100)}%",
        size=11, weight=ft.FontWeight.W_700, color=color,
        text_align=ft.TextAlign.CENTER,
    )
    return ft.Stack(
        width=size, height=size,
        controls=[
            ft.ProgressRing(
                value=ratio, color=color,
                bgcolor=ft.Colors.with_opacity(0.15, color),
                stroke_width=6, width=size, height=size,
            ),
            ft.Container(
                width=size, height=size,
                alignment=ft.Alignment.CENTER,
                content=pct,
            ),
        ],
    )


def _goal_card(
    page: ft.Page,
    repos: Repos,
    goal: Goal,
    on_refresh: Callable[[], None],
) -> ft.Container:
    ratio = goal.progress_ratio
    is_done = ratio >= 1.0
    color = GREEN if is_done else PURPLE
    deadline_str = (
        f"до {goal.deadline_at.date().isoformat()}"
        if goal.deadline_at else ""
    )

    def do_delete(_: ft.ControlEvent) -> None:
        with db_tx(repos.goal.conn):
            repos.goal.delete(goal_id=goal.id)
        on_refresh()

    bg = "#1E293B" if page.theme_mode == ft.ThemeMode.DARK else "#FFFFFF"
    return ft.Container(
        bgcolor=bg, border_radius=16, padding=20,
        shadow=ft.BoxShadow(
            blur_radius=10, spread_radius=0,
            color=ft.Colors.with_opacity(0.07, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        ),
        content=ft.Row(
            spacing=20,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                _ring_progress(ratio, color),
                ft.Column(
                    spacing=4, expand=True,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Text(goal.name, weight=ft.FontWeight.W_700,
                                        size=15, expand=True),
                                *([ ft.Container(
                                    bgcolor=GREEN_SOFT, border_radius=20,
                                    padding=ft.Padding(8, 2, 8, 2),
                                    content=ft.Text("Выполнено", size=10,
                                                    color=GREEN,
                                                    weight=ft.FontWeight.W_600),
                                )] if is_done else []),
                            ],
                        ),
                        ft.Text(
                            f"{format_rub(goal.current_cents)} ₽  /  "
                            f"{format_rub(goal.target_cents)} ₽"
                            + (f"  ·  {deadline_str}" if deadline_str else ""),
                            color=TEXT_MUTED, size=12,
                        ),
                        ft.ProgressBar(
                            value=ratio, color=color,
                            bgcolor=ft.Colors.with_opacity(0.12, color),
                            bar_height=6, border_radius=3,
                        ),
                    ],
                ),
                ft.Row(
                    spacing=0,
                    controls=[
                        ft.IconButton(
                            ft.Icons.ADD_CIRCLE_OUTLINE, icon_color=GREEN,
                            tooltip="Пополнить", icon_size=20,
                            on_click=lambda _, g=goal: _deposit_dialog(
                                page, repos, g, on_refresh),
                        ),
                        ft.IconButton(
                            ft.Icons.EDIT_OUTLINED, icon_color=TEXT_MUTED,
                            tooltip="Редактировать", icon_size=20,
                            on_click=lambda _, g=goal: _goal_dialog(
                                page, repos, on_refresh, g),
                        ),
                        ft.IconButton(
                            ft.Icons.DELETE_OUTLINE, icon_color=TEXT_MUTED,
                            tooltip="Удалить", icon_size=20,
                            on_click=do_delete,
                        ),
                    ],
                ),
            ],
        ),
    )


def _summary_banner(goals: list[Goal], page: ft.Page) -> ft.Container:
    total = len(goals)
    done = sum(1 for g in goals if g.progress_ratio >= 1.0)
    total_target = sum(g.target_cents for g in goals)
    total_current = sum(g.current_cents for g in goals)
    overall = min(1.0, total_current / total_target) if total_target else 0.0

    bg = "#1A2E1A" if page.theme_mode == ft.ThemeMode.DARK else GREEN_SOFT
    return ft.Container(
        bgcolor=bg, border_radius=16, padding=20,
        content=ft.Row(
            spacing=0,
            controls=[
                ft.Column(
                    spacing=4, expand=True,
                    controls=[
                        ft.Text(
                            f"{done} из {total} {'цели' if 2 <= total % 10 <= 4 and total % 100 not in range(11, 20) else 'целей'} достигнуто",
                            size=16, weight=ft.FontWeight.W_700, color=GREEN,
                        ),
                        ft.Text(
                            f"Накоплено {format_rub(total_current)} ₽"
                            f" из {format_rub(total_target)} ₽",
                            size=12, color=TEXT_MUTED,
                        ),
                        ft.Container(height=4),
                        ft.ProgressBar(
                            value=overall, color=GREEN,
                            bgcolor=ft.Colors.with_opacity(0.2, GREEN),
                            bar_height=8, border_radius=4,
                        ),
                    ],
                ),
                ft.Container(width=20),
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                    controls=[
                        ft.Text(f"{int(overall * 100)}%",
                                size=32, weight=ft.FontWeight.W_700, color=GREEN),
                        ft.Text("общий\nпрогресс", size=10, color=TEXT_MUTED,
                                text_align=ft.TextAlign.CENTER),
                    ],
                ),
            ],
        ),
    )


def build_goals(
    page: ft.Page,
    repos: Repos,
    navigate: Callable[[str], None],
    rebuild: Callable[[], None],
    on_theme_toggle: Callable[[Any], None],
) -> ft.Control:
    goals = repos.goal.list_all()

    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("Финансовые цели", size=22, weight=ft.FontWeight.W_700),
            ft.FilledButton(
                "Новая цель", icon=ft.Icons.ADD,
                on_click=lambda _: _goal_dialog(page, repos, rebuild),
                style=ft.ButtonStyle(bgcolor=GREEN, color=ft.Colors.WHITE),
            ),
        ],
    )

    if not goals:
        body: list[ft.Control] = [
            empty_state(
                "Целей пока нет.\n"
                "Нажмите «Новая цель», задайте сумму и следите за прогрессом.",
                ft.Icons.FLAG_OUTLINED,
            )
        ]
    else:
        body = [
            _summary_banner(goals, page),
            *[_goal_card(page, repos, g, rebuild) for g in goals],
        ]

    content = ft.Column(
        spacing=16, expand=True, scroll=ft.ScrollMode.AUTO,
        controls=[header, *body],
    )

    return ft.Row(
        expand=True,
        controls=[
            build_sidebar(page, "goals", navigate, on_theme_toggle),
            ft.Container(content=content, expand=True, padding=24,
                         bgcolor=page_bgcolor(page)),
        ],
    )
