## Deploy / Build (cross-platform)

Приложение кроссплатформенное на уровне **одной кодовой базы** (Python + Flet).
Сборка под разные платформы делается через `flet build`.

### Desktop (Windows) — flet build windows

Требования:
- Python **3.12 x64**
- Flutter SDK (устанавливается автоматически при первом `flet build`)

Сборка:

```powershell
cd <путь-к-репозиторию>
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements/app.txt -r requirements/dev.txt

# сборка
flet build windows --project PersonalFinance
```

Артефакт:
- `build/windows/PersonalFinance.exe`

### Android — flet build apk

Требования:
- Python 3.12
- Android SDK (устанавливается автоматически при первом `flet build android`)

```bash
flet build apk --project PersonalFinance
```

Артефакт:
- `build/apk/app-release.apk`

> **Примечание по шифрованию на Android:** для воспроизводимой сборки APK
> рекомендуется использовать `PF_DISABLE_ENCRYPTION=1` или реализовать
> отдельную логику хранения ключа через Android Keystore.

### Docker (только для проверок, без GUI)

```powershell
docker compose run --rm checks
```

Контейнер прогоняет те же проверки, что и CI:
- `ruff`
- `pytest`
- `pip-audit`
