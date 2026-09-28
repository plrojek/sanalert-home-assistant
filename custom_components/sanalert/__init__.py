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
    # A new point or language (the options): the entities start again from it.
    entry.async_on_unload(entry.add_update_listener(_async_options_changed))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SanAlertConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entry 1.1 → 1.2: SanAlert 1.0.0 made the place's grid cell the entry's unique id, so a second
    place in the same ~11 km square could not be added, and a place moved in the options would keep
    its old cell as its id. A place is its entry now; its entities and its device always were
    (`entry_id`), so nothing else changes and an older version still loads the entry."""
    if entry.version == 1 and entry.minor_version < 2:
        hass.config_entries.async_update_entry(entry, unique_id=None, minor_version=2)
    return True


async def _async_options_changed(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
