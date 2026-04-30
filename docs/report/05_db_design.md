## 2 Проектная часть — проектирование базы данных (SQLite)

### 2.6 Общие принципы
- База данных локальная, SQLite.
- Ключевые выборки: по периоду, по типу (доход/расход), по категории.
- Для ускорения отчётов используются индексы по дате и по категории.
- Удаление категорий не должно «ломать» историю: для `transactions.category_id` используется `ON DELETE SET NULL`.

### 2.7 Таблицы (черновая схема)

#### categories
- `id` INTEGER PRIMARY KEY
- `name` TEXT NOT NULL UNIQUE
- `kind` TEXT NOT NULL CHECK(kind IN ('income','expense','both')) DEFAULT 'both'
- `color` TEXT NULL
- `icon` TEXT NULL
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL

#### transactions
- `id` INTEGER PRIMARY KEY
- `type` TEXT NOT NULL CHECK(type IN ('income','expense'))
- `amount_cents` INTEGER NOT NULL CHECK(amount_cents >= 0)
- `occurred_at` TEXT NOT NULL  (ISO-8601)
- `category_id` INTEGER NULL REFERENCES categories(id) ON DELETE SET NULL
- `note` TEXT NULL
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL

Индексы:
- `idx_transactions_occurred_at` по `occurred_at`
- `idx_transactions_category_occurred` по `(category_id, occurred_at)`
- `idx_transactions_type_occurred` по `(type, occurred_at)`

#### goals
- `id` INTEGER PRIMARY KEY
- `name` TEXT NOT NULL
- `target_cents` INTEGER NOT NULL CHECK(target_cents > 0)
- `current_cents` INTEGER NOT NULL DEFAULT 0 CHECK(current_cents >= 0)
- `deadline_at` TEXT NULL
- `note` TEXT NULL
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL

#### reminders
- `id` INTEGER PRIMARY KEY
- `name` TEXT NOT NULL
- `amount_cents` INTEGER NULL CHECK(amount_cents >= 0)
- `due_at` TEXT NOT NULL
- `recurrence` TEXT NOT NULL CHECK(recurrence IN ('none','daily','weekly','monthly')) DEFAULT 'none'
- `note` TEXT NULL
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL

#### settings
- `key` TEXT PRIMARY KEY
- `value` TEXT NOT NULL

Примечание: параметры безопасности (salt, kdf-параметры) могут храниться в `settings`.

### 2.8 Версионирование схемы

В таблице `settings` хранится `schema_version` (текущее значение: `3`).
Значение записывается при инициализации и может использоваться для диагностики
совместимости.

**Ограничения v0.1:** автоматические миграции не реализованы. Таблицы создаются
через `CREATE TABLE IF NOT EXISTS` — существующие данные сохраняются при
добавлении новых таблиц. Однако изменения существующих таблиц (новые столбцы,
изменение типов) требуют ручного сброса БД. Поддержка автоматических миграций
(последовательные SQL-скрипты по версиям) запланирована в backlog v0.2.

