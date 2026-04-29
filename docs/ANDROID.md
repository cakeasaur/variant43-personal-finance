## Android build (WSL2 + Buildozer)

Эта инструкция готовит структуру и воспроизводимый процесс сборки Android.
Сборка выполняется **в Linux** (рекомендуется WSL2 + Ubuntu 22.04/24.04).

### 0) Предпосылки

- Windows 10/11 + включённый WSL2
- Ubuntu в WSL2
- Достаточно места на диске (SDK/NDK/Gradle)

### 1) Установка Buildozer (внутри Ubuntu)

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-venv python3-pip \
  build-essential libffi-dev libssl-dev autoconf automake libtool pkg-config

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip wheel setuptools
python -m pip install buildozer
```

### 2) `buildozer.spec`

В репозитории лежит готовый шаблон `buildozer.spec`.
Он использует entrypoint `main.py`.

По умолчанию Android-сборка идёт **без шифрования БД** (см. ниже), чтобы сборка была
воспроизводимой.

### 3) Первая сборка (debug APK)

```bash
buildozer -v android debug
```

Первый прогон скачает Android SDK/NDK и зависимости, это долго.

### 4) Где будет APK

Обычно:
- `bin/*.apk`

### Замечания по зависимостям (важно для криптографии)

Десктоп-версия использует `cryptography` для шифрования файла БД. На Android эта зависимость
часто усложняет сборку (нативные зависимости/рецепты python-for-android).

Решение в проекте:
- В `buildozer.spec` **не включаем** `cryptography` в requirements
- В коде шифрование автоматически отключается на Android
  (`src/app.py:encryption_enabled()`), т.к. БД хранится в приватном каталоге приложения.

