## Deploy / Build (cross-platform)

Приложение кроссплатформенное на уровне **одной кодовой базы** (Python + Kivy/KivyMD).
Сборка под разные платформы делается разными инструментами.

### Desktop (Windows) — PyInstaller

Требования:
- Python **3.12 x64**
- установленный Build Tools обычно не нужен (ставятся готовые wheel)

Сборка:

```powershell
cd <путь-к-репозиторию>
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements/app.txt -r requirements/dev.txt

# сборка
.\scripts\build_win.ps1
```

Артефакт:
- `dist/PersonalFinance/PersonalFinance.exe`

Smoke-проверка (без GUI):

```powershell
dist\PersonalFinance\PersonalFinance.exe --smoke
```

Где хранятся данные:
- В режиме exe база хранится рядом с exe: `dist/PersonalFinance/data/` (создаётся автоматически).

### Android — подготовка (Buildozer)

Важно:
- Сборка Android обычно делается на Linux (удобно через **WSL2 + Ubuntu**).
- В репозитории есть `main.py` — это entrypoint, который ожидает Buildozer.

Быстрый план:
1. Установить Buildozer в WSL (Python 3.11/3.12), Android SDK/NDK.
2. Сгенерировать/отредактировать `buildozer.spec`.
3. Собрать `debug` APK: `buildozer -v android debug`.

Подробная инструкция: см. `docs/ANDROID.md`.

