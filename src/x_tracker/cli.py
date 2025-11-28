from __future__ import annotations

import argparse
from pathlib import Path

from .tracker import ActivityTracker, TrackerConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Track X accounts and send Telegram updates.")
    parser.add_argument("--once", action="store_true", help="Run a single poll instead of looping.")
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Polling interval in seconds (overrides POLL_SECONDS).",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="Path to the JSON file storing last seen tweet IDs.",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> TrackerConfig:
    config = TrackerConfig.from_env()
    if args.interval:
        config.poll_seconds = args.interval
    if args.state_file:
        config.state_file = args.state_file
    return config


def main() -> None:
    args = parse_args()
    config = build_config(args)
    tracker = ActivityTracker(config)
    if args.once:
        tracker.check_once()
    else:
        tracker.run()


if __name__ == "__main__":
    main()
