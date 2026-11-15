"""Tests for the vehicle status poll interval driven by the push connection."""

from datetime import timedelta
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.mazda_cs.fcm_listener import MazdaFcmListener


def _listener(hass: HomeAssistant) -> MazdaFcmListener:
    listener = MazdaFcmListener(hass, MagicMock(), MagicMock())
    listener.enable_push_based_interval()
    return listener


async def test_push_connected_polls_hourly(hass: HomeAssistant) -> None:
    """With pushes arriving, the timed poll is only a safety net."""
    listener = _listener(hass)
    listener._on_mcs_state(True)
    assert listener._coordinator.update_interval == timedelta(hours=1)


async def test_push_down_polls_every_30_min(hass: HomeAssistant) -> None:
    """Without pushes, polling is the only source of updates."""
    listener = _listener(hass)
    listener._on_mcs_state(True)
    listener._on_mcs_state(False)
    assert listener._coordinator.update_interval == timedelta(minutes=30)


async def test_already_connected_when_enabled_polls_hourly(hass: HomeAssistant) -> None:
    """Enabling after MCS came up applies the hourly interval at once."""
    listener = MazdaFcmListener(hass, MagicMock(), MagicMock())
    listener._on_mcs_state(True)
    listener.enable_push_based_interval()
    assert listener._coordinator.update_interval == timedelta(hours=1)
