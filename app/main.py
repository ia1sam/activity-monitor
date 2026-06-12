from __future__ import annotations

import argparse
import time

from app.bootstrap import build_app_context
from app.monitoring.activity_collector import ActivityCollector


def build_collector(storage: str = "sqlite") -> ActivityCollector:
    return build_app_context(storage=storage).collector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="User activity monitoring")
    parser.add_argument(
        "--storage",
        choices=["sqlite", "csv", "both"],
        default="sqlite",
        help="Storage backend for activity records",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    collector = build_collector(storage=args.storage)
    collector.start()
    print("Activity collection started. Press Ctrl+C to stop.")
    print(f"Storage: {args.storage}")
    try:
        while collector.is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        collector.stop()
        time.sleep(1)


if __name__ == "__main__":
    main()
