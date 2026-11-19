"""Unit tests for the stream parser (no Home Assistant needed).

Run with:  python3 -m pytest tests
"""
import json

from conftest import parser as p

JsonStreamParser = p.JsonStreamParser

AUTH = {
    "action": 1, "resource_id": 2001, "version": "zeico_3.0.0", "msg_id": 0,
    "data": {"device_id": "SN0000000000", "device_key": "0000000000000000"},
}
HEARTBEAT = {"action": 1, "resource_id": 127, "version": "zeico_3.0.0", "data": {"signal": 66}}
STATE = {
    "action": 84, "resource_id": 9031, "version": "zeico_3.0.0", "msg_id": 1,
    "data": {"power": 1, "speed": 40, "mode": 0, "source": "manual", "temperature": 16.9},
}

# Provisioning request (resource 2000) with raw backslashes in "tail" that are
# not valid JSON escapes (here "\^" and "\Q").
# REAL PAYLOAD captured from a DM-FAN02-W during provisioning (factory reset +
# re-pairing via the Dream Maker app, DNS redirect to Home Assistant), 427 bytes.
# Redacted: product_id, sn, prov_code, mac, mark, local_ip, ssid -> 'X'; every
# character of "tail" -> 'x' except the backslash sequences, which are kept
# exactly as sent by the fan ("\^" and "\Q" are not valid JSON escapes).
PROVISIONING_RAW = (
    b'{"action": 1,"resource_id":2000,"version":"zeico_3.0.0","msg_id":0,'
    b'"data":{"product_id":"XXXXXXXXXXXXXXXXXXXXXXXX","sn":"XXXXXXXXXXXX",'
    b'"prov_code":"XXXXXXXXXXXXXXXX","mac":"XXXXXXXXXXXX","mark":"XXXXXX",'
    b'"local_ip":"XXXXXXXXXXXX","local_id":1,"local_port":8080,'
    b'"product_model":"fan02-w","product_type":"fan",'
    b'"factory_name":"dreammaker","ssid":"XXXXXXXXXXXXXXXXX",'
    b'"tail":"xxxx\\^xxxxxxxxxxxxxxxxxxxxxxxxxxxx\\Qxxxxxxxxxxxxxxxxxx"}}'
)


def test_provisioning_sample_really_is_invalid_json():
    # Guard: the sample must keep the invalid escapes, otherwise the
    # repair test below proves nothing.
    try:
        json.loads(PROVISIONING_RAW.decode())
    except json.JSONDecodeError as err:
        assert "Invalid \\escape" in err.msg
    else:
        raise AssertionError("sample unexpectedly decodes without repair")


def test_partial_message_waits_for_rest():
    parser = JsonStreamParser()
    raw = json.dumps(STATE).encode()
    cut = raw.index(b"manual") + 3  # inside a string value
    assert parser.feed(raw[:cut]) == []
    assert parser.feed(raw[cut:]) == [STATE]


def test_message_split_byte_by_byte():
    parser = JsonStreamParser()
    raw = json.dumps(AUTH).encode()
    out = []
    for i in range(len(raw)):
        out += parser.feed(raw[i:i + 1])
    assert out == [AUTH]


def test_two_concatenated_messages():
    parser = JsonStreamParser()
    raw = (json.dumps(AUTH) + json.dumps(HEARTBEAT)).encode()
    assert parser.feed(raw) == [AUTH, HEARTBEAT]


def test_nul_separator():
    parser = JsonStreamParser()
    raw = json.dumps(AUTH).encode() + b"\x00" + json.dumps(HEARTBEAT).encode() + b"\x00"
    assert parser.feed(raw) == [AUTH, HEARTBEAT]


def test_crlf_separator():
    parser = JsonStreamParser()
    raw = json.dumps(AUTH).encode() + b"\r\n" + json.dumps(HEARTBEAT).encode() + b"\r\n"
    assert parser.feed(raw) == [AUTH, HEARTBEAT]


def test_separators_do_not_log_warnings(caplog):
    parser = JsonStreamParser()
    parser.feed(b"\x00\r\n" + json.dumps(HEARTBEAT).encode() + b"\r\n\x00")
    assert not [r for r in caplog.records if r.levelname == "WARNING"]


def test_braces_and_escaped_quotes_inside_strings():
    parser = JsonStreamParser()
    message = {"action": 1, "data": {"ssid": 'my{wifi}"x\\', "other": "}}{{"}}
    assert parser.feed(json.dumps(message).encode() + json.dumps(HEARTBEAT).encode()) == [
        message,
        HEARTBEAT,
    ]


def test_corrupt_object_followed_by_valid_one():
    parser = JsonStreamParser()
    raw = b'{"broken": tru}' + json.dumps(HEARTBEAT).encode()
    assert parser.feed(raw) == [HEARTBEAT]


def test_junk_before_message_is_skipped():
    parser = JsonStreamParser()
    assert parser.feed(b"garbage " + json.dumps(HEARTBEAT).encode()) == [HEARTBEAT]


def test_unterminated_object_does_not_block_forever():
    parser = JsonStreamParser(max_size=200)
    heartbeat = json.dumps(HEARTBEAT).encode()
    assert parser.feed(b'{"x": 1' + heartbeat * 10) == [HEARTBEAT] * 10


def test_buffer_is_capped():
    parser = JsonStreamParser(max_size=200)
    parser.feed(b'{"x": "' + b"a" * 1000)
    assert len(parser._buffer) <= 200


def test_deep_nesting_is_dropped():
    parser = JsonStreamParser()
    assert parser.feed(b"{" * 20000) == []
    assert len(parser._buffer) <= p.MAX_DEPTH


def test_invalid_escape_provisioning_payload():
    parser = JsonStreamParser()
    messages = parser.feed(PROVISIONING_RAW)
    assert len(messages) == 1
    msg = messages[0]
    assert msg["resource_id"] == 2000
    assert msg["data"]["sn"] == "X" * 12
    assert msg["data"]["product_model"] == "fan02-w"
    # the raw backslashes survive as literal backslashes
    assert msg["data"]["tail"] == "xxxx\\^" + "x" * 28 + "\\Q" + "x" * 18


def test_invalid_escape_payload_split_and_followed_by_auth():
    parser = JsonStreamParser()
    raw = PROVISIONING_RAW + b"\x00" + json.dumps(AUTH).encode()
    cut = raw.index(b"\\^") + 1  # split right after the backslash
    first = parser.feed(raw[:cut])
    rest = parser.feed(raw[cut:])
    assert first == []
    assert [m["resource_id"] for m in rest] == [2000, 2001]


def test_escape_repair_is_local_to_one_message():
    # A valid message with a legitimate escaped backslash must not be altered
    # by the repair of a neighbouring broken message.
    parser = JsonStreamParser()
    valid = {"action": 1, "resource_id": 127, "data": {"path": "a\\nb"}}
    raw = PROVISIONING_RAW + json.dumps(valid).encode()
    msgs = parser.feed(raw)
    assert msgs[1] == valid


def test_pending_queue_per_parser():
    a, b = JsonStreamParser(), JsonStreamParser()
    a.feed(json.dumps(AUTH).encode())
    assert list(a.pending) == [AUTH]
    assert not b.pending


def test_fix_invalid_escapes_keeps_valid_ones():
    text = r'"a\n\t\"\\\/\u00e9\^\Q"'
    assert json.loads(p._fix_invalid_escapes(text)) == 'a\n\t"\\/\u00e9\\^\\Q'
