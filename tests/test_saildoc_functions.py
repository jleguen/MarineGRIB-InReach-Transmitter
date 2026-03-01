import base64
import zlib
from datetime import datetime
from unittest.mock import MagicMock

from src import saildoc_functions


def test_encode_saildocs_grib_file_roundtrip(tmp_path):
    source = b"\x00\x01GRIB\x00payload"
    grib_file = tmp_path / "sample.grb"
    grib_file.write_bytes(source)

    encoded = saildoc_functions.encode_saildocs_grib_file(str(grib_file))

    decoded = zlib.decompress(base64.b64decode(encoded.encode("utf-8")))
    assert decoded == source


def test_wait_for_saildocs_response_returns_when_newer_than_request(monkeypatch):
    monkeypatch.setattr(saildoc_functions.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        saildoc_functions.email_func,
        "_search_gmail_messages",
        lambda *_: [{"id": "msg-1"}],
    )

    auth_service = MagicMock()
    auth_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "payload": {"headers": [{"value": "unused"}, {"value": "2024-01-01 00:00:05 (UTC)"}]}
    }

    result = saildoc_functions.wait_for_saildocs_response(
        auth_service, datetime(2024, 1, 1, 0, 0, 0)
    )

    assert result == {"id": "msg-1"}


def test_wait_for_saildocs_response_times_out_when_no_newer_message(monkeypatch):
    monkeypatch.setattr(saildoc_functions.time, "sleep", lambda *_: None)
    monkeypatch.setattr(
        saildoc_functions.email_func,
        "_search_gmail_messages",
        lambda *_: [{"id": "msg-1"}],
    )

    auth_service = MagicMock()
    auth_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
        "payload": {"headers": [{"value": "unused"}, {"value": "2023-12-31 23:59:59 (UTC)"}]}
    }

    result = saildoc_functions.wait_for_saildocs_response(
        auth_service, datetime(2024, 1, 1, 0, 0, 0)
    )

    assert result is None
