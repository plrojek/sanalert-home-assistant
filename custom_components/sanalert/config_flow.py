"""Adding a place: a name, a point on the map (Home Assistant's own location by default) and the
language of the descriptions. The point is kept in Home Assistant; we keep its grid cell and the
voivodeship it belongs to, read once from the public grid. The options change the point and the
language later.

A place is its config entry: two places in one ~11 km square (a home and a school next to it) are two
entries, so the cell is not the entry's unique id (it was in 1.0; `async_migrate_entry` drops it)."""
from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from . import core
from .const import CONF_CELL, CONF_LANGUAGE, CONF_VOIVODESHIP, DOMAIN, GRID_URL, USER_AGENT


class SanAlertConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SanAlertOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            place, error = await _place(self.hass, user_input)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(title=user_input[CONF_NAME], data={CONF_NAME: user_input[CONF_NAME], **place})
        language = (self.hass.config.language or "").split("-")[0]
        schema = vol.Schema({
            vol.Required(CONF_NAME, default=self.hass.config.location_name or "Dom"): TextSelector(),
            **_place_schema({CONF_LATITUDE: self.hass.config.latitude, CONF_LONGITUDE: self.hass.config.longitude},
                            language if language in core.LANGUAGES else "pl"),
        })
        return self.async_show_form(step_id="user", data_schema=self.add_suggested_values_to_schema(schema, user_input),
                                    errors=errors)


class SanAlertOptionsFlow(OptionsFlow):
    """The point and the language, as when the place was added. The name is Home Assistant's to change
    (the entry's and the device's own rename). Saved as the entry's options; the entry reloads."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            place, error = await _place(self.hass, user_input)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(data=place)
        conf = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(_place_schema({CONF_LATITUDE: conf[CONF_LATITUDE], CONF_LONGITUDE: conf[CONF_LONGITUDE]},
                                          conf[CONF_LANGUAGE]))
        return self.async_show_form(step_id="init", data_schema=self.add_suggested_values_to_schema(schema, user_input),
                                    errors=errors)


def _place_schema(location: dict[str, float], language: str) -> dict:
    return {
        vol.Required(CONF_LOCATION, default=location): LocationSelector(LocationSelectorConfig(radius=False)),
        vol.Required(CONF_LANGUAGE, default=language):
            SelectSelector(SelectSelectorConfig(options=list(core.LANGUAGES), translation_key="language",
                                                mode=SelectSelectorMode.DROPDOWN)),
    }


async def _place(hass: HomeAssistant, user_input: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """The point, its cell and its voivodeship, and the language; or the form's error."""
    lat = float(user_input[CONF_LOCATION][CONF_LATITUDE])
    lon = float(user_input[CONF_LOCATION][CONF_LONGITUDE])
    cell = core.cell_id(lat, lon)
    try:
        voivodeship = await _voivodeship(hass, cell)
    except (aiohttp.ClientError, TimeoutError, ValueError, KeyError):
        return {}, "cannot_connect"
    if voivodeship is None:
        return {}, "outside_poland"
    return {CONF_LATITUDE: lat, CONF_LONGITUDE: lon, CONF_LANGUAGE: user_input[CONF_LANGUAGE], CONF_CELL: cell,
            CONF_VOIVODESHIP: voivodeship}, None


async def _voivodeship(hass: HomeAssistant, cell: str) -> str | None:
    session = async_get_clientsession(hass)
    async with session.get(GRID_URL, headers={"User-Agent": USER_AGENT},
                           timeout=aiohttp.ClientTimeout(total=15)) as resp:
        resp.raise_for_status()
        grid = await resp.json(content_type=None)
    return grid["cells"].get(cell)
