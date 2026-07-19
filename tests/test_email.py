from datetime import datetime
from zoneinfo import ZoneInfo

from event_agent.config import Settings
from event_agent.models import Event
from event_agent.outputs import email as email_output

SGT = ZoneInfo("Asia/Singapore")


def _event() -> Event:
    return Event(
        source="LinkedIn",
        title="AI Builders Night",
        description="Organizer overview from the linked event page.",
        url="https://example.com/register",
        start_at=datetime(2026, 7, 20, 19, 0, tzinfo=SGT),
        location="Singapore",
        keywords=("AI", "Networking"),
        perks=("Pizza", "Networking"),
        free_evidence="",
        score=40,
        attendee_count=75,
    )


def _settings(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_RECIPIENT", "recipient@example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_SECURITY", "starttls")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-specific-secret")
    monkeypatch.setenv("SMTP_FROM", "sender@example.com")
    return Settings.from_env(tmp_path)


def test_email_summary_contains_detail_page_overview(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path, monkeypatch)
    message = email_output.build_email_summary(
        [_event()], settings, datetime(2026, 7, 18, 8, 0, tzinfo=SGT)
    )
    rendered = message.get_body(preferencelist=("plain",)).get_content()
    headers = message.as_string()
    assert "recipient@example.com" in headers
    assert "AI Builders Night" in rendered
    assert "Pizza" in rendered
    assert "75 going" in rendered
    assert "Organizer overview from the linked event page." in rendered
    assert "event description was provided" not in rendered
    assert "JJ's Event Agent" in headers


def test_email_delivery_uses_starttls_and_app_credential(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path, monkeypatch)
    calls: list[object] = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ehlo(self):
            calls.append("ehlo")

        def starttls(self, *, context):
            calls.append(("starttls", context is not None))

        def login(self, username, password):
            calls.append(("login", username, password))

        def send_message(self, message):
            calls.append(("send", message["To"]))

    monkeypatch.setattr(email_output.smtplib, "SMTP", FakeSMTP)
    sent = email_output.send_email_summary(
        [_event()], settings, datetime(2026, 7, 18, 8, 0, tzinfo=SGT)
    )
    assert sent is True
    assert ("connect", "smtp.example.com", 587, 30) in calls
    assert ("starttls", True) in calls
    assert ("login", "sender@example.com", "app-specific-secret") in calls
    assert ("send", "recipient@example.com") in calls


def test_email_is_safely_skipped_when_credentials_are_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    settings = Settings.from_env(tmp_path)
    assert email_output.send_email_summary([], settings, datetime.now(SGT)) is False
