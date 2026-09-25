"""Adding a place: a name, a point on the map (Home Assistant's own location by default) and the
language of the descriptions. The point is kept in Home Assistant; we keep its grid cell and the
voivodeship it belongs to, read once from the public grid."""
from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
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

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            lat = float(user_input[CONF_LOCATION][CONF_LATITUDE])
            lon = float(user_input[CONF_LOCATION][CONF_LONGITUDE])
            cell = core.cell_id(lat, lon)
            try:
                voivodeship = await self._voivodeship(cell)
            except (aiohttp.ClientError, TimeoutError, ValueError, KeyError):
                errors["base"] = "cannot_connect"
            else:
                if voivodeship is None:
                    errors["base"] = "outside_poland"
                else:
                    await self.async_set_unique_id(cell)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=user_input[CONF_NAME], data={
                        CONF_NAME: user_input[CONF_NAME], CONF_LATITUDE: lat, CONF_LONGITUDE: lon,
                        CONF_LANGUAGE: user_input[CONF_LANGUAGE], CONF_CELL: cell, CONF_VOIVODESHIP: voivodeship,
                    })
        language = (self.hass.config.language or "").split("-")[0]
        schema = vol.Schema({
            vol.Required(CONF_NAME, default=self.hass.config.location_name or "Dom"): TextSelector(),
            vol.Required(CONF_LOCATION, default={CONF_LATITUDE: self.hass.config.latitude,
                                                 CONF_LONGITUDE: self.hass.config.longitude}):
                LocationSelector(LocationSelectorConfig(radius=False)),
            vol.Required(CONF_LANGUAGE, default=language if language in core.LANGUAGES else "pl"):
                SelectSelector(SelectSelectorConfig(options=list(core.LANGUAGES), translation_key="language",
                                                    mode=SelectSelectorMode.DROPDOWN)),
        })
        return self.async_show_form(step_id="user", data_schema=self.add_suggested_values_to_schema(schema, user_input),
                                    errors=errors)

    async def _voivodeship(self, cell: str) -> str | None:
        session = async_get_clientsession(self.hass)
        async with session.get(GRID_URL, headers={"User-Agent": USER_AGENT},
                               timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            grid = await resp.json(content_type=None)
        return grid["cells"].get(cell)
