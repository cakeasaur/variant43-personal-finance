# Миграция Kivy → Flet

Сессия 16 мая 2026.

## Что сделано

Переход с Kivy на Flet 0.85 как UI-фреймворк. Доменный слой (`src/core/`) и инфраструктура (`src/infra/`) не тронуты — переиспользованы один в один.

### Новая структура UI

```
src/ui_flet/
  __init__.py
  theme.py          — палитра, пути к БД, card_shadow()
  state.py          — Repos dataclass (cat / tx / goal / reminder)
  components.py     — переиспользуемые блоки: build_sidebar, metric_card,
                      tx_row, progress_row, card_container, section_card,
                      open_dialog / close_dialog, empty_state
  screens/
    overview.py     — главный экран (метрики, график динамики,
                      цели, последние операции)
    operations.py   — список операций с навигацией по месяцам,
                      фильтром (Все/Доходы/Расходы), добавлением, удалением
    goals.py        — финансовые цели: список с ProgressRing,
                      summary-баннер, создание/редактирование/
                      пополнение/удаление
    reminders.py    — напоминания с подсветкой просроченных,
                      создание/отметить выполненным/удалить
    reports.py      — аналитика: расходы по категориям (ProgressBar-ряды
                      с палитрой), расходы по дням
main_flet.py        — entrypoint: роутинг, диалог пароля,
                      шифрование БД на старте/закрытии
```

### Изменения вне UI

- `src/core/reporting.py` — добавлена `income_by_day()` (для двух линий на графике).
- `requirements/app.txt` — `flet==0.85.1`, `flet-charts==0.85.1`, `matplotlib>=3.9`, `cryptography==46.0.7`. Kivy и Pillow убраны.
- `tests/test_smoke.py` — Kivy-skip заменён на Flet-skip, все 6 smoke + 42 общих теста зелёные.
- `CLAUDE.md` — обновлён под Flet-стек.
- `prototypes/flet_overview.py` — оригинальный прототип, на основе которого сделан финальный код.

### Kivy-код

Не удалён. Лежит как было:
- `src/ui/` — все Kivy-виджеты.
- `src/app.py` — Kivy entrypoint.
- `main.py` — root entrypoint Kivy.

Можно удалить после подтверждения паритета.

## Чарты

### График динамики (главный экран)

Используется `matplotlib` → PNG-байты → `ft.Image(src=bytes)`. Это desktop-режим Flet — `MatplotlibChart` из flet_charts работает только в web-режиме (требует WebSocket), для desktop падает с `'FigureManagerBase' has no attribute 'add_web_socket'`.

Данные: per-day income/expense, Gaussian smoothing (sigma=2.5) → плавные купола вместо спайков. Маркеры через каждые 3 дня. X-ось: русские сокращённые месяцы («1 мая», «8 мая», ...).

### Аналитика — расходы по категориям

`flet_charts.PieChart` пришлось выбросить — не соблюдает границы контейнера в Flet 0.85, перекрывает заголовок. Замена: кастомные `ProgressBar`-ряды с цветной точкой, названием категории, процентом и суммой. Палитра расходов начинается с красного (не зелёного) — семантически правильно.

## Квирки Flet 0.85.1 (зафиксированы в памяти)

Документация Context7 отстаёт. Перед использованием — `inspect.signature(...)`. Найденные несовпадения:

| Что | Старое API | В 0.85 |
|-----|-----------|--------|
| Dropdown change | `on_change=` | `on_select=` |
| Image base64 | `src_base64=` | `src=bytes` (передавать байты напрямую) |
| Image fit enum | `ft.ImageFit.CONTAIN` | `ft.BoxFit.CONTAIN` |
| Dialog open | `page.overlay.append(dlg); dlg.open=True` | `page.show_dialog(dlg)` |
| Dialog close | `dlg.open=False; overlay.remove(dlg)` | `page.pop_dialog()` |
| Window close event | `e.type == ft.WindowEventType.CLOSE` | `e.type == ft.WindowEventType.CLOSE.value` (enum != string) |
| Charts | `from flet import LineChart, ...` | `from flet_charts import ...` |
| LineChartData points | `data_points=` | `points=` |
| ChartAxis label size | `labels_size=` | `label_size=` |
| Session storage | `page.session.set/get` | Убрано полностью — использовать замыкания/dict |
| Optional event callable | `ft.OptionalControlEventCallable` | Нет — `Callable[[Any], None] | None` |
| MatplotlibChart | работает в desktop | только web-режим, для desktop — `matplotlib → PNG → ft.Image` |

## Known issues

### ~~Шифрование при закрытии не работает стабильно~~ — исправлено

Баг: `atexit` работает в LIFO-порядке. `atexit(path.unlink)` регистрировался в `_new_temp_db()` позже, чем `atexit(shutdown_encrypt)` в `main()`, поэтому temp-файл удалялся до того, как `shutdown_encrypt` успевал его зашифровать.

Фикс: убран `atexit` из `_new_temp_db`. Очистку делает `shutdown_encrypt` (удаляет после шифрования), оставшиеся файлы подчищает `_cleanup_orphaned_dbs` при следующем запуске.

### Sparse-данные на графике

С одной транзакцией зарплаты на 15-е число график показывает одну плавную колоколообразную кривую вместо зигзага как на макете. Это математическое ограничение — зигзаг получится только при 10+ транзакциях, распределённых по месяцу. Заполни демо-данные → получишь нужную картинку.

## Что осталось

- [x] Стабилизировать шифрование при закрытии — исправлен LIFO atexit-баг.
- [ ] Сменить пароль — кнопка в Настройках (расшифровать старым → зашифровать новым).
- [ ] Экраны Категории и Настройки (сейчас заглушки «в разработке»).
- [ ] Сборка Windows / Android: `flet build` вместо `buildozer`. Обновить `scripts/build_win.ps1`, заменить `buildozer.spec`.
- [ ] Удалить Kivy-код (`src/ui/`, `src/app.py`, `main.py`) после подтверждения паритета.
- [ ] Обновить главы пояснительной записки: `docs/report/06_technology.md`, `04_architecture.md` — заменить упоминания Kivy на Flet.

## Команды

```powershell
# Запуск
py -3.12 main_flet.py

# Запуск без шифрования (debug)
$env:PF_DISABLE_ENCRYPTION=1; py -3.12 main_flet.py

# Тесты + линт
py -3.12 -m pytest -q
py -3.12 -m ruff check .

# Установка зависимостей с нуля
py -3.12 -m pip install -r requirements/app.txt -r requirements/dev.txt
```
