from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import flet as ft

from ...core.models import Transaction, TransactionType
from ...core.reporting import totals_for_period
from ...infra.db.connection import transaction as db_tx
from ...ui.formatting import (
    KIND_UI_TO_KIND,
    format_rub,
    month_bounds_utc,
    month_title_ru,
    parse_money,
)
from ..components import (
    build_sidebar,
    card_container,
    close_dialog,
    empty_state,
    metric_card,
    open_dialog,
    tx_row,
)
from ..state import Repos
from ..theme import BLUE_SOFT, GREEN, GREEN_SOFT, PURPLE, RED, RED_SOFT, TEXT_MUTED, page_bgcolor


def _add_tx_dialog(
    page: ft.Page,
    repos: Repos,
    on_saved: Callable[[], None],
) -> None:
    cats = repos.cat.list_all()
    cat_options = [ft.dropdown.Option("Без категории")] + [
        ft.dropdown.Option(c.name) for c in cats
    ]
    cat_map = {c.name: c.id for c in cats}

    amount_field = ft.TextField(
        label="Сумма (₽)", keyboard_type=ft.KeyboardType.NUMBER,
        autofocus=True, border_radius=10,
    )
    type_radio = ft.RadioGroup(
        value="expense",
        content=ft.Row([
            ft.Radio(value="expense", label="Расход"),
            ft.Radio(value="income", label="Доход"),
        ]),
    )
    cat_dd = ft.Dropdown(label="Категория", options=cat_options, value="Без категории",
                         border_radius=10)
    note_field = ft.TextField(label="Заметка (необязательно)", border_radius=10)
    date_field = ft.TextField(
        label="Дата и время (ГГГГ-ММ-ДД ЧЧ:ММ)",
        value=datetime.now(UTC).strftime("%Y-%m-%d %H:%M"),
        border_radius=10,
    )
    err_text = ft.Text("", color=RED, size=12)

    def do_save(_: ft.ControlEvent) -> None:
        err_text.value = ""
        try:
            amount_cents = parse_money(amount_field.value or "")
            if amount_cents <= 0:
                raise ValueError("Сумма должна быть > 0")
            kind = KIND_UI_TO_KIND.get(
                "Доход" if type_radio.value == "income" else "Расход", type_radio.value
            )
            cat_id = cat_map.get(cat_dd.value) if cat_dd.value != "Без категории" else None
            occurred = datetime.strptime(
                (date_field.value or "").strip(), "%Y-%m-%d %H:%M"
            ).replace(tzinfo=UTC)
            t = Transaction(
                type=TransactionType(kind),
                amount_cents=amount_cents,
                occurred_at=occurred,
                category_id=cat_id,
                note=note_field.value.strip() or None,
            )
            with db_tx(repos.tx.conn):
                repos.tx.create(t)
            close_dialog(page, dlg)
            on_saved()
        except ValueError as exc:
            err_text.value = str(exc)
            page.update()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text("Новая операция"),
        content=ft.Container(
            width=400,
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    ft.Text("Тип операции", size=13, color=TEXT_MUTED),
                    type_radio,
                    amount_field,
                    cat_dd,
                    note_field,
                    date_field,
                    err_text,
                ],
            ),
        ),
        actions=[
            ft.TextButton("Отмена", on_click=lambda _: close_dialog(page, dlg)),
            ft.FilledButton("Сохранить", on_click=do_save),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    open_dialog(page, dlg)


def build_operations(
    page: ft.Page,
    repos: Repos,
    state: dict,
    navigate: Callable[[str], None],
    rebuild: Callable[[], None],
    on_theme_toggle: Callable[[Any], None],
) -> ft.Control:
    current_month: datetime = state.setdefault("ops_month", datetime.now(UTC))
    current_filter: str = state.setdefault("ops_filter", "all")

    start, end = month_bounds_utc(current_month)
    all_stored = repos.tx.list_between(start=start, end=end)

    if current_filter == "income":
        stored = [s for s in all_stored if s.transaction.type == TransactionType.INCOME]
    elif current_filter == "expense":
        stored = [s for s in all_stored if s.transaction.type == TransactionType.EXPENSE]
    else:
        stored = all_stored

    txs = [s.transaction for s in all_stored]
    totals = totals_for_period(txs, start=start, end=end)
    categories = {c.id: c.name for c in repos.cat.list_all()}

    def prev_month(_: ft.ControlEvent) -> None:
        dt = state["ops_month"]
        state["ops_month"] = (
            datetime(dt.year - 1, 12, 1, tzinfo=UTC) if dt.month == 1
            else datetime(dt.year, dt.month - 1, 1, tzinfo=UTC)
        )
        rebuild()

    def next_month(_: ft.ControlEvent) -> None:
        dt = state["ops_month"]
        state["ops_month"] = (
            datetime(dt.year + 1, 1, 1, tzinfo=UTC) if dt.month == 12
            else datetime(dt.year, dt.month + 1, 1, tzinfo=UTC)
        )
        rebuild()

    def on_filter_change(e: ft.ControlEvent) -> None:
        mapping = {"Все": "all", "Доходы": "income", "Расходы": "expense"}
        state["ops_filter"] = mapping.get(e.control.value, "all")
        rebuild()

    def delete_tx(tx_id: int) -> None:
        with db_tx(repos.tx.conn):
            repos.tx.delete(tx_id=tx_id)
        rebuild()

    balance_color = GREEN if totals.balance_cents >= 0 else RED
    filter_value = {"all": "Все", "income": "Доходы", "expense": "Расходы"}.get(
        current_filter, "Все"
    )

    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text("Операции", size=22, weight=ft.FontWeight.W_700),
            ft.Row(spacing=8, controls=[
                ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=prev_month,
                              icon_color=TEXT_MUTED),
                ft.Text(month_title_ru(current_month), size=14,
                        weight=ft.FontWeight.W_600),
                ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=next_month,
                              icon_color=TEXT_MUTED),
            ]),
            ft.Row(spacing=10, controls=[
                ft.Dropdown(
                    value=filter_value,
                    options=[ft.dropdown.Option(v) for v in ("Все", "Доходы", "Расходы")],
                    on_select=on_filter_change,
                    width=130, border_radius=10,
                ),
                ft.FilledButton(
                    "Добавить",
                    icon=ft.Icons.ADD,
                    on_click=lambda _: _add_tx_dialog(page, repos, rebuild),
                    style=ft.ButtonStyle(bgcolor=GREEN, color=ft.Colors.WHITE),
                ),
            ]),
        ],
    )

    metric_row = ft.Row(
        spacing=16,
        controls=[
            metric_card(page, "Доходы", f"{format_rub(totals.income_cents)} ₽",
                        "", GREEN, ft.Icons.TRENDING_UP, GREEN_SOFT),
            metric_card(page, "Расходы", f"{format_rub(totals.expense_cents)} ₽",
                        "", RED, ft.Icons.TRENDING_DOWN, RED_SOFT),
            metric_card(page, "Баланс", f"{format_rub(totals.balance_cents)} ₽",
                        "", balance_color, ft.Icons.ACCOUNT_BALANCE_WALLET, GREEN_SOFT),
            metric_card(page, "Операций", str(len(all_stored)),
                        f"показано: {len(stored)}", PURPLE, ft.Icons.RECEIPT_LONG, BLUE_SOFT),
        ],
    )

    def _tx_item(s) -> ft.Container:
        def _on_delete(_: ft.ControlEvent, _id: int = s.id) -> None:
            delete_tx(_id)

        row = tx_row(s.transaction, categories.get(s.transaction.category_id))
        row.content.controls.append(
            ft.IconButton(
                ft.Icons.DELETE_OUTLINE, icon_color=TEXT_MUTED,
                icon_size=18, on_click=_on_delete,
                tooltip="Удалить",
            )
        )
        return ft.Container(
            content=row,
            border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.06, TEXT_MUTED))),
        )

    tx_list = card_container(
        page,
        ft.Column(
            spacing=0,
            controls=(
                [empty_state("Операций за этот период нет.\nНажмите «Добавить», чтобы создать первую.")]
                if not stored else
                [_tx_item(s) for s in stored]
            ),
        ),
    )

    content = ft.Column(
        spacing=16, expand=True, scroll=ft.ScrollMode.AUTO,
        controls=[header, metric_row, tx_list],
    )

    return ft.Row(
        expand=True,
        controls=[
            build_sidebar(page, "operations", navigate, on_theme_toggle),
            ft.Container(content=content, expand=True, padding=24,
                         bgcolor=page_bgcolor(page)),
        ],
    )
