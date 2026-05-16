from __future__ import annotations

from dataclasses import dataclass

from ..infra.db.repositories import (
    CategoryRepository,
    GoalRepository,
    ReminderRepository,
    TransactionRepository,
)


@dataclass
class Repos:
    cat: CategoryRepository
    tx: TransactionRepository
    goal: GoalRepository
    reminder: ReminderRepository
