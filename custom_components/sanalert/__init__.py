"""SanAlert: the unofficial threat level from the air for one place in Poland (sanalert.pl).

Not an official warning system: it does not replace sirens, Alert RCB or instructions from the
services. The place stays in Home Assistant; only the public state document is fetched."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SanAlertCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type SanAlertConfigEntry = ConfigEntry[SanAlertCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SanAlertConfigEntry) -> bool:
    coordinator = SanAlertCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SanAlertConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
