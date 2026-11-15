"""Tests for the health-report binary sensors."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mazda_cs import binary_sensor
from custom_components.mazda_cs.binary_sensor import (
    HEALTH_BINARY_SENSOR_ENTITIES,
    MazdaHealthBinarySensorEntity,
)
from custom_components.mazda_cs.const import DOMAIN


def _vehicle(has_fuel: bool = True) -> dict:
    return {
        "id": 1,
        "vin": "JM1TESTVIN",
        "modelYear": "2021",
        "carlineName": "CX-5",
        "hasFuel": has_fuel,
        "status": {},
    }


def _coordinator(hass: HomeAssistant, data: list) -> DataUpdateCoordinator:
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
    coordinator.data = data
    return coordinator


def _health_sensor(hass: HomeAssistant, key: str, health) -> MazdaHealthBinarySensorEntity:
    description = next(d for d in HEALTH_BINARY_SENSOR_ENTITIES if d.key == key)
    return MazdaHealthBinarySensorEntity(
        None,
        _coordinator(hass, [_vehicle()]),
        _coordinator(hass, [health]),
        0,
        description,
    )


@pytest.mark.parametrize(
    ("health", "expected"),
    [
        ({"warnings": {"oilAmountExceed": True}}, True),
        ({"warnings": {"oilAmountExceed": False}}, False),
        # getHealthReport failed for this vehicle.
        (None, None),
    ],
)
async def test_oil_overfill_warning(hass: HomeAssistant, health, expected) -> None:
    """The oil overfill sensor follows WngOilAmountExceed from the health report."""
    sensor = _health_sensor(hass, "health_oil_overfill", health)

    assert sensor.is_on is expected


@pytest.mark.parametrize(
    ("has_fuel", "expected_keys"),
    [
        (True, {"health_lights_problem", "health_oil_overfill"}),
        (False, {"health_lights_problem"}),
    ],
)
async def test_oil_overfill_only_for_fuel_vehicles(
    hass: HomeAssistant, monkeypatch, has_fuel, expected_keys
) -> None:
    """A vehicle without fuel (BEV) gets no oil sensor; the bulb sensor stays."""
    monkeypatch.setattr(binary_sensor, "BINARY_SENSOR_ENTITIES", [])
    entry = SimpleNamespace(
        runtime_data=SimpleNamespace(
            client=None,
            coordinator=_coordinator(hass, [_vehicle(has_fuel)]),
            health_coordinator=_coordinator(hass, [None]),
        )
    )
    add_entities = MagicMock()

    await binary_sensor.async_setup_entry(hass, entry, add_entities)

    added = add_entities.call_args.args[0]
    assert {e.entity_description.key for e in added} == expected_keys
