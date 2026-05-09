from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from src.infra.db.connection import transaction
from src.infra.db.repositories import GoalRepository
from src.ui.cards import GoalCard
from src.ui.factories import (
    empty_state_label,
    style_popup,
    ui_button,
    ui_error_label,
    ui_text_input,
)
from src.ui.formatting import parse_money
from src.ui.theme import COL_BORDER, COL_MUTED, COL_TEXT, FS_TITLE
from src.ui.widgets import ModalSheet


def build_goals_popup(
    *,
    conn: sqlite3.Connection,
    goal_repo: GoalRepository,
) -> None:
    shell = ModalSheet(size_hint=(1, 1))
    header = BoxLayout(orientation="horizontal", size_hint_y=None, height=48, spacing=10)
    title = Label(text="Финансовые цели", color=COL_TEXT, font_size=FS_TITLE - 2, bold=True,
                  halign="left", valign="middle", size_hint_x=1)
    title.bind(size=lambda inst, _v: setattr(inst, "text_size", (inst.width, None)))
    header.add_widget(title)
    add_btn = ui_button("Новая цель", width=132, accent=True)
    header.add_widget(add_btn)
    shell.add_widget(header)

    list_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=10)
    list_box.bind(minimum_height=list_box.setter("height"))

    def refresh_list() -> None:
        list_box.clear_widgets()
        current = goal_repo.list_all()
        if not current:
            list_box.add_widget(empty_state_label(
                "Целей пока нет. Нажмите «Новая цель», задайте сумму и следите за полосой прогресса."
            ))
            return
        for g in current:
            list_box.add_widget(
                GoalCard(g, on_edit=lambda goal: open_goal_editor(existing=goal),
                         on_delete=delete_goal)
            )

    def delete_goal(goal_id: int) -> None:
        with transaction(conn):
            goal_repo.delete(goal_id=goal_id)
        refresh_list()

    def open_goal_editor(*, existing=None) -> None:
        form = BoxLayout(orientation="vertical", spacing=10, padding=(2, 4))
        name_in = ui_text_input("Название")
        target_in = ui_text_input("Цель (сумма)")
        current_in = ui_text_input("Текущий прогресс (0 если пусто)")
        deadline_in = ui_text_input("Дедлайн YYYY-MM-DD (необязательно)")
        note_in = ui_text_input("Заметка (необязательно)")
        err = ui_error_label()

        if existing is not None:
            name_in.text = existing.name
            target_in.text = f"{existing.target_cents/100:.2f}"
            current_in.text = f"{existing.current_cents/100:.2f}"
            deadline_in.text = existing.deadline_at.date().isoformat() if existing.deadline_at else ""
            note_in.text = existing.note or ""

        form.add_widget(name_in)
        form.add_widget(target_in)
        form.add_widget(current_in)
        form.add_widget(deadline_in)
        form.add_widget(note_in)
        form.add_widget(err)

        def on_save(*_a) -> None:
            try:
                name = name_in.text.strip()
                if not name:
                    raise ValueError("Введите название")
                target_cents = parse_money(target_in.text)
                current_cents = parse_money(current_in.text or "0")
                if target_cents <= 0:
                    raise ValueError("Цель должна быть > 0")
                if current_cents < 0:
                    raise ValueError("Прогресс должен быть >= 0")
                deadline_text = deadline_in.text.strip()
                deadline_dt = None
                if deadline_text:
                    d = date.fromisoformat(deadline_text)
                    deadline_dt = datetime(d.year, d.month, d.day, 0, 0, tzinfo=UTC)
                note = note_in.text.strip() or None

                with transaction(conn):
                    if existing is None:
                        goal_repo.create(name=name, target_cents=target_cents,
                                         current_cents=current_cents,
                                         deadline_at=deadline_dt, note=note)
                    else:
                        goal_repo.update(goal_id=existing.id, name=name,
                                         target_cents=target_cents,
                                         current_cents=current_cents,
                                         deadline_at=deadline_dt, note=note)
                editor.dismiss()
                refresh_list()
            except Exception as exc:
                err.text = str(exc)

        save_btn = ui_button("Сохранить", accent=True)
        save_btn.bind(on_release=on_save)
        form.add_widget(save_btn)

        editor_sheet = ModalSheet(size_hint=(1, 1))
        editor_sheet.add_widget(form)
        editor_title = "Новая цель" if existing is None else "Редактировать цель"
        editor = Popup(title=editor_title, content=editor_sheet, size_hint=(0.9, 0.88))
        style_popup(editor)
        editor.open()

    add_btn.bind(on_release=lambda *_: open_goal_editor(existing=None))
    refresh_list()

    scroll = ScrollView(size_hint=(1, 1), bar_width=5,
                        bar_color=(*COL_BORDER[:3], 0.45),
                        bar_inactive_color=(*COL_BORDER[:3], 0.15),
                        scroll_type=["bars", "content"])
    scroll.add_widget(list_box)
    shell.add_widget(scroll)
    popup = Popup(title="Цели", content=shell, size_hint=(0.94, 0.9))
    style_popup(popup)
    popup.open()
