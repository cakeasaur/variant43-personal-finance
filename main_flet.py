"""Flet entrypoint для приложения «Личные финансы».

    py -3.12 main_flet.py

При первом запуске предложит придумать пароль → создаст зашифрованную БД.
При последующих — расшифрует БД во временный файл, по закрытию перешифрует обратно.
Отключить шифрование (для отладки): PF_DISABLE_ENCRYPTION=1 py -3.12 main_flet.py
"""

from __future__ import annotations

import atexit
import glob
import os
import sys
import tempfile
from pathlib import Path

import flet as ft

from src.infra.db.connection import connect
from src.infra.db.connection import transaction as db_tx
from src.infra.db.repositories import (
    CategoryRepository,
    GoalRepository,
    ReminderRepository,
    TransactionRepository,
)
from src.infra.db.schema import init_schema
from src.infra.security.crypto import (
    MIN_PASSPHRASE_LEN,
    InvalidPasswordError,
    decrypt_file_to_path,
    encrypt_file_to_path,
)
from src.ui_flet.components import close_dialog, open_dialog
from src.ui_flet.screens.categories import build_categories
from src.ui_flet.screens.goals import build_goals
from src.ui_flet.screens.operations import build_operations
from src.ui_flet.screens.overview import build_overview
from src.ui_flet.screens.reminders import build_reminders
from src.ui_flet.screens.reports import build_reports
from src.ui_flet.screens.settings import build_settings
from src.ui_flet.state import Repos
from src.ui_flet.theme import (
    ENCRYPTED_DB_PATH,
    GREEN,
    PLAINTEXT_DB_PATH,
    RED,
    page_bgcolor,
)

# ── шифрование ────────────────────────────────────────────────────────────

def encryption_enabled() -> bool:
    if str(os.environ.get("PF_DISABLE_ENCRYPTION", "")).strip() in {"1", "true", "yes", "on"}:
        return False
    return True


def _cleanup_orphaned_dbs() -> None:
    for leftover in glob.glob(os.path.join(tempfile.gettempdir(), "pfm_*.sqlite3")):
        try:
            os.unlink(leftover)
        except Exception:
            pass


def _new_temp_db() -> Path:
    fd, p = tempfile.mkstemp(prefix="pfm_", suffix=".sqlite3")
    os.close(fd)
    return Path(p)



# ── основной entrypoint ───────────────────────────────────────────────────

