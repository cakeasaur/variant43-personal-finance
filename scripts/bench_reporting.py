from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.perf import benchmark_reporting  # noqa: E402


def main() -> None:
    res = benchmark_reporting(n=50_000)
    print(
        "reporting benchmark "
        f"(n={int(res['n'])}): totals={res['totals_s']:.4f}s, "
        f"by_category={res['by_category_s']:.4f}s, by_day={res['by_day_s']:.4f}s, "
        f"total={res['total_s']:.4f}s"
    )


if __name__ == "__main__":
    main()

