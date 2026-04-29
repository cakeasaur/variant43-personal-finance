"""
Cross-platform entrypoint.

- Used by Buildozer (Android) which expects `main.py` at the project root.
- Can also be used by PyInstaller as a stable entry script.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _smoke() -> int:
    """
    Smoke-check for packaged builds.

    Validates that:
    - the entrypoint runs
    - `assets/` is discoverable in a PyInstaller context
    - a writable `data/` directory can be created next to the executable
    """
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
    data_dir = exe_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    assets_dir = root / "assets"
    ok = assets_dir.exists()
    print(f"root={root}")
    print(f"exe_dir={exe_dir}")
    print(f"data_dir={data_dir}")
    print(f"assets_dir={assets_dir} exists={ok}")
    return 0 if ok else 2


def main() -> None:
    # Import Kivy/KivyMD only after our arg parsing.
    from src.app import PersonalFinanceApp

    PersonalFinanceApp().run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--smoke", action="store_true", help="run packaging smoke-check and exit")
    args, _unknown = parser.parse_known_args()

    if args.smoke:
        # Avoid Kivy parsing CLI args in smoke mode.
        os.environ["KIVY_NO_ARGS"] = "1"
        raise SystemExit(_smoke())

    main()

