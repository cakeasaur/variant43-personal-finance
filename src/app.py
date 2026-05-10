from __future__ import annotations

import atexit
import glob
import logging
import os
import tempfile
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from src.infra.db.connection import connect, transaction
from src.infra.db.repositories import CategoryRepository, TransactionRepository
from src.infra.db.schema import init_schema
from src.infra.security.crypto import (
    MIN_PASSPHRASE_LEN,
    InvalidPasswordError,
    decrypt_file_to_path,
    encrypt_file_to_path,
)
from src.ui.factories import style_popup, ui_button, ui_error_label, ui_label, ui_text_input
from src.ui.screens.overview import RootView
from src.ui.theme import (
    COL_BG,
    DATA_DIR,
    ENCRYPTED_DB_PATH,
    FONT_ICONS,
    PLAINTEXT_DB_PATH,
)
from src.ui.widgets import ModalSheet


def encryption_enabled() -> bool:
    if str(os.environ.get("PF_DISABLE_ENCRYPTION", "")).strip() in {"1", "true", "yes", "on"}:
        return False
    try:
        from kivy.utils import platform
        if platform == "android":
            return False
    except Exception:
        pass
    return True


def _cleanup_orphaned_plaintext_dbs() -> None:
    pattern = os.path.join(tempfile.gettempdir(), "pfm_*.sqlite3")
    for leftover in glob.glob(pattern):
        try:
            os.unlink(leftover)
        except Exception:
            pass


def _new_temp_plaintext_db_path() -> Path:
    fd, p = tempfile.mkstemp(prefix="pfm_", suffix=".sqlite3")
    try:
        os.close(fd)
    except Exception:
        pass
    path = Path(p)
    atexit.register(_remove_file_best_effort, path)
    return path


def _remove_file_best_effort(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


class PersonalFinanceApp(App):
    title = "Личные финансы"

    def build(self):
        LabelBase.register("MaterialIcons", FONT_ICONS)
        Window.clearcolor = COL_BG
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _cleanup_orphaned_plaintext_dbs()
        self._passphrase: str | None = None
        self._conn = None
        self._runtime_db_path: Path | None = None

        root = BoxLayout(orientation="vertical", padding=0, spacing=0)
        root.add_widget(Label(text="Загрузка…", size_hint_y=None, height=40))
        Clock.schedule_once(lambda *_: self._prompt_password_and_unlock(root), 0)
        return root

    def _prompt_password_and_unlock(self, root: BoxLayout) -> None:
        first_run = not ENCRYPTED_DB_PATH.exists()

        content = BoxLayout(orientation="vertical", spacing=10, padding=12)
        err = ui_error_label()

        if first_run:
            content.add_widget(ui_label(
                "Первый запуск: придумайте пароль для шифрования локальной БД.\n"
                "Пароль не восстанавливается — сохраните его.",
                height=56, muted=True,
            ))
            pwd = ui_text_input("Новый пароль", password=True)
            pwd2 = ui_text_input("Повторите пароль", password=True)
            content.add_widget(pwd)
            content.add_widget(pwd2)
        else:
            content.add_widget(ui_label("Введите пароль для шифрования локальной БД.",
                                        height=40, muted=True))
            pwd = ui_text_input("Пароль для БД", password=True)
            pwd2 = None
            content.add_widget(pwd)

        content.add_widget(err)

        btn_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=40, spacing=8)
        unlock_btn = ui_button("Открыть", accent=True)
        exit_btn = ui_button("Выход")
        btn_row.add_widget(unlock_btn)
        btn_row.add_widget(exit_btn)
        content.add_widget(btn_row)

        sheet = ModalSheet(size_hint=(1, 1))
        sheet.add_widget(content)
        popup = Popup(
            title="Создание пароля" if first_run else "Разблокировка БД",
            content=sheet,
            size_hint=(0.9, 0.62 if first_run else 0.52),
            auto_dismiss=False,
        )
        style_popup(popup)

        def do_exit(*_a) -> None:
            popup.dismiss()
            self.stop()

        def _cleanup_runtime_db() -> None:
            try:
                if self._runtime_db_path and self._runtime_db_path != PLAINTEXT_DB_PATH:
                    self._runtime_db_path.unlink(missing_ok=True)
            except Exception:
                pass

        def do_unlock(*_a) -> None:
            try:
                passphrase = pwd.text
                if encryption_enabled():
                    if not passphrase:
                        raise ValueError("Введите пароль")
                    if first_run:
                        if pwd2 is None:
                            raise ValueError("Повторите пароль")
                        if pwd2.text != passphrase:
                            raise ValueError("Пароли не совпадают")
                        if len(passphrase) < MIN_PASSPHRASE_LEN:
                            raise ValueError(
                                f"Слишком короткий пароль (минимум {MIN_PASSPHRASE_LEN} символов)"
                            )
                    runtime_db = _new_temp_plaintext_db_path()
                    self._runtime_db_path = runtime_db
                    if ENCRYPTED_DB_PATH.exists():
                        decrypt_file_to_path(encrypted_path=ENCRYPTED_DB_PATH,
                                             passphrase=passphrase, out_path=runtime_db)
                else:
                    passphrase = ""
                    runtime_db = PLAINTEXT_DB_PATH
                    self._runtime_db_path = runtime_db

                conn = connect(runtime_db)
                init_schema(conn)
                cat_repo = CategoryRepository(conn)
                tx_repo = TransactionRepository(conn)
                with transaction(conn):
                    cat_repo.ensure_defaults()

                self._passphrase = passphrase
                self._conn = conn

                root.clear_widgets()
                root.add_widget(RootView(conn, tx_repo, cat_repo))
                popup.dismiss()
            except InvalidPasswordError:
                err.text = "Неверный пароль (или файл БД повреждён)."
                _cleanup_runtime_db()
            except Exception as exc:
                err.text = str(exc)
                _cleanup_runtime_db()

        unlock_btn.bind(on_release=do_unlock)
        exit_btn.bind(on_release=do_exit)
        popup.open()

    def on_stop(self):
        conn = getattr(self, "_conn", None)
        passphrase = getattr(self, "_passphrase", None)
        runtime_db = getattr(self, "_runtime_db_path", None) or PLAINTEXT_DB_PATH
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        if encryption_enabled() and passphrase and runtime_db.exists():
            try:
                encrypt_file_to_path(plaintext_path=runtime_db, passphrase=passphrase,
                                     out_path=ENCRYPTED_DB_PATH)
                runtime_db.unlink(missing_ok=True)
            except Exception:
                logging.exception("Failed to encrypt DB on exit — data may not be saved")


if __name__ == "__main__":
    PersonalFinanceApp().run()
