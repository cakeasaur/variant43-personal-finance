from __future__ import annotations

from collections.abc import Callable
from typing import Any

import flet as ft

from ...infra.db.connection import transaction as db_tx
from ...infra.db.repositories import Category
from ..components import build_sidebar, close_dialog, empty_state, open_dialog
from ..state import Repos
from ..theme import GREEN, RED, TEXT_MUTED, page_bgcolor

_KIND_LABELS = {"income": "Доход", "expense": "Расход", "both": "Оба"}
_KIND_COLORS = {"income": "#3B82F6", "expense": RED, "both": TEXT_MUTED}


def _kind_badge(kind: str) -> ft.Container:
    color = _KIND_COLORS.get(kind, TEXT_MUTED)
    label = _KIND_LABELS.get(kind, kind)
    return ft.Container(
        border_radius=20,
        padding=ft.Padding(10, 3, 10, 3),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
    )


def _category_dialog(
    page: ft.Page,
    repos: Repos,
    on_saved: Callable[[], None],
    existing: Category | None = None,
) -> None:
    name_f = ft.TextField(
        label="Название", autofocus=True, border_radius=10,
        value=existing.name if existing else "",
    )
    kind_dd = ft.Dropdown(
        label="Тип операций",
        border_radius=10,
        value=existing.kind if existing else "both",
        options=[
            ft.dropdown.Option(key="both", text="Оба"),
            ft.dropdown.Option(key="income", text="Доход"),
            ft.dropdown.Option(key="expense", text="Расход"),
        ],
    )
    err = ft.Text("", color=RED, size=12)

    def do_save(_: ft.ControlEvent) -> None:
        err.value = ""
        try:
            name = name_f.value.strip()
            if not name:
                raise ValueError("Введите название")
            kind = kind_dd.value or "both"
            with db_tx(repos.cat.conn):
                if existing is None:
                    repos.cat.create(name=name, kind=kind)
                else:
                    repos.cat.update(category_id=existing.id, name=name, kind=kind)
            close_dialog(page, dlg)
            on_saved()
        except Exception as exc:
            err.value = str(exc)
            page.update()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Новая категория" if existing is None else "Редактировать категорию"),
        content=ft.Container(
            width=360,
            content=ft.Column(tight=True, spacing=12, controls=[name_f, kind_dd, err]),
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda _: close_dialog(page, dlg)),
            ft.FilledButton("Сохранить", on_click=do_save),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    open_dialog(page, dlg)


def _category_row(
    page: ft.Page,
    repos: Repos,
    cat: Category,
    on_refresh: Callable[[], None],
) -> ft.Container:
    def do_delete(_: ft.ControlEvent) -> None:
        with db_tx(repos.cat.conn):
            repos.cat.delete(category_id=cat.id)
        on_refresh()

    return ft.Container(
        padding=ft.Padding(0, 10, 0, 10),
        border=ft.Border(
            bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE))
        ),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.LABEL_OUTLINE, size=18, color=TEXT_MUTED),
                ft.Container(width=10),
                ft.Text(cat.name, expand=True, weight=ft.FontWeight.W_500, size=14),
                _kind_badge(cat.kind),
                ft.IconButton(
                    ft.Icons.EDIT_OUTLINED, icon_color=TEXT_MUTED, icon_size=18,
                    tooltip="Редактировать",
                    on_click=lambda _, c=cat: _category_dialog(page, repos, on_refresh, c),
                ),
                ft.IconButton(
                    ft.Icons.DELETE_OUTLINE, icon_color=TEXT_MUTED, icon_size=18,
                    tooltip="Удалить",
                    on_click=do_delete,
                ),
            ],
        ),
    )


def build_categories(
    page: ft.Page,
    repos: Repos,
    navigate: Callable[[str], None],
    rebuild: Callable[[], None],
    on_theme_toggle: Callable[[Any], None],
) -> ft.Control:
    categories = repos.cat.list_all()

    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("Категории", size=22, weight=ft.FontWeight.W_700),
            ft.FilledButton(
                "Новая категория", icon=ft.Icons.ADD,
                on_click=lambda _: _category_dialog(page, repos, rebuild),
                style=ft.ButtonStyle(bgcolor=GREEN, color=ft.Colors.WHITE),
            ),
        ],
    )

    hint = ft.Text(
        "Категории используются при добавлении операций. "
        "Удаление категории не удаляет связанные операции.",
        color=TEXT_MUTED, size=12,
    )

    if not categories:
        body: list[ft.Control] = [
            empty_state("Категорий нет.\nНажмите «Новая категория».", ft.Icons.LABEL_OUTLINE)
        ]
    else:
        body = [
            hint,
            ft.Column(
                spacing=0,
                controls=[_category_row(page, repos, c, rebuild) for c in categories],
            ),
        ]

    content = ft.Column(
        spacing=16, expand=True, scroll=ft.ScrollMode.AUTO,
        controls=[header, *body],
    )

    return ft.Row(
        expand=True,
        controls=[
            build_sidebar(page, "categories", navigate, on_theme_toggle),
            ft.Container(content=content, expand=True, padding=24, bgcolor=page_bgcolor(page)),
        ],
    )
