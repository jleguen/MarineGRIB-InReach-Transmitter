from src import inreach_functions


def test_split_message_chunks_and_format(monkeypatch):
    monkeypatch.setattr(inreach_functions.configs, "MESSAGE_SPLIT_LENGTH", 5)

    parts = inreach_functions._split_message("abcdefghijk")

    assert parts == [
        "msg 1/3:\nabcde\nend",
        "msg 2/3:\nfghij\nend",
        "msg 3/3:\nk\nend",
    ]


def test_send_messages_to_inreach_sends_each_chunk_without_real_post(monkeypatch):
    monkeypatch.setattr(inreach_functions.configs, "MESSAGE_SPLIT_LENGTH", 4)

    calls = []

    def fake_post(url, message_str, _send_context=None):
        calls.append((url, message_str))
        return {"status_code": 200, "message": message_str}

    monkeypatch.setattr(inreach_functions, "_post_request_to_inreach", fake_post)
    monkeypatch.setattr(
        inreach_functions,
        "_build_send_context",
        lambda *_: {"mode": "legacy", "guid": "abc"},
    )
    monkeypatch.setattr(inreach_functions.time, "sleep", lambda *_: None)

    responses = inreach_functions.send_messages_to_inreach(
        "https://explore.garmin.com/TextMessage/TxtMsg?extId=abc&adr=foo",
        "abcdefgh",
    )

    assert len(calls) == 2
    assert calls[0][1] == "msg 1/2:\nabcd\nend"
    assert calls[1][1] == "msg 2/2:\nefgh\nend"
    assert len(responses) == 2


def test_extract_hidden_field():
    html = '<input id="MessageId" type="hidden" value="187639628" /><input id="Guid" type="hidden" value="abc-guid" />'
    assert inreach_functions._extract_hidden_field(html, "MessageId") == "187639628"
    assert inreach_functions._extract_hidden_field(html, "Guid") == "abc-guid"


def test_extract_ext_id():
    url = "https://eur.explore.garmin.com/textmessage/txtmsg?extId=gl_i6_pv7sZD3CBIVB9zf3g"
    assert inreach_functions._extract_ext_id(url) == "gl_i6_pv7sZD3CBIVB9zf3g"
