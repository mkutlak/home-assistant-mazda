"""Tests that account identifiers stay out of logs and exception text."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mazda_cs.pymazda.connection import Connection, _redact
from custom_components.mazda_cs.pymazda.exceptions import MazdaException


@pytest.mark.parametrize(
    "key", ["sessionId", "contactMailAddress", "custId", "usherId", "internalUserId"]
)
def test_redact_hides_account_identifiers(key: str) -> None:
    """Attach and getUserInfo payloads carry these; debug logs must not."""
    assert _redact({"data": [{key: "secret-value"}]}) == {
        "data": [{key: "**REDACTED**"}]
    }


async def test_check_version_failure_hides_response(caplog) -> None:
    """A failed checkVersion must not echo the response into logs or the error."""
    resp = MagicMock(status=200)
    resp.json = AsyncMock(
        return_value={"state": "E", "errorCode": 400007, "payload": "LEAKED-PAYLOAD"}
    )
    session = MagicMock()
    session.request = AsyncMock(return_value=resp)
    conn = Connection("test-sub", "MNAO", AsyncMock(), websession=session)

    with caplog.at_level(logging.DEBUG), pytest.raises(MazdaException) as exc_info:
        await conn._Connection__api_request_to_url("POST", "https://x/checkVersion")

    assert "400007" in str(exc_info.value)
    assert "LEAKED-PAYLOAD" not in str(exc_info.value)
    assert "LEAKED-PAYLOAD" not in caplog.text
