# AI-инструменты в разработке проекта

> **Инструмент:** Claude (Anthropic) — через интерфейс Claude.ai и Claude Code (CLI)  
> **Проект:** Variant 43 — Personal Finance App  
> **Период:** март–май 2026

В этом файле задокументированы реальные сессии взаимодействия с AI-ассистентом
в ходе разработки проекта. Для каждой сессии указаны: запрос, ключевые решения,
принятые или отклонённые предложения, итоговый код или документ.

---

## Содержание

1. [Выбор стека и архитектуры](#1-выбор-стека-и-архитектуры)
2. [Проектирование доменной модели](#2-проектирование-доменной-модели)
3. [Модуль шифрования (crypto.py)](#3-модуль-шифрования-cryptopy)
4. [Схема БД и индексы](#4-схема-бд-и-индексы)
5. [Слой репозитория и подключение к БД](#5-слой-репозитория-и-подключение-к-бд)
6. [Модуль отчётности (reporting.py)](#6-модуль-отчётности-reportingpy)
7. [Написание тестов](#7-написание-тестов)
8. [Настройка CI (GitHub Actions)](#8-настройка-ci-github-actions)
9. [Исправление ошибок по результатам code review](#9-исправление-ошибок-по-результатам-code-review)
10. [Итоги использования AI](#10-итоги-использования-ai)
11. [Рефакторинг: разбивка app.py и правки по итогам финального ревью](#11-рефакторинг-разбивка-apppy-и-правки-по-итогам-финального-ревью)

---

## 1. Выбор стека и архитектуры

**Инструмент:** Claude.ai (claude-sonnet-4-5)  
**Когда:** начало проекта, март 2026

### Запрос

```
Пишу курсовой проект — приложение для личных финансов на Python.
Требования: кроссплатформенность (мобильные + Desktop), офлайн-first,
шифрование локальной БД, Python 3.12.
Какой GUI-фреймворк выбрать и как структурировать проект?
```

### Что предложил Claude

- **GUI:** Kivy + KivyMD — единственный зрелый Python-фреймворк с реальным
  Android-билдом через Buildozer; PyQt5/6 исключён, т.к. GPL-лицензия
  проблематична для учебных проектов.
- **Архитектура:** трёхслойная — `core` (доменная логика, чистые dataclass),
  `infra` (БД + крипто), `ui` (Kivy-экраны). Зависимости направлены только
  вниз: `ui → core ← infra`.
- **Хранилище:** SQLite через стандартный `sqlite3` — не требует отдельного
  сервера, поддерживается на Android/iOS.
- **Шифрование:** AES-256-GCM + scrypt KDF вместо SQLCipher —
  `pip install cryptography` проще, чем пересобирать SQLite с патчем.

### Что я отклонил

- Предложение использовать SQLAlchemy ORM — избыточно для SQLite-only проекта,
  усложняет Android-билд.
- Предложение `Flet` (Flutter-обёртка) — нет production-опыта Buildozer-билда.

### Итог

Структура `src/core/`, `src/infra/db/`, `src/infra/security/`, `src/ui/`
принята. Зафиксирована в `docs/report/04_architecture.md`.

---

## 2. Проектирование доменной модели

**Инструмент:** Claude Code (CLI, `claude`)  
**Когда:** март 2026  
**Файл:** `src/core/models.py`

### Запрос

```
Помоги спроектировать доменную модель. Нужны: Transaction (доход/расход),
TransactionType (enum). Хочу immutable dataclass, без ORM-зависимостей,
с валидацией суммы.
```

### Диалог

**Я:**
> Стоит ли хранить сумму в float или int?

**Claude:**
> Категорически int (amount_cents). Float вызывает проблемы при сравнении
> и суммировании из-за IEEE 754. Например, 0.1 + 0.2 ≠ 0.3 в float.
> Храни центы (копейки), отображай с делением на 100 только в UI.

**Я:**
> Как правильно сделать валидацию в frozen dataclass?

**Claude:**
> Используй `__post_init__`. Frozen не блокирует его вызов — он выполняется
> сразу после автогенерированного `__init__`.

### Принятые решения

- `amount_cents: int` вместо `float` — предложение Claude, согласился сразу.
- `frozen=True, slots=True` — иммутабельность и экономия памяти.
- Валидация в `__post_init__`: отрицательные и нулевые суммы запрещены.
- `StrEnum` вместо `Enum` — удобнее сериализация в SQLite без `.value`.

### Что скорректировал сам

Claude изначально предложил хранить `amount: Decimal` — заменил на `int`
после обсуждения (проще для SQLite, где нет типа DECIMAL).

### Итоговый фрагмент кода

```python
@dataclass(frozen=True, slots=True)
class Transaction:
    type: TransactionType
    amount_cents: int
    occurred_at: datetime
    category_id: int | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if self.amount_cents < 0:
            raise ValueError("amount_cents must be >= 0")
        if self.amount_cents == 0:
            raise ValueError("amount_cents must be > 0 (zero-amount transactions are not allowed)")
```

---

## 3. Модуль шифрования (crypto.py)

**Инструмент:** Claude.ai  
**Когда:** март 2026  
**Файл:** `src/infra/security/crypto.py`

### Запрос

```
Нужен модуль шифрования SQLite-файла для Python 3.12.
Требования из ТЗ (NFR-05):
- данные не читаются без пароля
- пароль/PIN не хранится в открытом виде
- KDF: PBKDF2/scrypt/argon2

Предложи реализацию с выбором алгоритмов и объясни почему.
```

### Анализ предложений Claude

| Вариант | Предложен Claude | Принят? | Причина |
|---------|-----------------|---------|---------|
| AES-256-GCM | ✅ | ✅ | AEAD — даёт одновременно конфиденциальность и целостность |
| scrypt (n=2¹⁴) | ✅ | ✅ | Устойчив к GPU-атакам; n=2¹⁴ — баланс скорость/безопасность |
| argon2id | ✅ | ❌ | Требует `argon2-cffi`, лишняя зависимость |
| PBKDF2-HMAC-SHA256 | ✅ | ❌ | Слабее scrypt против параллельных атак |
| Файловый формат: MAGIC + salt + nonce + ciphertext | ✅ | ✅ | Самодостаточный blob, не нужна внешняя БД метаданных |

### Ключевые вопросы в диалоге

**Я:**
> Почему nonce должен быть случайным, а не счётчиком?

**Claude:**
> GCM катастрофически ломается при повторе nonce с тем же ключом:
> атакующий может восстановить ключ и расшифровать всё. Случайные 12 байт
> из `os.urandom` — стандартная практика для файлового шифрования,
> где один файл шифруется один раз.

**Я:**
> Нужно ли добавлять AAD (additional authenticated data)?

**Claude:**
> Для базового учебного проекта — нет. AAD полезен, когда нужно
> аутентифицировать незашифрованные метаданные (например, имя файла).
> В нашем случае весь контент шифруется, AAD не добавляет защиты.

### Что написал сам (после подсказок Claude)

- Константу `MAGIC = b"PFM1"` — идентификатор формата.
- Логику `decrypt_file_to_path` / `encrypt_file_to_path` — обёртки над
  байтовыми функциями для работы с файловой системой.
- Graceful-деградацию `_CRYPTO_AVAILABLE = False` для Android-окружений,
  где `cryptography` может не собраться.

### Ошибки, исправленные позже (по результатам code review)

**Проблема 1 — MIN_PASSPHRASE_LEN = 1:**  
Claude изначально поставил `MIN_PASSPHRASE_LEN = 1` с комментарием
«UI may impose stricter rules». Это было ошибкой — ни один слой не
проверял длину реально. По результатам ревью (сессия 11) поднято до `8`:

```python
# было
MIN_PASSPHRASE_LEN = 1  # enforce non-empty; UI may impose stricter rules
# стало
MIN_PASSPHRASE_LEN = 8
```

**Проблема 2 — слишком широкий except:**  
В `decrypt_bytes` Claude написал `except Exception`, сославшись на то,
что `cryptography` бросает `InvalidTag`. Правильный вариант — ловить
именно его:

```python
# было
except Exception as exc:  # cryptography raises InvalidTag
    raise InvalidPasswordError(...) from exc
# стало
from cryptography.exceptions import InvalidTag
...
except InvalidTag as exc:
    raise InvalidPasswordError(...) from exc
```

Оба исправления закоммичены в рамках `fix: исправить валидацию и безопасность crypto/schema`.

---

## 4. Схема БД и индексы

**Инструмент:** Claude Code (CLI)  
**Когда:** март 2026  
**Файл:** `src/infra/db/schema.py`

### Запрос

```
Нужна схема SQLite для таблиц: transactions, categories, goals, reminders, settings.
Добавь CHECK-constraints и индексы для фильтрации по дате и категории.
```

### Диалог об индексах

**Claude предложил:**
```sql
CREATE INDEX idx_transactions_occurred_at ON transactions(occurred_at);
CREATE INDEX idx_transactions_category_occurred ON transactions(category_id, occurred_at);
CREATE INDEX idx_transactions_type_occurred ON transactions(type, occurred_at);
```

**Я:**
> Зачем три индекса на transactions? Это не слишком?

**Claude:**
> Три паттерна запросов — три индекса. Покрытие (FR-03):
> 1. Фильтрация по периоду (без доп. условий) — `occurred_at`.
> 2. Фильтрация по категории + период — `(category_id, occurred_at)`.
> 3. Фильтрация по типу (доход/расход) + период — `(type, occurred_at)`.
> При N≈5000 (NFR-03) SQLite без индексов делает full scan — ощутимо.

Объяснение показалось убедительным, принял все три.

### Что скорректировал

Изначально Claude предложил хранить даты как `INTEGER` (Unix timestamp).
Заменил на `TEXT` (ISO-8601) — удобнее отладки, SQLite сортирует строки
ISO-8601 лексикографически правильно, `datetime.fromisoformat()` встроен
в Python без доп. парсинга.

### Важная правка (по итогам review)

Claude изначально добавил комментарий:
```python
# Bump SCHEMA_VERSION and the app re-creates the DB automatically.
```

Это была ошибка — никакого автоматического пересоздания нет. По результатам
code review заменил на честный комментарий:
```python
# NOTE: schema migrations are not supported in this version.
# All tables are created with IF NOT EXISTS — existing data is preserved
# on upgrade, but incompatible schema changes require a manual DB reset.
```

---

## 5. Слой репозитория и подключение к БД

**Инструмент:** Claude Code (CLI)  
**Когда:** март 2026  
**Файлы:** `src/infra/db/connection.py`, `src/infra/db/repositories.py`

### Запрос

```
Напиши connection manager для SQLite с поддержкой:
- временного расшифрованного файла (работа через plaintext SQLite)
- автоматической очистки tempfile при закрытии
- WAL-режима для производительности
```

### Принятые предложения

- `contextlib.contextmanager` + `tempfile.NamedTemporaryFile` — безопасная
  работа с расшифрованным файлом во временной директории ОС.
- `PRAGMA foreign_keys=ON` — обеспечивает `ON DELETE SET NULL` в `transactions`.

### Отклонённое предложение — WAL и почему

Claude изначально предложил `PRAGMA journal_mode=WAL`:

**Claude:**
> WAL даёт параллельное чтение без блокировки писателя и лучшую
> производительность при нескольких соединениях.

**Я:**
> Но у нас БД — временный расшифрованный файл в temp-директории.
> Что будет с WAL-файлами при аварийном завершении?

**Claude:**
> Точно подметил. При WAL SQLite создаёт sidecar-файлы `-wal` и `-shm`
> рядом с основным файлом. Если приложение упадёт до re-encrypt,
> в temp-директории останутся plaintext `-wal` файлы с данными.
> Это нарушает модель угроз проекта.
>
> Для вашего случая правильный выбор — `journal_mode=DELETE`:
> журнал удаляется сразу после коммита, sidecar-файлов нет.

Итог: принял `journal_mode=DELETE`. Это архитектурное решение зафиксировано
комментарием в `connection.py`:
```python
# DELETE mode: no WAL sidecar files (-wal/-shm) that could leak plaintext
# in the temp directory if the process crashes before re-encryption.
```

### Что я добавил сам

Логику шифрования обратно после закрытия соединения: `encrypt_file_to_path`
вызывается в `finally`-блоке, чтобы зашифрованный файл обновился даже
при исключении в коде приложения.

---

## 6. Модуль отчётности (reporting.py)

**Инструмент:** Claude.ai  
**Когда:** апрель 2026  
**Файл:** `src/core/reporting.py`

### Запрос

```
Нужны функции для отчётности (FR-03, FR-04):
1. Сумма доходов/расходов за период
2. Расходы по категориям за период (для диаграммы)
3. Расходы по дням за период (для графика динамики)

Функции должны принимать Iterable[Transaction] — чистая доменная логика,
без зависимости от БД.
```

### Диалог о дизайне API

**Я:**
> Стоит ли возвращать `dict` или отдельный dataclass для totals?

**Claude:**
> Dataclass предпочтительнее: даёт именованный доступ (`totals.income_cents`),
> тип проверяется mypy, легче тестировать. dict с магическими строками —
> антипаттерн для внутреннего API.

Согласился, `Totals` стал `frozen dataclass` с вычисляемым `balance_cents`.

**Я:**
> Как обработать транзакции вне периода — фильтр внутри функции или снаружи?

**Claude:**
> Внутри функции — это защищает от логических ошибок вызывающего кода.
> Функция берёт ответственность за корректность периода и сама проверяет
> `end >= start`.

### Что отклонил

Claude предложил сделать `totals_for_period` методом класса `ReportService`
с инъекцией репозитория. Отклонил — для учебного проекта проще чистые функции,
тесты пишутся без моков.

---

## 7. Написание тестов

**Инструмент:** Claude Code (CLI)  
**Когда:** апрель 2026  
**Файлы:** `tests/test_core_reporting.py`, `tests/test_crypto.py`,
`tests/test_infra_db.py`, `tests/test_smoke.py`

### Запрос

```
Покрой тестами:
1. src/core/reporting.py — граничные случаи периода, фильтрация по типу
2. src/infra/security/crypto.py — roundtrip, неверный пароль, битый заголовок
3. Добавь conftest.py с фикстурой временной БД
```

### Что написал Claude, что доработал я

| Тест | Автор | Примечание |
|------|-------|------------|
| `test_encrypt_decrypt_roundtrip` | Claude | принят без изменений |
| `test_decrypt_rejects_wrong_password` | Claude | принят |
| `test_decrypt_rejects_wrong_header` | Claude | принят |
| `test_totals_for_period_filters_by_date_inclusive` | Claude | скорректировал данные — более показательный набор транзакций |
| `test_expense_by_category_sums_only_expenses` | Claude | добавил случай `category_id=None` |
| `test_transaction_rejects_zero_amount` | Я сам | добавил после того, как написал валидацию нуля в `__post_init__` |
| `conftest.py` с фикстурой `db_path` | Claude | принят |

### Найденная проблема при написании тестов

При попытке добавить `"Goal"` и `"Reminder"` в `__all__` модуля `models.py`
(подсказка Claude — "экспортируй все публичные классы") CI упал с `ruff F822`:
эти классы определены в других файлах, не в `models.py`.

**Решение:** `__all__` содержит только `["TransactionType", "Transaction"]`.
Проверил через `python -m ruff check .` локально перед коммитом.

---

## 8. Настройка CI (GitHub Actions)

**Инструмент:** Claude.ai  
**Когда:** апрель 2026  
**Файл:** `.github/workflows/ci.yml`

### Запрос

```
Настрой GitHub Actions CI:
- Python 3.12, ubuntu-latest
- ruff (линтер), pytest, pip-audit (проверка CVE)
- Kivy нельзя ставить в CI (нет дисплея)
- Как разделить зависимости?
```

### Предложенное решение (принято)

Два профиля зависимостей:
- `requirements/ci.txt` — только `cryptography` (без Kivy/KivyMD),
  для CI и Docker.
- `requirements/app.txt` — полный стек с Kivy для локального запуска.

**Я:**
> pip-audit ругается на `pytest==8.4.2` — CVE GHSA-6w46-j5rx-g56g.

**Claude:**
> Обнови до `pytest>=9.0.3`, где уязвимость закрыта. Команда:
> `pip install -U pytest && pip freeze | grep pytest`

Обновил до `pytest==9.0.3`, CVE исчез, CI позеленел.

### Что уточнил сам

Добавил шаг `pip-audit` явно в CI, хотя Claude его не включил в первый
вариант `ci.yml`. Важно проверять уязвимости в автоматическом режиме,
а не только вручную.

---

## 9. Исправление ошибок по результатам code review

**Инструмент:** Claude Code (CLI)  
**Когда:** апрель 2026 (финальный этап)

Автоматизированный bot-review выявил несколько проблем. Ниже — как AI помог
с диагностикой и исправлением.

### 9.1. Misleading-комментарий в schema.py

**Проблема (bot review):**
> Комментарий утверждает, что приложение автоматически пересоздаёт БД
> при смене SCHEMA_VERSION — это не реализовано.

**Запрос к Claude:**
```
В schema.py есть комментарий про автоматическую миграцию,
которой не существует. Как исправить честно, не обещая того, чего нет?
```

**Claude:**
> Замени на описание фактического поведения: `IF NOT EXISTS` сохраняет данные,
> но несовместимые изменения требуют ручного сброса. Не обещай то,
> что не реализовано.

Исправлено. Commit: `fix: correct misleading comments about schema migration`.

### 9.2. FR-02 в документации — нереализованные функции

**Проблема (bot review):**
> Документ `03_requirements.md` описывает CRUD категорий как реализованный,
> хотя в v0.1 это backlog.

**Запрос к Claude:**
```
Как корректно отразить в требованиях, что FR-02 (CRUD категорий)
запланирован, но не реализован в текущей версии?
```

**Claude:**
> Добавь явную пометку `_(backlog — не реализовано в v0.1)_` в заголовок FR-02.
> В критериях приёмки замени "пользовательские категории" на
> "минимум 5 предустановленных категорий; CRUD — backlog v0.2".

Исправлено. Commit: `fix: correct misleading comments about schema migration and category CRUD`.

### 9.3. Непропинованные зависимости в dev.txt

**Проблема (bot review):**
> `requirements/dev.txt` не содержит точных версий.

**Решение (с помощью Claude):**
```bash
pip install pytest ruff pip-audit pyinstaller
pip freeze | grep -E "pytest|ruff|pip.audit|pyinstaller"
```

Добавлен комментарий и пины:
```
pytest==9.0.3
ruff==0.15.11
pip-audit==2.9.0
pyinstaller==6.19.0
```

---

## 10. Итоги использования AI

### Что работало хорошо

| Задача | Польза AI |
|--------|-----------|
| Выбор алгоритмов шифрования | Объяснил trade-offs scrypt vs PBKDF2 vs argon2 |
| Дизайн API функций отчётности | Аргументировал dataclass vs dict |
| Написание boilerplate-тестов | Сгенерировал 80% тест-кода за один запрос |
| Диагностика CVE в pip-audit | Мгновенно определил пакет и версию-фикс |
| SQL-индексы | Объяснил, какой индекс для какого паттерна |

### Где пришлось корректировать AI

| Проблема | Что исправил |
|----------|-------------|
| `__all__` содержал несуществующие имена → `ruff F822` | Убрал `"Goal"`, `"Reminder"` из `__all__` в `models.py` |
| Misleading-комментарий про автомиграцию | Переписал на честное описание ограничений |
| Предложение ORM (SQLAlchemy) | Отклонил — избыточно для SQLite-only |
| Хранение дат как `INTEGER` | Заменил на `TEXT` (ISO-8601) — удобнее отладки |
| Предложение `ReportService`-класса | Оставил чистые функции — проще для тестов |

### Вывод

AI-ассистент использовался как **инструмент ускорения**, а не замена понимания.
Каждое предложение оценивалось критически: часть принималась, часть отклонялась
с обоснованием. Итоговый код написан и понят мной — AI помогал с
выбором алгоритмов, генерацией boilerplate и диагностикой ошибок.

---

## 11. Рефакторинг: разбивка app.py и правки по итогам финального ревью

**Инструмент:** Claude Code (CLI, `claude-sonnet-4-6`)  
**Когда:** 09.05.2026  
**Затронуто файлов:** 13 (создано 12 новых, изменён `src/app.py`)

### Контекст

Automated bot review выставил 87/100. Из замечаний:
- `src/app.py` — 1705 строк, монолит, "смешанная логика UI и use cases"
- `MIN_PASSPHRASE_LEN = 1` — фактически не проверяется
- `except Exception` в `decrypt_bytes` вместо `InvalidTag`
- Несоответствие `amount_cents`: `>= 0` в схеме vs `> 0` в модели
- Дублирование фильтрации в `reporting.py` (3 функции, одинаковый код)
- Нет тестов на corrupted ciphertext и DB rollback

### Этап 1 — быстрые фиксы

**Запрос:**
```
По ревью нашли 5 проблем в crypto.py, schema.py, models.py.
Исправь и покрой тестами.
```

**Что предложил Claude и что принято:**

| Правка | Предложение | Принято? |
|--------|------------|---------|
| `MIN_PASSPHRASE_LEN = 8` | Claude | ✅ |
| Импортировать `InvalidTag`, ловить именно его | Claude | ✅ |
| `amount_cents > 0` в SQL CHECK (было `>= 0`) | Claude | ✅ |
| Упростить двойную проверку в `__post_init__` до `<= 0` | Claude | ✅ |
| Тест `test_decrypt_rejects_corrupted_ciphertext` | Claude | ✅ |
| Тест `test_encrypt_decrypt_empty_plaintext` | Claude | ✅ |
| Тест `test_rollback_on_duplicate_category_name` | Claude | ✅ |

**Что скорректировал я:**  
Существующие тесты использовали пароль `"secret"` (6 символов) —
после поднятия минимума до 8 они сломались. Обновил на `"supersecret123"`.

### Этап 2 — рефакторинг reporting.py

**Запрос:**
```
В reporting.py одна и та же проверка end >= start и цикл
фильтрации по дате повторяются в трёх функциях. Вынеси в хелпер.
```

**Claude предложил:**
```python
def _filter_period(transactions, start, end):
    if end < start:
        raise ValueError("end must be >= start")
    return [t for t in transactions if start <= t.occurred_at <= end]
```

Принял без изменений — функция чистая, все три функции стали короче,
тесты прошли без правок.

### Этап 3 — разбивка app.py (Plan mode)

**Задача:**  
1705 строк в одном файле → архитектурно правильный пакет `src/ui/`.

**Запрос (Plan mode):**
```
Как разбивать app.py будем?
```

Claude предложил **12-шаговый план снизу вверх** (от листьев к корню),
чтобы на каждом шаге файл был готов к импорту.

**Ключевое архитектурное решение — как передавать репозитории в popup-экраны:**

Три варианта:
1. Передавать каждый репозиторий как kwarg: `build_goals_popup(*, conn, goal_repo)`
2. Объект-контекст: `build_goals_popup(ctx: AppContext)`
3. Оставить методами на `RootView`

**Я:**
> Какой вариант предпочтительнее для учебного проекта?

**Claude:**
> Вариант 1 — keyword-only аргументы. Явно, легко тестировать,
> нет скрытых зависимостей. Context-объект оправдан, когда параметров 5+
> и они меняются вместе; у нас их 2–3.

Принял вариант 1. В `RootView` остались тонкие делегаторы с deferred import,
чтобы гарантировать отсутствие циклов:

```python
def open_reports_popup(self) -> None:
    from src.ui.screens.reports import build_reports_popup
    build_reports_popup(tx_repo=self.repo, cat_repo=self.cat_repo,
                        current_month=self.state.current_month)
```

**Что отклонил:**  
Claude предложил вынести `encryption_enabled()` в `src/ui/theme.py` вместе
с путями к файлам. Отклонил — функция содержит `from kivy.utils import platform`,
это runtime-поведение, а не константа; она принадлежит lifecycle приложения.

### Результат рефакторинга

| Метрика | До | После |
|---------|-----|-------|
| `src/app.py` | 1705 строк | 185 строк |
| Новых модулей | 0 | 12 (`src/ui/`) |
| Тестов | 36 | 40 |
| ruff ошибок | 0 | 0 (после фикса CI) |

### Постфикс — CI упал после пуша

ruff нашёл 8 ошибок в новых файлах:
неиспользуемые импорты (`sys`, `FS_TITLE`, `COL_BORDER` и др.)
и несортированный блок импортов в `overview.py`.

**Запрос:**
```
CI упал на ruff. Как исправить?
```

**Claude:**
> `py -3.12 -m ruff check . --fix` — все 8 ошибок fixable автоматически.

Запустил, проверил тесты (40/40), закоммитил.
