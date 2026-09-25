"""The integration inside Home Assistant: adding a place, the two entities, "no data" rather than
a stale calm, and one polite request with If-None-Match."""
import datetime as dt

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.sanalert.const import (CONF_CELL, CONF_LANGUAGE, CONF_VOIVODESHIP, DOMAIN, GRID_URL,
                                              STATE_URL, USER_AGENT)

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


GRID = {"v": 1, "cells": {"511:156": "lubelskie", "501:149": "podkarpackie"}}


def state(now, level="approaching", official=None, seq=1):
    return {"v": 1, "sequence": seq, "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "levels_valid": True,
            "health": {"status": "ok"}, "objects": [], "regions": {}, "ua_alarms": [],
            "cells": {"511:156": {"level": level, "risk": 60, "confidence": "medium",
                                  "drivers": [{"code": "object_toward", "kind": "drone", "km": 61, "eta_min": 20}]}},
            "official": official or [], "notice": {"pl": "Nieoficjalny.", "en": "Unofficial.", "uk": "Неофіційний."},
            "attribution": [{"name": "NEPTUN", "url": "https://neptun.in.ua"}]}


def entry(language="pl"):
    return MockConfigEntry(domain=DOMAIN, title="Dom", unique_id="511:156", data={
        CONF_NAME: "Dom", CONF_LATITUDE: 51.143, CONF_LONGITUDE: 23.471, CONF_LANGUAGE: language,
        CONF_CELL: "511:156", CONF_VOIVODESHIP: "lubelskie"})


async def test_adding_a_place_in_poland(hass, aioclient_mock):
    aioclient_mock.get(GRID_URL, json=GRID)
    aioclient_mock.get(STATE_URL, json=state(dt_util.utcnow()))
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {
        CONF_NAME: "Chełm", CONF_LOCATION: {CONF_LATITUDE: 51.143, CONF_LONGITUDE: 23.471}, CONF_LANGUAGE: "uk"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CELL] == "511:156" and result["data"][CONF_VOIVODESHIP] == "lubelskie"
    await hass.async_block_till_done()


async def test_a_place_abroad_is_refused(hass, aioclient_mock):
    aioclient_mock.get(GRID_URL, json=GRID)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {
        CONF_NAME: "Lwów", CONF_LOCATION: {CONF_LATITUDE: 49.84, CONF_LONGITUDE: 24.03}, CONF_LANGUAGE: "pl"})
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "outside_poland"}


async def test_the_level_its_reason_and_the_official_layer(hass, aioclient_mock):
    now = dt_util.utcnow()
    official = [{"source": "rcb", "class": "shelter", "title": "Alert RCB", "regions": ["lubelskie"],
                 "date": now.astimezone(dt.timezone(dt.timedelta(hours=2))).date().isoformat(), "cancelled": False,
                 "url": "https://www.gov.pl/web/rcb/x", "first_seen": None}]
    aioclient_mock.get(STATE_URL, json=state(now, official=official), headers={"ETag": '"1"'})
    e = entry()
    e.add_to_hass(hass)
    assert await hass.config_entries.async_setup(e.entry_id)
    await hass.async_block_till_done()
    level = hass.states.get("sensor.dom_poziom") or hass.states.get("sensor.dom_level")
    assert level is not None, [s.entity_id for s in hass.states.async_all()]
    assert level.state == "approaching"
    assert level.attributes["reason"] == "Dron leci w tę stronę: około 20 min, 61 km."
    assert level.attributes["rank"] == 2 and level.attributes["eta_min"] == 20
    assert "NEPTUN (https://neptun.in.ua)" in level.attributes["attribution"]
    assert "data_age_s" not in level.attributes and "generated_at" not in level.attributes
    official_state = [s for s in hass.states.async_all("binary_sensor")][0]
    assert official_state.state == "on" and official_state.attributes["highest_rcb_tier"] == 3
    # The one request said who is asking, and nothing else about anybody.
    assert aioclient_mock.mock_calls[0][3]["User-Agent"] == USER_AGENT


async def test_an_old_document_reads_no_data_not_calm(hass, aioclient_mock, freezer):
    now = dt_util.utcnow()
    aioclient_mock.get(STATE_URL, json=state(now, level="quiet"), headers={"ETag": '"1"'})
    e = entry(language="en")
    e.add_to_hass(hass)
    assert await hass.config_entries.async_setup(e.entry_id)
    await hass.async_block_till_done()
    sensor_id = [s.entity_id for s in hass.states.async_all("sensor")][0]
    assert hass.states.get(sensor_id).state == "quiet"
    # The server answers 304 from now on (same document), then stops answering at all.
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATE_URL, status=304)
    freezer.tick(dt.timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert aioclient_mock.mock_calls[-1][3].get("If-None-Match") == '"1"'
    assert hass.states.get(sensor_id).state == "quiet"
    freezer.tick(dt.timedelta(seconds=40))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(sensor_id).state == "no_data"
    assert hass.states.get(sensor_id).attributes["reason"].startswith("We have no data")
