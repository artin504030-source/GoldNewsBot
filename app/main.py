"""Command-line entry point for operational checks."""
from __future__ import annotations

import argparse
import json

from app.platform.health import health_report


def main() -> int:
    parser = argparse.ArgumentParser(description="GoldNewsBot operations")
    parser.add_argument("command", nargs="?", choices=("health",), help="Operational command")
    parser.add_argument("--health", action="store_true", help="Compatibility health check")
    args = parser.parse_args()
    if args.command != "health" and not args.health:
        parser.print_help()
        return 0
    report = health_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
