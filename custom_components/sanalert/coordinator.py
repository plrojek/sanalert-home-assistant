"""One request for the public state document every 10 s, the same one everybody gets, with
If-None-Match. The place never leaves Home Assistant: the level is looked up here (core.py)."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL, STATE_URL, USER_AGENT

_LOGGER = logging.getLogger(__name__)


class SanAlertCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """Holds the last state document. A failed request keeps the last one: its `generated_at` ages,
    and after 60 s the place reads "no data" (rule 2: blind is not calm), so the entities stay
    available and never fall back to a calm they cannot know."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self._etag: str | None = None
        self._failing = False

    async def _async_update_data(self) -> dict[str, Any] | None:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if self._etag and self.data is not None:
            headers["If-None-Match"] = self._etag
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(STATE_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 304:
                    return self.data
                resp.raise_for_status()
                data = await resp.json(content_type=None)
                self._etag = resp.headers.get("ETag")
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            if not self._failing:
                _LOGGER.warning("SanAlert state unavailable (%s); the level reads no data after 60 s", err)
            self._failing = True
            return self.data
        if self._failing:
            _LOGGER.info("SanAlert state available again")
        self._failing = False
        return data if isinstance(data, dict) else self.data
