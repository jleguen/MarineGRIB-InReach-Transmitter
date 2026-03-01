import base64
from unittest.mock import MagicMock

import pytest

pytest.importorskip("googleapiclient")
pytest.importorskip("google_auth_oauthlib")

from src import email_functions


def test_get_new_message_id_returns_only_unprocessed(monkeypatch):
    monkeypatch.setattr(
        email_functions,
        "_search_gmail_messages",
        lambda *_: [{"id": "a"}, {"id": "b"}, {"id": "c"}],
    )

    new_ids = email_functions._get_new_message_ID(object(), {"b", "x"})

    assert new_ids == {"a", "c"}


def test_fetch_message_text_and_url_parses_body_fields(monkeypatch):
    monkeypatch.setattr(
        email_functions.configs, "BASE_GARMIN_REPLY_URL", "explore.garmin.com"
    )
    raw_body = (
        "ECMWF:24n,34n,72w,60w|8,8|12,48|wind,press\r\n"
        "https://explore.garmin.com/TextMessage/TxtMsg?extId=abc123&adr=foo\r\n"
    )
    encoded_body = base64.urlsafe_b64encode(raw_body.encode("utf-8")).decode("utf-8")

    auth_service = MagicMock()
    auth_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "payload": {"body": {"data": encoded_body}}
    }

    msg_text, reply_url = email_functions._fetch_message_text_and_url(
        "id-1", auth_service
    )

    assert msg_text == "ecmwf:24n,34n,72w,60w|8,8|12,48|wind,press"
    assert (
        reply_url
        == "https://explore.garmin.com/TextMessage/TxtMsg?extId=abc123&adr=foo"
    )


def test_fetch_message_text_and_url_resolves_inreach_short_link(monkeypatch):
    monkeypatch.setattr(
        email_functions.configs, "BASE_GARMIN_REPLY_URL", "inreachlink.com"
    )
    raw_body = (
        "ECMWF:24n,34n,72w,60w|8,8|12,48|wind,press\r\n"
        "https://inreachlink.com/gl_i6_pv7sZD3CBIVB9zf3g\r\n"
    )
    encoded_body = base64.urlsafe_b64encode(raw_body.encode("utf-8")).decode("utf-8")

    auth_service = MagicMock()
    auth_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "payload": {"body": {"data": encoded_body}}
    }
    monkeypatch.setattr(
        email_functions,
        "resolve_url_direct",
        lambda *_: (
            "https://eur.explore.garmin.com/textmessage/txtmsg?extId=gl_i6_pv7sZD3CBIVB9zf3g"
        ),
    )

    _, reply_url = email_functions._fetch_message_text_and_url("id-1", auth_service)

    assert (
        reply_url
        == "https://eur.explore.garmin.com/textmessage/txtmsg?extId=gl_i6_pv7sZD3CBIVB9zf3g"
    )


def test_resolve_url_direct_returns_final_location(monkeypatch):
    class DummyResponse:
        url = "https://eur.explore.garmin.com/textmessage/txtmsg?extId=abc"

    monkeypatch.setattr(
        email_functions.requests,
        "get",
        lambda *_args, **_kwargs: DummyResponse(),
    )

    resolved = email_functions.resolve_url_direct("https://inreachlink.com/abc")

    assert resolved == "https://eur.explore.garmin.com/textmessage/txtmsg?extId=abc"


def test_process_new_inreach_message_returns_none_when_no_unanswered(monkeypatch):
    monkeypatch.setattr(email_functions, "_load_previous_messages", lambda: {"a"})
    monkeypatch.setattr(email_functions, "_get_new_message_ID", lambda *_: set())

    assert email_functions.process_new_inreach_message(object()) is None


def test_process_new_inreach_message_processes_and_records_message(monkeypatch):
    appended = []

    monkeypatch.setattr(email_functions, "_load_previous_messages", lambda: set())
    monkeypatch.setattr(email_functions, "_get_new_message_ID", lambda *_: {"m1"})
    monkeypatch.setattr(
        email_functions,
        "_request_and_process_saildocs_grib",
        lambda *_: (
            "/tmp/result.grb",
            "https://explore.garmin.com/TextMessage/TxtMsg?extId=abc&adr=foo",
        ),
    )
    monkeypatch.setattr(
        email_functions, "_append_to_previous_messages", appended.append
    )

    result = email_functions.process_new_inreach_message(object())

    assert result == (
        "/tmp/result.grb",
        "https://explore.garmin.com/TextMessage/TxtMsg?extId=abc&adr=foo",
    )
    assert appended == ["m1"]
