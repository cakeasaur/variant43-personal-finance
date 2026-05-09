from __future__ import annotations

from datetime import UTC, datetime

from kivy.uix.boxlayout import BoxLayout

from src.ui.factories import ui_button, ui_error_label, ui_spinner, ui_text_input


class AddTransactionForm(BoxLayout):
    def __init__(self, on_submit, categories: list[tuple[int, str]], **kwargs):
        super().__init__(orientation="vertical", spacing=10, padding=12, **kwargs)
        self._on_submit = on_submit

        self.amount = ui_text_input("Сумма (например 199.90)")
        self.add_widget(self.amount)

        self.kind = ui_spinner(text="Расход", values=["Расход", "Доход"])
        self.add_widget(self.kind)

        self.category = ui_spinner(
            text="Без категории",
            values=["Без категории"] + [name for _, name in categories],
        )
        self._category_map = {name: cid for cid, name in categories}
        self.add_widget(self.category)

        self.note = ui_text_input("Заметка (опционально)")
        self.add_widget(self.note)

        self.error_label = ui_error_label()
        self.add_widget(self.error_label)

        submit = ui_button("Сохранить", accent=True)
        submit.bind(on_release=lambda *_: self._submit())
        self.add_widget(submit)

    def set_error(self, text: str) -> None:
        self.error_label.text = text

    def _submit(self) -> None:
        self._on_submit(
            amount_text=self.amount.text.strip(),
            kind=self.kind.text,
            category_name=self.category.text,
            note=self.note.text.strip() or None,
            occurred_at=datetime.now(UTC),
        )
