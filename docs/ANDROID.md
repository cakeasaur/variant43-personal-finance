## Android build (flet build)

Сборка Android APK выполняется через `flet build` — официальный инструмент Flet,
основанный на Flutter.

### 0) Предпосылки

- Python 3.12
- `flet` установлен (`pip install flet`)
- Достаточно места на диске (Flutter SDK + Android SDK скачиваются автоматически)

### 1) Первая сборка

```bash
cd <путь-к-репозиторию>
pip install -r requirements/app.txt

flet build apk --project PersonalFinance
```

При первом запуске `flet build` автоматически скачает Flutter SDK и Android SDK/NDK.
Это занимает время (5–15 минут в зависимости от соединения).

### 2) Где будет APK

```
build/apk/app-release.apk
```

### 3) Замечания по шифрованию

Desktop-версия использует `cryptography` для шифрования файла БД.
На Android рекомендуется:
- отключить шифрование через `PF_DISABLE_ENCRYPTION=1` (БД хранится
  в приватном каталоге приложения, недоступном без root);
- либо реализовать хранение ключа через Android Keystore API.

### 4) Entrypoint

Flet ожидает `main_flet.py` в корне проекта — он уже используется
как основная точка входа.
