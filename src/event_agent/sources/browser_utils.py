from __future__ import annotations

import base64
import json
from typing import Any


def parse_cookie_json(raw: str, *, default_domain: str) -> list[dict[str, Any]]:
    """Parse JSON (or base64-encoded JSON) into Playwright-compatible cookies."""
    if not raw.strip():
        return []
    payload = raw.strip()
    if not payload.startswith(("[", "{")):
        try:
            payload = base64.b64decode(payload, validate=True).decode()
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Cookie secret is neither JSON nor base64-encoded JSON") from exc
    parsed = json.loads(payload)
    if isinstance(parsed, dict):
        parsed = [
            {"name": name, "value": value, "domain": default_domain, "path": "/"}
            for name, value in parsed.items()
        ]
    if not isinstance(parsed, list):
        raise ValueError("Cookie JSON must be an object or an array")
    cookies: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        cookie = dict(item)
        cookie.setdefault("domain", default_domain)
        cookie.setdefault("path", "/")
        if cookie.get("sameSite") not in {"Strict", "Lax", "None"}:
            cookie.pop("sameSite", None)
        cookies.append(cookie)
    return cookies

