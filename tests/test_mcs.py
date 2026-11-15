"""Tests for the MCS push connection's reconnect and dead-link handling."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mazda_cs.pymazda.push import _mcs
from custom_components.mazda_cs.pymazda.push._mcs import LoginResponse, McsClient


class _ModuleAsyncio:
    """Stands in for ``asyncio`` inside _mcs only; records sleeps, stops after N."""

    def __init__(self, client: McsClient, stop_after: int) -> None:
        self.sleeps: list[float] = []
        self._client = client
        self._stop_after = stop_after

    def __getattr__(self, name):
        return getattr(asyncio, name)

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        if len(self.sleeps) >= self._stop_after:
            self._client._do_listen = False


def _client() -> McsClient:
    client = McsClient("1234", "token", on_message=lambda _data: None)
    client._do_listen = True
    return client


async def test_failed_login_backs_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rejected login must not reconnect every 3 s forever."""
    client = _client()
    failed = LoginResponse()
    failed.error.code = 401
    calls = 0

    async def recv():
        # Server answers the login with an error, then closes the stream.
        nonlocal calls
        calls += 1
        if calls % 2:
            return failed
        raise asyncio.IncompleteReadError(b"", 1)

    monkeypatch.setattr(client, "_connect_with_retry", AsyncMock(return_value=True))
    monkeypatch.setattr(client, "_login", AsyncMock())
    monkeypatch.setattr(client, "_recv", recv)
    monkeypatch.setattr(client, "_close_writer", AsyncMock())
    fake = _ModuleAsyncio(client, stop_after=9)
    monkeypatch.setattr(_mcs, "asyncio", fake)

    await client._listen()

    assert fake.sleeps == [3, 6, 12, 24, 48, 96, 192, 300, 300]


async def test_successful_login_resets_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """After a good login the next reconnect waits the minimum again."""
    client = _client()
    client._reconnect_delay = 300
    await client._dispatch(LoginResponse())
    assert client._reconnect_delay == 3


async def test_monitor_drops_silent_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """No traffic for 2x the heartbeat interval means the link is dead."""
    client = _client()
    client._writer = MagicMock()
    client._last_message_time = time.monotonic() - 3 * client._client_hb
    monkeypatch.setattr(client, "_send", AsyncMock())
    monkeypatch.setattr(client, "_close_writer", AsyncMock())
    monkeypatch.setattr(_mcs, "asyncio", _ModuleAsyncio(client, stop_after=2))

    await client._monitor()

    client._close_writer.assert_awaited_once()


async def test_connect_counts_as_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fresh connection must not be judged dead by the previous one's silence."""
    client = _client()
    client._last_message_time = 0.0
    fake = _ModuleAsyncio(client, stop_after=99)
    fake.open_connection = AsyncMock(return_value=(MagicMock(), MagicMock()))
    monkeypatch.setattr(_mcs, "asyncio", fake)

    assert await client._connect()
    assert time.monotonic() - client._last_message_time < 5


@pytest.mark.parametrize(
    "length_prefix",
    [b"\x80\x80\x80\x01", b"\x80\x80\x80\x80\x80\x01"],
    ids=["2MiB", "6-byte-varint"],
)
async def test_recv_rejects_oversized_length(length_prefix: bytes) -> None:
    """A huge or overlong length prefix is rejected before any read of the body."""
    client = _client()
    client._first_message = False
    client._reader = asyncio.StreamReader()
    client._reader.feed_data(bytes([3]) + length_prefix)
    client._reader.feed_eof()

    with pytest.raises(RuntimeError, match="MCS"):
        await client._recv()
