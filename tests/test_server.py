"""End-to-end test of the TCP handshake with a simulated fan.

Home Assistant is stubbed in conftest.py; this exercises server.py over a
real socket: provisioning (2000) -> reply -> auth (2001) -> device created ->
state update -> command, plus async_stop() with a fan still connected.
"""
import asyncio
import json

import pytest

from conftest import DISPATCHED, server as srv
from test_parser import AUTH, PROVISIONING_RAW, STATE


async def _read_obj(reader, parser):
    while not parser.pending:
        data = await asyncio.wait_for(reader.read(4096), 2)
        assert data, "server closed the connection"
        parser.feed(data)
    return parser.pending.popleft()


def _free_port():
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_full_session_and_stop_with_fan_connected():
    asyncio.run(_session())


async def _session():
    DISPATCHED.clear()
    server = srv.DreamMakerServer(object(), "entry1", port=_free_port())
    await server.async_start()
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    rx = srv.JsonStreamParser()  # the simulated fan's own receive parser

    # provisioning request, split in two writes and with invalid escapes
    writer.write(PROVISIONING_RAW[:150])
    await writer.drain()
    await asyncio.sleep(0.05)
    writer.write(PROVISIONING_RAW[150:] + b"\x00")
    await writer.drain()
    reply = await _read_obj(reader, rx)
    assert reply["action"] == 81 and reply["resource_id"] == 2000
    assert reply["data"]["device_id"] == "X" * 12  # sn (redacted) used as device_id

    # auth + first state push in a single write
    writer.write(json.dumps(AUTH).encode() + json.dumps(STATE).encode())
    await writer.drain()
    ack = await _read_obj(reader, rx)
    assert ack["resource_id"] == 2001
    ack2 = await _read_obj(reader, rx)
    assert ack2["resource_id"] == 9031
    assert DISPATCHED and DISPATCHED[0][0] == "dreammaker_fan_new_device_entry1"
    device = DISPATCHED[0][1][0]
    assert device.state["speed"] == 40

    # command from HA to the fan
    await device.async_send_command({"power": 0})
    cmd = await _read_obj(reader, rx)
    assert cmd["action"] == 4 and cmd["resource_id"] == 9031 and cmd["data"] == {"power": 0}

    # unload while the fan is still connected must not hang
    await asyncio.wait_for(server.async_stop(), timeout=srv.CLOSE_TIMEOUT + 2)
    assert server._server is None
    writer.close()


async def _connect_and_auth(port, parser):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(json.dumps(AUTH).encode())
    await writer.drain()
    ack = await _read_obj(reader, parser)
    assert ack["resource_id"] == 2001
    return reader, writer


async def _is_closed_by_server(reader, timeout=2):
    try:
        return await asyncio.wait_for(reader.read(4096), timeout) == b""
    except (asyncio.TimeoutError, ConnectionError):
        return False


def test_reconnect_closes_previous_connection():
    asyncio.run(_reconnect())


async def _reconnect():
    DISPATCHED.clear()
    server = srv.DreamMakerServer(object(), "entry1", port=_free_port())
    await server.async_start()
    # first connection stays open, as the fan's socket did before a re-pairing
    old_reader, old_writer = await _connect_and_auth(server.port, srv.JsonStreamParser())
    device = DISPATCHED[0][1][0]

    rx = srv.JsonStreamParser()
    new_reader, new_writer = await _connect_and_auth(server.port, rx)
    assert await _is_closed_by_server(old_reader), "old connection was not closed"
    await asyncio.sleep(0.05)  # let the old handler finish
    assert len(DISPATCHED) == 1  # same device, not created again
    assert device.available  # the old handler must not mark it unavailable
    assert len(server._connections) == 1

    # commands go to the new connection
    await device.async_send_command({"power": 1})
    cmd = await _read_obj(new_reader, rx)
    assert cmd["data"] == {"power": 1}

    await server.async_stop()
    old_writer.close()
    new_writer.close()


def test_stop_with_stale_and_active_connection_is_fast(caplog):
    asyncio.run(_stop_stale_and_active())
    assert "Timeout waiting" not in caplog.text


async def _stop_stale_and_active():
    DISPATCHED.clear()
    server = srv.DreamMakerServer(object(), "entry1", port=_free_port())
    await server.async_start()
    # A stale socket from another address that no device references any more
    # (as left behind when a fan reconnects without closing its old socket),
    # plus an active, authenticated fan.
    stale_reader, stale_writer = await asyncio.open_connection(
        "127.0.0.1", server.port, local_addr=("127.0.0.2", 0)
    )
    await asyncio.sleep(0.05)
    server.devices.pop("127.0.0.2")
    _, active_writer = await _connect_and_auth(server.port, srv.JsonStreamParser())
    assert len(server._connections) == 2
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    await server.async_stop()
    elapsed = loop.time() - t0
    assert elapsed < 1, f"async_stop took {elapsed:.1f} s"
    assert not server._connections
    assert await _is_closed_by_server(stale_reader, timeout=1)
    stale_writer.close()
    active_writer.close()
