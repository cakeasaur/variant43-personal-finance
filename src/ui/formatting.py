from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

MONTH_NAMES_RU = (
    "", "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
)

RECURRENCE_LABELS = ["Не повторять", "Ежедневно", "Еженедельно", "Ежемесячно"]
RECURRENCE_VALUES = ["none", "daily", "weekly", "monthly"]
RECURRENCE_UI_TO_VALUE = dict(zip(RECURRENCE_LABELS, RECURRENCE_VALUES, strict=True))
RECURRENCE_VALUE_TO_UI = {v: k for k, v in RECURRENCE_UI_TO_VALUE.items()}

FILTER_UI_TO_KIND = {"Все": "all", "Расходы": "expense", "Доходы": "income"}
KIND_UI_TO_KIND   = {"Расход": "expense", "Доход": "income"}
KIND_KIND_TO_UI   = {v: k for k, v in KIND_UI_TO_KIND.items()}


def format_rub(cents: int) -> str:
    return f"{cents / 100:,.2f}".replace(",", " ")


def _ops_word(n: int) -> str:
    """Russian plural for 'операция'."""
    if 11 <= n % 100 <= 19:
        return "операций"
    if n % 10 == 1:
        return "операция"
    if 2 <= n % 10 <= 4:
        return "операции"
    return "операций"


def month_title_ru(dt: datetime) -> str:
    return f"{MONTH_NAMES_RU[dt.month]} {dt.year}".capitalize()


def month_bounds_utc(dt: datetime) -> tuple[datetime, datetime]:
    start = datetime(dt.year, dt.month, 1, tzinfo=UTC)
    if dt.month == 12:
        next_month = datetime(dt.year + 1, 1, 1, tzinfo=UTC)
    else:
        next_month = datetime(dt.year, dt.month + 1, 1, tzinfo=UTC)
    return start, next_month - timedelta(seconds=1)


def recurrence_display(value: str) -> str:
    return RECURRENCE_VALUE_TO_UI.get(value, value)


def kind_to_ui(kind: str) -> str:
    return KIND_KIND_TO_UI.get(kind, kind)


def parse_money(text: str) -> int:
    try:
        cents = (Decimal(text.strip().replace(",", ".")) * 100).to_integral_value()
        return int(cents)
    except InvalidOperation as exc:
        raise ValueError("Некорректная сумма") from exc
