from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

LOGIN_URLS = {
    "linkedin": "https://www.linkedin.com/login",
    "eventbrite": "https://www.eventbrite.com/signin/",
    "luma": "https://luma.com/signin",
}


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


def browser_cookies(site: str, output: Path) -> None:
    profile = output.parent / f"{site}-browser-profile"
    profile.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(profile.resolve()), headless=False, viewport={"width": 1440, "height": 1000}
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(LOGIN_URLS[site], wait_until="domcontentloaded")
        input(f"Sign in to {site} in the browser. When finished, press Enter here... ")
        cookies = context.cookies()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(cookies, separators=(",", ":")), encoding="utf-8")
        context.close()
    print(f"Session cookies saved in {output.resolve()}; treat this file like a password.")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Bootstrap interactive account sessions")
    subparsers = parser.add_subparsers(dest="source", required=True)
    whatsapp_parser = subparsers.add_parser("whatsapp")
    whatsapp_parser.add_argument("--profile", type=Path, default=Path(".state/whatsapp"))
    cookie_parser = subparsers.add_parser("cookies")
    cookie_parser.add_argument("site", choices=sorted(LOGIN_URLS))
    cookie_parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.source == "whatsapp":
        whatsapp(args.profile)
    else:
        output = args.output or Path(f".state/{args.site}-cookies.json")
        browser_cookies(args.site, output)


if __name__ == "__main__":
    main()
