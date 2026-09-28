"""On while an official RCB or RSO message about a threat from the air is in force for the place's
voivodeship (rule 4: current, not an exercise or cancelled; an RCB alert until its end, 12 hours at
most after its latest sending; where an end went to part of its area, only the rest). It is the
official layer, shown apart: it never changes the level, and it says "for the voivodeship", because
a message narrowed to some powiats is still counted for the whole of it here.

Unavailable, never off, while it cannot be told: the document older than 60 s, or RCB's or RSO's
feed out of reach. "Off" means no message is in force, not that we cannot see."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import SanAlertConfigEntry, core
from .entity import SanAlertEntity


async def async_setup_entry(hass: HomeAssistant, entry: SanAlertConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([SanAlertOfficialSensor(entry.runtime_data, "official")])


class SanAlertOfficialSensor(SanAlertEntity, BinarySensorEntity):

    @property
    def available(self) -> bool:
        return core.official_available(self.coordinator.data, dt_util.utcnow())

    @property
    def is_on(self) -> bool:
        return bool(self._summary()["official"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self._summary()
        tiers = [m["tier"] for m in s["official"] or [] if m["tier"]]
        return {"messages": s["official"] or [], "highest_rcb_tier": max(tiers) if tiers else None,
                "voivodeship": s["voivodeship"], "notice": s["notice"]}
