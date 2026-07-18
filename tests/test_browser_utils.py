import base64

from event_agent.sources.browser_utils import parse_cookie_json


def test_parses_object_cookie_json() -> None:
    cookies = parse_cookie_json('{"session":"secret"}', default_domain=".example.com")
    assert cookies == [
        {"name": "session", "value": "secret", "domain": ".example.com", "path": "/"}
    ]


def test_parses_base64_cookie_array() -> None:
    raw = base64.b64encode(b'[{"name":"session","value":"secret"}]').decode()
    cookies = parse_cookie_json(raw, default_domain=".example.com")
    assert cookies[0]["domain"] == ".example.com"

