import os
import time
import uuid

import pytest

pytest.importorskip("googleapiclient")
pytest.importorskip("google_auth_oauthlib")

from src import configs
from src import email_functions


pytestmark = pytest.mark.integration


def _get_required_env(name):
    value = os.getenv(name)
    if not value:
        pytest.skip(f"Missing required env var: {name}")
    return value


@pytest.fixture
def live_gmail_service(monkeypatch):
    if os.getenv("GMAIL_LIVE_TEST") != "1":
        pytest.skip("Set GMAIL_LIVE_TEST=1 to run live Gmail integration tests")

    token_path = _get_required_env("GMAIL_LIVE_TOKEN_PATH")
    credentials_path = _get_required_env("GMAIL_LIVE_CREDENTIALS_PATH")

    monkeypatch.setattr(configs, "TOKEN_PATH", token_path)
    monkeypatch.setattr(configs, "CREDENTIALS_PATH", credentials_path)

    return email_functions.gmail_authenticate()


def test_live_gmail_auth_and_query(live_gmail_service):
    query = os.getenv("GMAIL_LIVE_QUERY", "in:anywhere newer_than:30d")
    messages = email_functions._search_gmail_messages(live_gmail_service, query)

    assert isinstance(messages, list)


@pytest.mark.live_send
def test_live_gmail_send_and_find_message(live_gmail_service, monkeypatch):
    if os.getenv("GMAIL_LIVE_ALLOW_SEND") != "1":
        pytest.skip("Set GMAIL_LIVE_ALLOW_SEND=1 to run live send test")

    sender = _get_required_env("GMAIL_LIVE_ADDRESS")
    destination = os.getenv("GMAIL_LIVE_DESTINATION", sender)

    monkeypatch.setattr(configs, "GMAIL_ADDRESS", sender)

    marker = f"gmail-live-{uuid.uuid4().hex[:12]}"
    subject = f"Integration {marker}"
    body = f"This is a live integration test message: {marker}"

    sent = email_functions._send_gmail_message(
        live_gmail_service,
        destination=destination,
        obj=subject,
        body=body,
    )
    assert "id" in sent

    # Gmail indexing can take a short moment.
    time.sleep(3)

    found = email_functions._search_gmail_messages(
        live_gmail_service,
        f'subject:"{marker}" newer_than:1d',
    )
    assert found, "Could not find the message that was just sent"
