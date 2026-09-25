"""On while an official RCB or RSO message about a threat from the air is in force for the place's
voivodeship (rule 4: current, not an exercise or cancelled; RCB only on its own date). It is the
official layer, shown apart: it never changes the level, and it says "for the voivodeship", because
a message narrowed to some powiats is still counted for the whole of it here."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SanAlertConfigEntry
from .entity import SanAlertEntity


async def async_setup_entry(hass: HomeAssistant, entry: SanAlertConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([SanAlertOfficialSensor(entry.runtime_data, "official")])


class SanAlertOfficialSensor(SanAlertEntity, BinarySensorEntity):

    @property
    def is_on(self) -> bool:
        return bool(self._summary()["official"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self._summary()
        tiers = [m["tier"] for m in s["official"] if m["tier"]]
        return {"messages": s["official"], "highest_rcb_tier": max(tiers) if tiers else None,
                "voivodeship": s["voivodeship"], "notice": s["notice"]}
