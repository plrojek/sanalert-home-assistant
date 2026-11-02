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
    # How old the data is reaches an automation (rule 2) without a database row every 10 s: these two
    # move with every update and are kept out of the recorder (copy cut, AX; 1.2.0).
    _unrecorded_attributes = frozenset({"data_age_s", "generated_at"})

    @property
    def native_value(self) -> str:
        return self._summary()["level"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self._summary()
        # The level is the state itself. `data_age_s` and `generated_at` stay, out of the recorder
        # (`_unrecorded_attributes`); rule 2 still turns an old document into "no_data" (core.level).
        s.pop("level")
        return s
