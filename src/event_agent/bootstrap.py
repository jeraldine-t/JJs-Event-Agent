from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from telethon import TelegramClient
from telethon.sessions import StringSession


def whatsapp(profile: Path) -> None:
    profile.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile.resolve()), headless=False, viewport={"width": 1440, "height": 1000}
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
        input("Scan the QR code if asked. When the chat list is visible, press Enter here... ")
        context.close()
    print(f"WhatsApp session saved in {profile.resolve()}")


def telegram() -> None:
    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session = client.session.save()
    print("Store this value as TELEGRAM_SESSION_STRING (never commit it):")
    print(session)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Bootstrap interactive account sessions")
    subparsers = parser.add_subparsers(dest="source", required=True)
    whatsapp_parser = subparsers.add_parser("whatsapp")
    whatsapp_parser.add_argument("--profile", type=Path, default=Path(".state/whatsapp"))
    subparsers.add_parser("telegram")
    args = parser.parse_args()
    if args.source == "whatsapp":
        whatsapp(args.profile)
    else:
        telegram()


if __name__ == "__main__":
    main()

