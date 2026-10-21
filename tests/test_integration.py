"""The integration inside Home Assistant: adding a place, the two entities, "no data" rather than
a stale calm, and one polite request with If-None-Match."""
import datetime as dt
import json
from pathlib import Path

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
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
    """A place as SanAlert 1.0.0 saved it: entry 1.1, its grid cell as the unique id."""
    return MockConfigEntry(domain=DOMAIN, title="Dom", unique_id="511:156", version=1, minor_version=1, data={
        CONF_NAME: "Dom", CONF_LATITUDE: 51.143, CONF_LONGITUDE: 23.471, CONF_LANGUAGE: language,
        CONF_CELL: "511:156", CONF_VOIVODESHIP: "lubelskie"})


def test_the_user_agent_carries_the_released_version():
    manifest = json.loads((Path(__file__).parents[1] / "custom_components/sanalert/manifest.json").read_text())
    assert USER_AGENT == f"SanAlert-HomeAssistant/{manifest['version']}"


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
    # The official sensor has no "no data" state of its own: it goes unavailable, never "off".
    official_id = [s.entity_id for s in hass.states.async_all("binary_sensor")][0]
    assert hass.states.get(official_id).state == "unavailable"



async def _set_up(hass, language="en"):
    e = entry(language=language)
    e.add_to_hass(hass)
    assert await hass.config_entries.async_setup(e.entry_id)
    await hass.async_block_till_done()
    return ([s.entity_id for s in hass.states.async_all("sensor")][0],
            [s.entity_id for s in hass.states.async_all("binary_sensor")][0])


async def _later(hass, freezer, seconds):
    freezer.tick(dt.timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_a_clock_running_behind_never_keeps_an_old_quiet_fresh(hass, aioclient_mock, freezer):
    """Home Assistant's clock 2 h behind the server's: the document looks 2 h "in the future". After one
    good fetch the API goes down; once Home Assistant has held the document for 60 s it is no data."""
    server_now = dt_util.utcnow() + dt.timedelta(hours=2)
    aioclient_mock.get(STATE_URL, json=state(server_now - dt.timedelta(seconds=5), level="quiet"))
    sensor_id, official_id = await _set_up(hass)
    assert hass.states.get(sensor_id).state == "quiet"
    assert hass.states.get(official_id).state == "off"
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATE_URL, exc=aiohttp.ClientError())
    await _later(hass, freezer, 30)                 # held 30 s: still the document it has
    assert hass.states.get(sensor_id).state == "quiet"
    await _later(hass, freezer, 31)                 # held 61 s: no data, whatever the clock says
    level = hass.states.get(sensor_id)
    assert level.state == "no_data" and level.attributes["reason"].startswith("We have no data")
    assert level.attributes["official"] is None
    # What must stay with the data is still the document's.
    assert level.attributes["notice"] == "Unofficial." and "NEPTUN (https://neptun.in.ua)" in level.attributes["attribution"]
    assert hass.states.get(official_id).state == "unavailable"


@pytest.mark.parametrize("behind", [dt.timedelta(0), dt.timedelta(hours=2)])
async def test_documents_that_keep_coming_stay_fresh(hass, aioclient_mock, freezer, behind):
    """Each new `generated_at` is held from when it came: a working API never reads no data, with Home
    Assistant's clock right or behind."""
    aioclient_mock.get(STATE_URL, json=state(dt_util.utcnow() + behind, seq=1))
    sensor_id, official_id = await _set_up(hass)
    assert hass.states.get(sensor_id).state == "approaching"
    for seq in range(2, 10):                        # 80 s in all, a new document every 10 s
        aioclient_mock.clear_requests()
        aioclient_mock.get(STATE_URL, json=state(dt_util.utcnow() + behind + dt.timedelta(seconds=10), seq=seq))
        await _later(hass, freezer, 10)
        assert hass.states.get(sensor_id).state == "approaching"
        assert hass.states.get(official_id).state == "off"


async def test_a_clock_running_ahead_reads_no_data_never_quiet(hass, aioclient_mock, freezer):
    """Home Assistant's clock ahead of the server's: the held time never makes a document younger than
    the clock says. 2 h ahead, every document looks 2 h old: no data from the start (safe, if useless,
    until the clock is put right)."""
    aioclient_mock.get(STATE_URL, json=state(dt_util.utcnow() - dt.timedelta(hours=2), level="quiet"))
    sensor_id, official_id = await _set_up(hass)
    assert hass.states.get(sensor_id).state == "no_data"
    assert hass.states.get(official_id).state == "unavailable"
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATE_URL, json=state(dt_util.utcnow() - dt.timedelta(hours=2) + dt.timedelta(seconds=10),
                                             level="quiet", seq=2))
    await _later(hass, freezer, 10)
    assert hass.states.get(sensor_id).state == "no_data"


