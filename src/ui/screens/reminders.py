from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from src.infra.db.connection import transaction
from src.infra.db.repositories import ReminderRepository
from src.ui.cards import ReminderRowCard
from src.ui.factories import (
    empty_state_label,
    style_popup,
    ui_button,
    ui_error_label,
    ui_spinner,
    ui_text_input,
)
from src.ui.formatting import RECURRENCE_LABELS, RECURRENCE_UI_TO_VALUE, parse_money
from src.ui.theme import COL_BORDER, COL_TEXT, FS_TITLE
from src.ui.widgets import ModalSheet


def build_reminders_popup(
    *,
    conn: sqlite3.Connection,
    reminder_repo: ReminderRepository,
) -> None:
    shell = ModalSheet(size_hint=(1, 1))
    header = BoxLayout(orientation="horizontal", size_hint_y=None, height=48, spacing=10)
    title = Label(text="Напоминания о платежах", color=COL_TEXT, font_size=FS_TITLE - 2,
                  bold=True, halign="left", valign="middle", size_hint_x=1)
    title.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
    header.add_widget(title)
    add_btn = ui_button("Новое", width=110, accent=True)
    header.add_widget(add_btn)
    shell.add_widget(header)

    list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=10)
    list_box.bind(minimum_height=list_box.setter("height"))

    def refresh_list() -> None:
        list_box.clear_widgets()
        items = reminder_repo.list_due_sorted()
        if not items:
            list_box.add_widget(empty_state_label(
                "Список пуст. Добавьте дату платежа и при необходимости повтор — приложение "
                "подсветит просроченные записи."
            ))
            return
        now = datetime.now(UTC)
        for r in items:
            list_box.add_widget(
                ReminderRowCard(r, now=now, on_done=mark_done, on_delete=delete_reminder)
            )

    def mark_done(reminder_id: int) -> None:
        with transaction(conn):
            reminder_repo.mark_done(reminder_id=reminder_id)
        refresh_list()

    def delete_reminder(reminder_id: int) -> None:
        with transaction(conn):
            reminder_repo.delete(reminder_id=reminder_id)
        refresh_list()

    def open_editor() -> None:
        form = BoxLayout(orientation="vertical", spacing=10, padding=(2, 4))
        name_in = ui_text_input("Название")
        due_in = ui_text_input("Дата и время: YYYY-MM-DD HH:MM")
        recurrence_in = ui_spinner(text=RECURRENCE_LABELS[0], values=list(RECURRENCE_LABELS))
        amount_in = ui_text_input("Сумма (необязательно)")
        note_in = ui_text_input("Заметка (необязательно)")
        err = ui_error_label()

        form.add_widget(name_in)
        form.add_widget(due_in)
        form.add_widget(recurrence_in)
        form.add_widget(amount_in)
        form.add_widget(note_in)
        form.add_widget(err)

        def on_save(*_a) -> None:
            try:
                name = name_in.text.strip()
                if not name:
                    raise ValueError("Введите название")
                due_text = due_in.text.strip()
                if not due_text:
                    raise ValueError("Введите дату/время")
                due_dt = datetime.strptime(due_text, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
                recurrence = RECURRENCE_UI_TO_VALUE.get(recurrence_in.text, "none")
                amount_text = amount_in.text.strip()
                amount_cents = parse_money(amount_text) if amount_text else None
                note = note_in.text.strip() or None
                with transaction(conn):
                    reminder_repo.create(name=name, due_at=due_dt,
                                         recurrence=recurrence,
                                         amount_cents=amount_cents, note=note)
                editor.dismiss()
                refresh_list()
            except Exception as exc:
                err.text = str(exc)

        save_btn = ui_button("Сохранить", accent=True)
        save_btn.bind(on_release=on_save)
        form.add_widget(save_btn)

        editor_sheet = ModalSheet(size_hint=(1, 1))
        editor_sheet.add_widget(form)
        editor = Popup(title="Новое напоминание", content=editor_sheet, size_hint=(0.9, 0.88))
        style_popup(editor)
        editor.open()

    add_btn.bind(on_release=lambda *_: open_editor())
    refresh_list()

    scroll = ScrollView(size_hint=(1, 1), bar_width=5,
                        bar_color=(*COL_BORDER[:3], 0.45),
                        bar_inactive_color=(*COL_BORDER[:3], 0.15),
                        scroll_type=["bars", "content"])
    scroll.add_widget(list_box)
    shell.add_widget(scroll)
    popup = Popup(title="Напоминания", content=shell, size_hint=(0.94, 0.9))
    style_popup(popup)
    popup.open()
