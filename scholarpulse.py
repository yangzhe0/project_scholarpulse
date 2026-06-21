#!/usr/bin/env python3
"""ScholarPulse command line entry point."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from config import load_config
from workflow import run


def valid_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc
    if parsed.strftime("%Y-%m-%d") != value:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate configured ScholarPulse daily reports.")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Generate daily reports and indexes")
    generate.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    generate.add_argument("--date", type=valid_date, default=datetime.now().strftime("%Y-%m-%d"))
    generate.add_argument("--direction", help="Run only the direction with this name")
    generate.add_argument("--force", action="store_true")

    argv = sys.argv[1:]
    if not argv or argv[0].startswith("-"):
        argv.insert(0, "generate")
    args = parser.parse_args(argv)
    return run(load_config(args.config), args.date, args.force, args.direction)


if __name__ == "__main__":
    raise SystemExit(main())
