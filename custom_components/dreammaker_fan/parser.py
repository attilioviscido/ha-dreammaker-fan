"""Stream framing for the Dream Maker fan protocol.

The fans send JSON objects back to back over TCP, without a reliable
delimiter (some firmwares add ``\\x00`` or ``\\r\\n``). A single read() can
contain several objects or only part of one.

The approach mirrors ``JsonStreamParser`` from upstream dmiot2mqtt
(https://github.com/klada/dmiot2mqtt, klada, GPLv3): first isolate exactly one
object by counting braces (ignoring braces inside strings), and only then
decode it. A broken object is skipped by resynchronising on the next ``{``, so
it cannot block the messages that follow it.

Dream Maker specific addition: the provisioning request (resource 2000) has a
``tail`` field that contains raw backslashes which are not valid JSON escapes
(for example ``\\^``). ``_fix_invalid_escapes`` is applied only to the single
isolated message, and only after its first decode attempt failed.

This module has no Home Assistant dependencies so it can be unit tested on
its own.
"""
from __future__ import annotations

from collections import deque
import json
import logging
import re

_LOGGER = logging.getLogger(__name__)

# Largest amount of unparsed data kept per connection. A complete message is
# well below 1 KiB (the provisioning request is ~420 bytes), so anything larger
# means an object that never closes.
MAX_BUFFER_SIZE = 4 * 1024

# Deepest nesting accepted in a message. Fan messages are two levels deep.
MAX_DEPTH = 8

# Bytes that may separate two messages and are dropped silently.
_SEPARATORS = b" \t\r\n\x00"

# A backslash followed by a valid JSON escape is kept, any other backslash is
# doubled so it decodes as a literal backslash.
_ESCAPE_RE = re.compile(r'\\(["\\/bfnrt]|u[0-9a-fA-F]{4})|\\')


def _fix_invalid_escapes(text: str) -> str:
    """Double every backslash that does not start a valid JSON escape."""
    return _ESCAPE_RE.sub(lambda m: m.group(0) if m.group(1) else "\\\\", text)


def _find_object_end(buffer: bytes) -> int:
    """Return the index right after the object starting at ``buffer[0]``.

    Returns -1 if the object is not complete yet and -2 if it nests deeper than
    MAX_DEPTH. Braces inside strings (including escaped quotes) are ignored.
    Scanning bytes is safe because every character checked here is ASCII and
    never occurs inside a multi-byte UTF-8 sequence.
    """
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(buffer):
        if in_string:
            if escaped:
                escaped = False
            elif char == 0x5C:  # backslash
                escaped = True
            elif char == 0x22:  # double quote
                in_string = False
        elif char == 0x22:
            in_string = True
        elif char == 0x7B:  # {
            depth += 1
            if depth > MAX_DEPTH:
                return -2
        elif char == 0x7D:  # }
            depth -= 1
            if depth == 0:
                return index + 1
    return -1


def decode_message(raw: bytes) -> dict | None:
    """Decode one isolated JSON object, repairing invalid escapes if needed."""
    text = raw.decode("utf-8", "replace")
    try:
        message = json.loads(text)
    except json.JSONDecodeError as err:
        try:
            message = json.loads(_fix_invalid_escapes(text))
        except json.JSONDecodeError:
            _LOGGER.warning("Invalid JSON received, ignoring: %r", raw[:100])
            return None
        _LOGGER.debug("Repaired invalid escape(s) in message (%s at %s)", err.msg, err.pos)
    if not isinstance(message, dict):
        _LOGGER.debug("Ignoring non-object JSON: %r", raw[:100])
        return None
    return message


class JsonStreamParser:
    """Split the byte stream of one fan connection into JSON objects.

    Create one instance per connection. Incomplete data is kept until the
    rest arrives; completed messages wait in ``pending`` until they are taken.
    """

    def __init__(self, max_size: int = MAX_BUFFER_SIZE) -> None:
        self._buffer = b""
        self._max_size = max_size
        self.pending: deque[dict] = deque()

    def feed(self, data: bytes) -> list[dict]:
        """Add received data and return all messages completed by it.

        The returned messages are also appended to ``pending``.
        """
        self._buffer += data
        messages: list[dict] = []
        while self._buffer:
            start = self._buffer.find(b"{")
            if start == -1:
                if self._buffer.strip(_SEPARATORS):
                    _LOGGER.warning("Discarding non-JSON data: %r", self._buffer[:100])
                self._buffer = b""
                break
            if self._buffer[:start].strip(_SEPARATORS):
                _LOGGER.warning("Discarding non-JSON data: %r", self._buffer[:start][:100])
            self._buffer = self._buffer[start:]

            end = _find_object_end(self._buffer)
            if end == -1 and len(self._buffer) <= self._max_size:
                break  # incomplete, wait for more data
            if end < 0:
                # An object that never closes would swallow every following
                # message, so give up on it and look for the next one.
                _LOGGER.warning("Broken JSON object, skipping to the next one: %r", self._buffer[:100])
                next_start = self._buffer.find(b"{", 1)
                self._buffer = self._buffer[next_start:] if next_start != -1 else b""
                continue

            raw, self._buffer = self._buffer[:end], self._buffer[end:]
            message = decode_message(raw)
            if message is not None:
                messages.append(message)
        self.pending.extend(messages)
        return messages
