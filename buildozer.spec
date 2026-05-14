[app]
title = Personal Finance
package.name = personalfinance
package.domain = org.variant43

# Buildozer expects main.py at project root.
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,txt

version = 0.1.0

# NOTE: `cryptography` is intentionally omitted to keep Android builds reproducible.
# See `src/app.py:encryption_enabled()` and `docs/ANDROID.md`.
requirements = python3,kivy,pillow

orientation = portrait
fullscreen = 0

icon.filename = assets/brand_coin.png

# (Optional) If you add a presplash image later:
# presplash.filename = assets/bg_app.png

[buildozer]
log_level = 2
warn_on_root = 1

[android]
android.api = 33
android.minapi = 26
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a

# Permissions: storage not required; DB is stored in app-private storage by default.
# android.permissions =