async def test_a_clock_slightly_ahead_reaches_no_data_by_its_own_count(hass, aioclient_mock, freezer):
    """20 s ahead, with the API down: the clock's age passes 60 s after 41 s held, before the held time
    does. The larger of the two decides, so the held time never delays no data."""
    aioclient_mock.get(STATE_URL, json=state(dt_util.utcnow() - dt.timedelta(seconds=20), level="quiet"))
    sensor_id, _ = await _set_up(hass)
    assert hass.states.get(sensor_id).state == "quiet"
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATE_URL, exc=aiohttp.ClientError())
    await _later(hass, freezer, 30)                 # held 30 s, 50 s old by the clock
    assert hass.states.get(sensor_id).state == "quiet"
    await _later(hass, freezer, 11)                 # held 41 s, 61 s old by the clock
    assert hass.states.get(sensor_id).state == "no_data"

async def test_the_official_sensor_is_off_only_when_it_can_see(hass, aioclient_mock):
    now = dt_util.utcnow()
    doc = state(now, level="quiet")
    doc["health"]["sources"] = {"neptun": {"status": "ok", "age_s": 5}, "rcb": {"status": "ok", "age_s": 40},
                                "rso": {"status": "ok", "age_s": 40}}
    aioclient_mock.get(STATE_URL, json=doc)
    e = entry()
    e.add_to_hass(hass)
    assert await hass.config_entries.async_setup(e.entry_id)
    await hass.async_block_till_done()
    official_id = [s.entity_id for s in hass.states.async_all("binary_sensor")][0]
    assert hass.states.get(official_id).state == "off"
    # RSO out of reach: "no message" would be a guess.
    doc["health"]["sources"]["rso"] = {"status": "unknown", "age_s": None}
    aioclient_mock.clear_requests()
    aioclient_mock.get(STATE_URL, json=doc)
    async_fire_time_changed(hass, dt_util.utcnow() + dt.timedelta(seconds=11))
    await hass.async_block_till_done()
    assert hass.states.get(official_id).state == "unavailable"
    level = [s for s in hass.states.async_all("sensor")][0]
    assert level.state == "quiet" and level.attributes["official"] is None


async def test_two_places_in_one_square(hass, aioclient_mock):
    # A place saved by 1.0.0 keeps working, and gives up the cell as its id…
    aioclient_mock.get(GRID_URL, json=GRID)
    aioclient_mock.get(STATE_URL, json=state(dt_util.utcnow()))
    old = entry()
    old.add_to_hass(hass)
    data = dict(old.data)
    # Its entity as 1.0.0 registered it, renamed by its user: it must survive the migration.
    registry = er.async_get(hass)
    registry.async_get_or_create("sensor", DOMAIN, f"{old.entry_id}_level", config_entry=old,
                                 suggested_object_id="moj_dom_poziom")
    assert await hass.config_entries.async_setup(old.entry_id)
    await hass.async_block_till_done()
    assert old.unique_id is None and old.minor_version == 2 and dict(old.data) == data
    assert hass.states.get("sensor.moj_dom_poziom").state == "approaching"
    assert [e.entity_id for e in er.async_entries_for_config_entry(registry, old.entry_id) if e.domain == "sensor"] \
        == ["sensor.moj_dom_poziom"]
    # …so a school next door, in the same ~11 km square, is a place of its own.
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {
        CONF_NAME: "Szkoła", CONF_LOCATION: {CONF_LATITUDE: 51.139, CONF_LONGITUDE: 23.48}, CONF_LANGUAGE: "pl"})
    assert result["type"] is FlowResultType.CREATE_ENTRY and result["data"][CONF_CELL] == "511:156"
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert len(hass.states.async_all("sensor")) == 2


async def test_the_options_change_the_point_and_the_language(hass, aioclient_mock):
    aioclient_mock.get(GRID_URL, json=GRID)
    aioclient_mock.get(STATE_URL, json=state(dt_util.utcnow()))
    e = entry(language="pl")
    e.add_to_hass(hass)
    assert await hass.config_entries.async_setup(e.entry_id)
    await hass.async_block_till_done()
    sensor_id = [s.entity_id for s in hass.states.async_all("sensor")][0]
    assert hass.states.get(sensor_id).attributes["reason"].startswith("Dron leci")
    result = await hass.config_entries.options.async_init(e.entry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "init"
    # Abroad is refused here too.
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        CONF_LOCATION: {CONF_LATITUDE: 49.84, CONF_LONGITUDE: 24.03}, CONF_LANGUAGE: "en"})
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "outside_poland"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        CONF_LOCATION: {CONF_LATITUDE: 50.1, CONF_LONGITUDE: 22.4}, CONF_LANGUAGE: "en"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    # The same entities, reloaded for the new square (quiet there) and in English.
    level = hass.states.get(sensor_id)
    assert level.state == "quiet" and level.attributes["cell"] == "501:149"
    assert level.attributes["voivodeship"] == "podkarpackie"
    assert level.attributes["reason"] == "Nothing we track is heading for your place."
