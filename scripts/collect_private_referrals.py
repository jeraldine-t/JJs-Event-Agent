"""Build local, URL-only referral queues from the paired Telegram and WhatsApp plugins.

This script deliberately never writes message bodies, sender details, chat names, media, or
account information. The agent subsequently accepts only pages that can be verified without
cookies as public event detail pages.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

URL_RE = re.compile(r"https?://[^\s<>\]\[)]+", re.IGNORECASE)
TIMEZONE = ZoneInfo("Asia/Singapore")


def _items(variable: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(variable, "").split("|") if item.strip())


def _text(result: object) -> str:
    return "\n".join(
        str(getattr(item, "text", ""))
        for item in getattr(result, "content", [])
        if getattr(item, "text", None)
    )


def _urls(text: str) -> list[str]:
    return list(dict.fromkeys(match.rstrip(".,;:!?") for match in URL_RE.findall(text)))


async def _call(params: StdioServerParameters, tool: str, arguments: dict) -> str:
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as session:
        await session.initialize()
        return _text(await session.call_tool(tool, arguments))


async def _telegram_urls(after: str) -> list[str]:
    chats = _items("JJS_TELEGRAM_CHAT_REFS")
    if not chats:
        return []
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "codex_telegram", "serve"],
        env=os.environ.copy(),
    )
    urls: list[str] = []
    for chat_ref in chats:
        urls.extend(
            _urls(
                await _call(
                    params,
                    "get_history",
                    {"chat_ref": chat_ref, "limit": 100, "min_date": after},
                )
            )
        )
    return list(dict.fromkeys(urls))


async def _whatsapp_urls(after: str) -> list[str]:
    chats = _items("JJS_WHATSAPP_CHAT_JIDS")
    root = os.getenv("JJS_WHATSAPP_PLUGIN_ROOT", "").strip()
    if not chats or not root:
        return []
    environment = os.environ.copy()
    environment["WHATSAPP_BRIDGE_AUTO_START"] = "0"
    params = StdioServerParameters(
        command="bash",
        args=[str(Path(root) / "scripts" / "run-mcp.sh")],
        cwd=root,
        env=environment,
    )
    urls: list[str] = []
    for chat_jid in chats:
        urls.extend(
            _urls(
                await _call(
                    params,
                    "list_messages",
                    {
                        "chat_jid": chat_jid,
                        "after": after,
                        "limit": 100,
                        "include_context": False,
                    },
                )
            )
        )
    return list(dict.fromkeys(urls))


def _write_queue(directory: Path, source: str, urls: list[str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(TIMEZONE).isoformat(),
        "urls": urls,
    }
    temporary = directory / f".{source}-referrals.tmp"
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(directory / f"{source}-referrals.json")


async def main() -> None:
    lookback_days = max(1, int(os.getenv("MESSAGE_LOOKBACK_DAYS", "14")))
    after = (datetime.now(TIMEZONE) - timedelta(days=lookback_days)).isoformat()
    state_dir = Path(
        os.getenv("JJS_PRIVATE_STATE_DIR", "~/.local/share/jjs-event-agent")
    ).expanduser()
    telegram, whatsapp = await asyncio.gather(_telegram_urls(after), _whatsapp_urls(after))
    _write_queue(state_dir, "telegram", telegram)
    _write_queue(state_dir, "whatsapp", whatsapp)
    print(f"Private referral queues refreshed: telegram={len(telegram)}, whatsapp={len(whatsapp)}")


if __name__ == "__main__":
    asyncio.run(main())
