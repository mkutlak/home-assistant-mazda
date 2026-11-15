"""Tests for ``MazdaSensorEntity`` availability after a field disappears."""

import datetime
import logging
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mazda_cs.const import DOMAIN
from custom_components.mazda_cs.sensor import SENSOR_ENTITIES, MazdaSensorEntity


def _sensor(hass: HomeAssistant, key: str, status: dict) -> MazdaSensorEntity:
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    coordinator = DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name=DOMAIN,
        update_method=AsyncMock(),
        update_interval=None,
        config_entry=entry,
    )
    coordinator.data = [
        {
            "id": 1,
            "vin": "JM1TESTVIN",
            "modelYear": "2021",
            "carlineName": "CX-5",
            "status": status,
        }
    ]
    description = next(d for d in SENSOR_ENTITIES if d.key == key)
    return MazdaSensorEntity(None, coordinator, 0, description)


async def test_sensor_unavailable_when_field_disappears(hass: HomeAssistant) -> None:
    """A null frame after setup marks the sensor unavailable instead of raising."""
    sensor = _sensor(hass, "odometer", {"odometerKm": 1234.5})
    assert sensor.available is True
    assert sensor.native_value == 1234

    sensor.coordinator.data[0]["status"]["odometerKm"] = None

    assert sensor.available is False


async def test_position_timestamp_sensor(hass: HomeAssistant) -> None:
    """The position timestamp sensor reports the parsed AcquisitionDatetime."""
    acquired = datetime.datetime(2026, 8, 23, 11, 55, tzinfo=datetime.UTC)
    sensor = _sensor(hass, "position_timestamp", {"positionTimestamp": acquired})
    assert sensor.available is True
    assert sensor.native_value == acquired

    sensor.coordinator.data[0]["status"]["positionTimestamp"] = None

    assert sensor.available is False


async def test_battery_sensor_unavailable_above_127(hass: HomeAssistant) -> None:
    """socEcmAEst above 127 (invalid frame) would show more than 100 %."""
    sensor = _sensor(
        hass, "soc_ecm_a_est", {"batteryStatus": {"socEcmAEst": 127}}
    )
    assert sensor.available is True

    sensor.coordinator.data[0]["status"]["batteryStatus"]["socEcmAEst"] = 200

    assert sensor.available is False
