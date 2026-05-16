from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable so `import src...` works even when pytest is
# launched from outside the repository root (e.g. via IDE runner).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

