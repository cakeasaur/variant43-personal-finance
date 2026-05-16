## 4 Реализация

### 4.1 Структура проекта
Код расположен в каталоге `src/` и разделён на уровни:
- `src/core/` — доменные модели и расчёты агрегатов (отчёты); нет внешних зависимостей;
- `src/infra/db/` — подключение SQLite, схема и репозитории;
- `src/infra/security/` — криптография для защиты локальной БД;
- `src/ui_flet/` — UI-слой на Flet: компоненты, тема, экраны.

Точка входа: `main_flet.py` — роутинг, диалог пароля, жизненный цикл шифрования.

### 4.2 Основные сценарии
- **Транзакции**: добавление дохода/расхода, фильтр по типу и месяцу,
  отображение списка и итогов.
- **Отчёты**: расходы по категориям (ProgressBar-ряды) и по дням;
  динамика доходов/расходов на matplotlib-графике (главный экран).
- **Цели**: CRUD целей, атомарное пополнение (`deposit()`), прогресс.
- **Напоминания**: CRUD напоминаний, периодичность (none/daily/weekly/monthly),
  отметка выполнения, подсветка просроченных.
- **Категории**: CRUD категорий с типом (доход/расход/оба).
- **Настройки**: смена пароля (верификация текущего + новый), статус шифрования.

### 4.3 Хранение данных (SQLite)
Инициализация схемы выполняется в `src/infra/db/schema.py`,
доступ к данным — через репозитории в `src/infra/db/repositories.py`.
Схема включает таблицы: `categories`, `transactions`, `goals`, `reminders`, `settings`.

Ключевые решения:
- `isolation_level=None` (autocommit) — нет скрытых транзакций.
- `journal_mode=DELETE` — нет WAL-файлов, plaintext не утекает при краше.
- `amount_cents: int` — суммы в копейках, никаких float.
- Даты как ISO-8601 `TEXT` — лексикографическая сортировка работает корректно.

### 4.4 Защита данных
Реализовано шифрование файла БД:
- контейнер AES-GCM (256-бит), аутентифицирует целостность данных;
- ключ получается из пароля через scrypt (n=2¹⁴, r=8, p=1);
- формат контейнера: MAGIC(4) + salt(16) + nonce(12) + ciphertext;
- ввод пароля при запуске приложения;
- пере-шифрование при завершении (on_window_event + atexit fallback);
- `MIN_PASSPHRASE_LEN = 8` — валидация на уровне crypto-модуля и UI.

### 4.5 Репозиторный слой
Доступ к данным инкапсулирован в четырёх репозиториях:

| Репозиторий | Ключевые методы |
|------------|----------------|
| `CategoryRepository` | `ensure_defaults()`, `list_all()`, `create()`, `update()`, `delete()` |
| `TransactionRepository` | `create()`, `list_between(tx_type?)`, `delete()` |
| `GoalRepository` | `create()`, `get()`, `deposit()`, `update()`, `delete()`, `list_all()` |
| `ReminderRepository` | `create()`, `list_upcoming(within_days)`, `list_due_sorted()`, `mark_done()`, `delete()` |

`GoalRepository.deposit()` выполняет атомарный инкремент с ограничением через
`MIN(target_cents, current_cents + ?)` на уровне SQL.

### 4.6 UI-слой (Flet)
Каждый экран — чистая функция `build_<screen>(page, repos, navigate, ...) → ft.Control`.
Роутинг реализован через `app_state["route"]` + `rebuild()`:
при смене маршрута `page.controls` очищаются и перестраиваются заново.

Переиспользуемые компоненты (`src/ui_flet/components.py`):
`build_sidebar`, `metric_card`, `tx_row`, `empty_state`, `card_container`,
`open_dialog`, `close_dialog`.

### 4.7 Тестирование
Автоматические тесты расположены в `tests/`:

| Файл | Что проверяет |
|------|--------------|
| `test_core_reporting.py` | доменная логика агрегаций (totals, by-category, by-day) |
| `test_crypto.py` | шифрование/дешифрование, неверный пароль, битый заголовок |
| `test_infra_db.py` | репозитории, транзакционность, валидации, граничные случаи |
| `test_smoke.py` | импорт всех слоёв, инициализация схемы |

CI запускает `ruff` (линтер) + `pytest` + `pip-audit` (проверка CVE)
на каждый push через GitHub Actions.
