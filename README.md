## Курсовой проект — Вариант 43: Личные финансы

**Дисциплина**: «Методы и технологии программирования»  
**Вариант**: 43 — Приложение для управления личными финансами  
**Стек**: Python + Kivy + SQLite  

### Краткое описание
Кроссплатформенное мобильное приложение для учёта доходов/расходов:
- Категоризация транзакций
- Визуализация (диаграммы)
- Финансовые цели
- Напоминания о платежах
- Защита данных (шифрование локальной БД)

### Что реализовано
- **UI**: боковая навигация, три карточки метрик, иконки через Material Icons (TTF)
- **Транзакции**: доход/расход, список, фильтр по типу, итоги за текущий месяц
- **Отчёты**: диаграммы расходов по категориям и по дням (текущий месяц)
- **Цели**: создание/редактирование/удаление, прогресс, дедлайн (опционально)
- **Напоминания**: создание/удаление, повторяемость (none/daily/weekly/monthly), отметка «OK»
- **Безопасность**: шифрование файла локальной БД (пароль, scrypt + AES-GCM)
- **Качество**: ruff + pytest + pip-audit, CI в GitHub Actions

### Репозиторные правила (кратко)
- **Ветки**: Git flow (см. `docs/GIT_FLOW.md`)
- **Коммиты**: семантические (см. `docs/COMMIT_CONVENTION.md`)
- **Релизы/теги**: см. `docs/RELEASE_PLAN.md`

### Структура проекта
```
variant43-personal-finance/
  .github/workflows/          # CI (ruff/pytest/pip-audit)
  scripts/                    # служебные скрипты (бенчмарки)
  docs/                       # материалы для пояснительной записки, правила
    report/                   # пояснительная записка (главы)
    diagrams/                 # диаграммы (Mermaid)
  src/
    app.py                    # точка входа: PersonalFinanceApp + startup/crypto
    core/                     # доменная логика (без внешних зависимостей)
      models.py               # Transaction, TransactionType
      reporting.py            # totals_for_period, expense_by_category, expense_by_day
      perf.py                 # бенчмарк-хелперы
    infra/
      db/                     # SQLite: connection, schema, repositories
      security/               # AES-256-GCM шифрование файла БД
    ui/                       # UI-слой (Kivy)
      theme.py                # цвета, иконки, размеры шрифтов, пути к файлам
      formatting.py           # format_rub, parse_money, month_bounds_utc и др.
      factories.py            # фабрики виджетов (ui_button, ui_label, …)
      widgets.py              # ModalSheet, BarTrack, SectionCard, ReportBarRow
      cards.py                # GoalCard, StatCard, Sidebar, TransactionCard и др.
      forms.py                # AddTransactionForm
      screens/
        overview.py           # AppState + RootView (главный экран)
        reports.py            # build_reports_popup()
        goals.py              # build_goals_popup()
        reminders.py          # build_reminders_popup()
  requirements/               # зависимости (app/ci/dev)
```

### Окружение разработки (Блок 0)
- **Python**: целевая версия **3.12** (см. `.python-version`)

У вас может быть установлено несколько Python. Для Windows удобно использовать
`py -3.12`.

### Установка зависимостей (локально)
Создайте venv и установите зависимости:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install -r requirements/app.txt -r requirements/dev.txt
```

### Проверки качества

> **Два профиля зависимостей:**
> - `requirements/app.txt` — полный набор для desktop (Kivy + cryptography + Pillow).
> - `requirements/ci.txt` — облегчённый набор для CI/headless-тестов (только cryptography, **без Kivy**).
>   Именно его использует GitHub Actions, потому что Kivy требует GPU и не устанавливается на headless-серверах.

Локальная проверка (с установленным Kivy):
```powershell
py -3.12 -m ruff check .
py -3.12 -m pytest -q
py -3.12 -m pip_audit -r requirements/app.txt -r requirements/dev.txt
```

CI / headless (без Kivy — те же команды, что выполняет GitHub Actions):
```powershell
py -3.12 -m ruff check .
py -3.12 -m pytest -q
py -3.12 -m pip_audit -r requirements/ci.txt -r requirements/dev.txt
```

### Запуск приложения (desktop)

Основной UI — тёмная тема на Kivy с карточками «Доходы / Расходы / Баланс»,
списком операций с цветными полосами по типу, отчётами, целями и напоминаниями.

Рекомендуемый entrypoint (он же используется для сборки exe и Android):

```powershell
py -3.12 main.py
```

Альтернативно (запустить напрямую через модуль):

```powershell
py -3.12 -m src.app
```

При запуске **на desktop** приложение попросит пароль для локальной БД. Файл БД хранится в `data/` в виде
`personal_finance.sqlite3.enc` и расшифровывается только на время работы приложения.
После добавления операции можно удалить её кнопкой «Удалить» прямо в списке.
Месяц, за который показываются сводка и список операций, переключается
стрелками ‹ › рядом с заголовком месяца.

### Безопасность и важные ограничения
- **Android**: ради воспроизводимой сборки APK шифрование отключено (БД хранится в приватном каталоге приложения).
- **Пароль не восстанавливается**: если забыть пароль, расшифровать `*.enc` нельзя.
- **Plaintext БД**: временный расшифрованный файл создаётся в системной папке temp (`pfm_*.sqlite3`)
  и существует только во время работы приложения. При штатном закрытии выполняется
  пере-шифрование и удаление plaintext-файла (best-effort). При следующем запуске
  любые осиротевшие `pfm_*.sqlite3` из прошлых сессий также удаляются автоматически.
- **Модель угроз (упрощённо)**: защита от чтения данных при копировании файла БД; не покрывает компрометацию ОС.

### Бенчмарк (производительность отчётов)
```powershell
py -3.12 scripts\bench_reporting.py
```

### Скриншоты (для приложений к записке)
Добавляйте скриншоты в `docs/screenshots/` и вставляйте ссылки в текст записки/README.

### Пояснительная записка (структура)
Главы лежат в `docs/report/`:
- `00_introduction.md` — Введение
- `01_domain_analysis.md` — Аналитика предметной области
- `02_analogs.md` — Аналоги
- `03_requirements.md` — Требования
- `04_architecture.md` — Архитектура
- `05_db_design.md` — Проектирование БД
- `06_technology.md` — Технологическая часть
- `07_implementation.md` — Реализация
- `08_testing.md` — Тестирование
- `09_conclusion.md` — Заключение
- `10_references.md` — Литература

### Docker (только для проверок, без GUI)
```powershell
docker compose run --rm checks
```

Контейнер прогоняет те же проверки, что и CI:
- `ruff`
- `pytest`
- `pip-audit`

### Сборка / Deploy
- Windows (exe): `scripts/build_win.ps1`
- Android (структура + инструкция): `buildozer.spec`, `docs/ANDROID.md`
- Общая сводка: `docs/DEPLOYMENT.md`