def main(page: ft.Page) -> None:
    page.title = "Finance"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window.width = 1280
    page.window.height = 820

    _cleanup_orphaned_dbs()

    # изменяемое состояние приложения — переживает rebuild()
    app_state: dict = {}
    ctx: dict = {"repos": None, "passphrase": "", "runtime_db": None}

    def rebuild() -> None:
        if ctx["repos"] is None:
            return
        repos: Repos = ctx["repos"]
        route: str = app_state.get("route", "overview")
        page.controls.clear()
        page.bgcolor = page_bgcolor(page)
        page.add(_build_route(route, repos))
        page.update()

    def navigate(route: str) -> None:
        app_state["route"] = route
        rebuild()

    def on_theme_toggle(_e: ft.ControlEvent) -> None:
        page.theme_mode = (
            ft.ThemeMode.DARK if page.theme_mode == ft.ThemeMode.LIGHT
            else ft.ThemeMode.LIGHT
        )
        rebuild()

    def change_password(old: str, new: str) -> str | None:
        if old != ctx["passphrase"]:
            return "Неверный текущий пароль"
        ctx["passphrase"] = new
        return None

    def _build_route(route: str, repos: Repos) -> ft.Control:
        if route == "overview":
            return build_overview(page, repos, navigate, on_theme_toggle)
        if route == "operations":
            return build_operations(page, repos, app_state, navigate, rebuild, on_theme_toggle)
        if route == "goals":
            return build_goals(page, repos, navigate, rebuild, on_theme_toggle)
        if route == "reminders":
            return build_reminders(page, repos, navigate, rebuild, on_theme_toggle)
        if route == "reports":
            return build_reports(page, repos, app_state, navigate, rebuild, on_theme_toggle)
        if route == "categories":
            return build_categories(page, repos, navigate, rebuild, on_theme_toggle)
        if route == "settings":
            return build_settings(
                page, navigate, on_theme_toggle,
                on_change_password=change_password if encryption_enabled() else None,
            )
        return build_overview(page, repos, navigate, on_theme_toggle)

    # ── диалог пароля ───────────────────────────────────────────────────

    def show_password_dialog() -> None:
        first_run = not ENCRYPTED_DB_PATH.exists() and encryption_enabled()

        err = ft.Text("", color=RED, size=12)
        pwd = ft.TextField(
            label="Новый пароль" if first_run else "Пароль для БД",
            password=True, can_reveal_password=True,
            autofocus=True, border_radius=10,
        )
        pwd2 = ft.TextField(
            label="Повторите пароль",
            password=True, can_reveal_password=True,
            border_radius=10,
            visible=first_run,
        )
        hint = ft.Text(
            ("Первый запуск: придумайте пароль для шифрования локальной БД.\n"
             "Пароль не восстанавливается — сохраните его!")
            if first_run else
            "Введите пароль для расшифровки локальной БД.",
            color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
            size=13,
        )

        def do_unlock(_: ft.ControlEvent) -> None:
            err.value = ""
            try:
                passphrase = pwd.value or ""
                if encryption_enabled():
                    if not passphrase:
                        raise ValueError("Введите пароль")
                    if first_run:
                        if pwd2.value != passphrase:
                            raise ValueError("Пароли не совпадают")
                        if len(passphrase) < MIN_PASSPHRASE_LEN:
                            raise ValueError(
                                f"Пароль слишком короткий (минимум {MIN_PASSPHRASE_LEN} символов)"
                            )
                    runtime_db = _new_temp_db()
                    if ENCRYPTED_DB_PATH.exists():
                        decrypt_file_to_path(
                            encrypted_path=ENCRYPTED_DB_PATH,
                            passphrase=passphrase,
                            out_path=runtime_db,
                        )
                else:
                    passphrase = ""
                    runtime_db = PLAINTEXT_DB_PATH

                conn = connect(runtime_db)
                init_schema(conn)
                repos = Repos(
                    cat=CategoryRepository(conn),
                    tx=TransactionRepository(conn),
                    goal=GoalRepository(conn),
                    reminder=ReminderRepository(conn),
                )
                with db_tx(conn):
                    repos.cat.ensure_defaults()

                ctx["repos"] = repos
                ctx["passphrase"] = passphrase
                ctx["runtime_db"] = runtime_db

                close_dialog(page, dlg)
                app_state["route"] = "overview"
                rebuild()

            except InvalidPasswordError:
                err.value = "Неверный пароль (или файл БД повреждён)."
                page.update()
            except ValueError as exc:
                err.value = str(exc)
                page.update()

        def do_exit(_: ft.ControlEvent) -> None:
            page.window.close()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Создание пароля" if first_run else "Разблокировка БД"),
            content=ft.Container(
                width=380,
                content=ft.Column(
                    tight=True, spacing=12,
                    controls=[hint, pwd, *([] if not first_run else [pwd2]), err],
                ),
            ),
            actions=[
                ft.TextButton("Выход", on_click=do_exit),
                ft.FilledButton(
                    "Открыть",
                    on_click=do_unlock,
                    style=ft.ButtonStyle(bgcolor=GREEN, color=ft.Colors.WHITE),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.bgcolor = page_bgcolor(page)
        page.update()
        open_dialog(page, dlg)

    # ── закрытие: перешифровать БД ────────────────────────────────────────
    # Используем idempotent функцию + atexit (надёжнее window-event в Flet 0.85)
    encrypted_flag = {"done": False}

    def shutdown_encrypt() -> None:
        if encrypted_flag["done"]:
            return
        encrypted_flag["done"] = True

        repos = ctx.get("repos")
        passphrase = ctx.get("passphrase", "")
        runtime_db = ctx.get("runtime_db")

        print(f"[shutdown] repos={repos is not None} "
              f"passphrase={'set' if passphrase else 'empty'} "
              f"runtime_db={runtime_db}", file=sys.stderr)

        if repos is not None:
            try:
                repos.tx.conn.close()
            except Exception as exc:
                print(f"[shutdown] conn.close error: {exc}", file=sys.stderr)

        if not (encryption_enabled() and passphrase and runtime_db):
            print("[shutdown] skipping encryption (no passphrase or disabled)",
                  file=sys.stderr)
            return
        if not runtime_db.exists():
            print(f"[shutdown] runtime_db missing: {runtime_db}", file=sys.stderr)
            return

        try:
            ENCRYPTED_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            encrypt_file_to_path(
                plaintext_path=runtime_db,
                passphrase=passphrase,
                out_path=ENCRYPTED_DB_PATH,
            )
            runtime_db.unlink(missing_ok=True)
            print(f"[shutdown] encrypted DB saved to {ENCRYPTED_DB_PATH}",
                  file=sys.stderr)
        except Exception as exc:
            print(f"[shutdown] ENCRYPTION FAILED: {exc!r}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

    atexit.register(shutdown_encrypt)

    def on_window_event(e: ft.WindowEvent) -> None:
        if e.type != ft.WindowEventType.CLOSE.value:
            return
        shutdown_encrypt()
        page.window.destroy()

    page.window.prevent_close = True
    page.window.on_event = on_window_event

    if encryption_enabled():
        show_password_dialog()
    else:
        # шифрование выключено — сразу открываем plaintext БД
        conn = connect(PLAINTEXT_DB_PATH)
        init_schema(conn)
        repos = Repos(
            cat=CategoryRepository(conn),
            tx=TransactionRepository(conn),
            goal=GoalRepository(conn),
            reminder=ReminderRepository(conn),
        )
        with db_tx(conn):
            repos.cat.ensure_defaults()
        ctx["repos"] = repos
        ctx["runtime_db"] = PLAINTEXT_DB_PATH
        app_state["route"] = "overview"
        rebuild()


if __name__ == "__main__":
    ft.app(target=main)
