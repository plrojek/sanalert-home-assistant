"""What every SanAlert entity shares: the place's device, and the summary worked out from the state."""
from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import core
from .const import CONF_CELL, CONF_LANGUAGE, CONF_VOIVODESHIP, DOMAIN
from .coordinator import SanAlertCoordinator


class SanAlertEntity(CoordinatorEntity[SanAlertCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SanAlertCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._cell = entry.data[CONF_CELL]
        self._voivodeship = entry.data[CONF_VOIVODESHIP]
        self._language = entry.data[CONF_LANGUAGE]
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.data[CONF_NAME], manufacturer="Applied AI",
            model="SanAlert", entry_type=DeviceEntryType.SERVICE, configuration_url="https://sanalert.pl")

    @property
    def available(self) -> bool:
        # Blind is not calm: with no document, or an old one, the level reads "no_data" rather than
        # the entity going unavailable, so an automation can act on it. The official sensor has no
        # such state and goes unavailable instead (binary_sensor.py).
        return True

    def _summary(self) -> dict[str, Any]:
        return core.summary(self.coordinator.data, self._cell, self._voivodeship, dt_util.utcnow(), self._language)

    @property
    def attribution(self) -> str:
        return core.attribution(self.coordinator.data)
