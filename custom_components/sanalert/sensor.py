"""The level for the place: quiet, activity, approaching, near, or no_data (rule 2). Its attributes
say why, how old the data is, and which official messages are in force for the voivodeship."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SanAlertConfigEntry, core
from .entity import SanAlertEntity


async def async_setup_entry(hass: HomeAssistant, entry: SanAlertConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([SanAlertLevelSensor(entry.runtime_data, "level")])


class SanAlertLevelSensor(SanAlertEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(core.STATES)

    @property
    def native_value(self) -> str:
        return self._summary()["level"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self._summary()
        # Only what changes with the situation: the document's age moves every 10 s and would write
        # a state row to Home Assistant's database each time. Rule 2 still turns an old document
        # into "no_data" (core.level).
        for key in ("level", "data_age_s", "generated_at"):
            s.pop(key)
        return s
