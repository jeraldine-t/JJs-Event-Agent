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
        help="Comma-separated source override (linkedin,eventbrite,luma,meetup,whatsapp)",
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
    count, statuses = run_pipeline(settings)
    summary = ", ".join(f"{status.source}={status.state}" for status in statuses) or "none"
    logging.getLogger(__name__).info(
        "Complete: %d curated events; sources: %s",
        count,
        summary,
    )


if __name__ == "__main__":
    main()
