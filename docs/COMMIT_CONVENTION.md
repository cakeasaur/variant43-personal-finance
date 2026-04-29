## Семантические коммиты (Conventional Commits)

### Формат
```
<type>(<scope>): <subject>
```

Где:
- **type** — тип изменения
- **scope** — область (опционально), например: `ui`, `db`, `docs`, `tests`, `ci`
- **subject** — кратко и в повелительном наклонении

### Рекомендованные типы
- **feat**: новая функциональность
- **fix**: исправление дефекта
- **docs**: документация
- **test**: тесты
- **refactor**: рефакторинг без изменения поведения
- **perf**: улучшение производительности
- **build**: сборка/зависимости
- **ci**: CI/CD
- **chore**: прочее (рутина/обслуживание)

### Примеры
```
feat(db): add transactions table with indices
feat(ui): add transaction editor screen
fix(db): handle NULL category_id in aggregates
docs(report): add architecture diagrams description
test(core): add unit tests for monthly totals
```

