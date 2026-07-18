from __future__ import annotations

import argparse
import logging
from dataclasses import replace
from pathlib import Path

from event_agent.config import Settings
from event_agent.pipeline import run_pipeline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover and publish curated Singapore events")
    parser.add_argument(
        "--sources",
        help="Comma-separated source override (linkedin,luma,eventbrite,meetup,whatsapp,telegram)",
    )
    parser.add_argument(
        "--skip-telegram",
        action="store_true",
        help="Generate the dashboard without sending the Telegram Bot output",
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--log-level", default="INFO")
    return parser


def main() -> None:
    args = _parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_env(args.root)
    if args.sources is not None:
        requested = tuple(item.strip() for item in args.sources.split(",") if item.strip())
        settings = replace(settings, enabled_sources=requested)
    count, statuses, notification = run_pipeline(
        settings, send_telegram=not args.skip_telegram
    )
    summary = ", ".join(f"{status.source}={status.state}" for status in statuses) or "none"
    logging.getLogger(__name__).info(
        "Complete: %d curated events; sources: %s; Telegram: %s",
        count,
        summary,
        notification.state,
    )


if __name__ == "__main__":
    main()

