"""The contract's rules for one place (SanAlert's API contract), with no Home Assistant."""
import datetime as dt

from custom_components.sanalert import core

NOW = dt.datetime(2026, 9, 23, 21, 0, tzinfo=dt.timezone.utc)


def state(age_s=5, **over):
    doc = {"v": 1, "generated_at": (NOW - dt.timedelta(seconds=age_s)).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "levels_valid": True, "health": {"status": "ok"}, "cells": {}, "official": [],
           "notice": {"pl": "Nieoficjalny.", "en": "Unofficial.", "uk": "Неофіційний."},
           "attribution": [{"name": "NEPTUN", "url": "https://neptun.in.ua"}]}
    doc.update(over)
    return doc


def test_grid_is_the_contracts_with_its_epsilon():
    assert core.cell_id(50.9, 23.1) == "509:154"          # 50.9 * 10 is 508.999… without the epsilon
    assert core.cell_id(51.143, 23.471) == "511:156"      # Chełm
    assert core.cell_id(49.8, 22.77) == "498:151"


def test_a_missing_cell_is_quiet_and_a_listed_one_is_its_level():
    assert core.level(state(), "511:156", True, NOW) == "quiet"
    s = state(cells={"511:156": {"level": "approaching", "risk": 60, "confidence": "medium", "drivers": []}})
    assert core.level(s, "511:156", True, NOW) == "approaching"


def test_blind_is_not_calm():
    assert core.level(None, "511:156", True, NOW) == "no_data"
    assert core.level(state(levels_valid=False), "511:156", True, NOW) == "no_data"
    assert core.level(state(health={"status": "unknown"}), "511:156", True, NOW) == "no_data"
    assert core.level(state(age_s=61), "511:156", True, NOW) == "no_data"
    assert core.level(state(age_s=59), "511:156", True, NOW) == "quiet"
    assert core.level(state(health={"status": "degraded"}), "511:156", True, NOW) == "quiet"
    assert core.degraded(state(health={"status": "degraded"}))


def test_outside_poland_is_out_of_range():
    assert core.level(state(), "504:240", False, NOW) == "out_of_range"


def test_official_in_force_for_the_voivodeship_only():
    msgs = [
        {"source": "rcb", "class": "shelter", "title": "Alert", "regions": ["lubelskie"], "date": "2026-09-23",
         "cancelled": False, "url": "u1", "first_seen": "2026-09-23T20:14:00Z"},
        {"source": "rcb", "class": "precaution", "title": "Old", "regions": ["lubelskie"], "date": "2026-09-22",
         "cancelled": False, "url": "u2"},
        {"source": "rcb", "class": "heightened", "title": "Off", "regions": ["lubelskie"], "date": "2026-09-23",
         "cancelled": True, "url": "u3"},
        {"source": "rso", "class": "exercise", "title": "Drill", "regions": ["lubelskie"], "url": "u4"},
        {"source": "rso", "class": "warning", "title": "RSO", "regions": ["podkarpackie"], "url": "u5"},
    ]
    got = core.current_official(state(official=msgs), "lubelskie", NOW)
    assert [m["url"] for m in got] == ["u1"] and got[0]["tier"] == 3
    assert [m["url"] for m in core.current_official(state(official=msgs), "podkarpackie", NOW)] == ["u5"]
    # With no time of ours for its sending, an RCB alert stands on its own date in Poland: 23:59 in
    # Poland on the 23rd is still the 23rd (UTC 21:59).
    undated = [{**msgs[0], "first_seen": None}]
    late = dt.datetime(2026, 9, 23, 21, 59, tzinfo=dt.timezone.utc)
    assert core.current_official(state(official=undated), "lubelskie", late)[0]["url"] == "u1"
    after_midnight = dt.datetime(2026, 9, 23, 22, 1, tzinfo=dt.timezone.utc)
    assert core.current_official(state(official=undated), "lubelskie", after_midnight) == []


def at_warsaw(day, hh, mm):
    """A September 2026 moment given in Polish time (CEST, UTC+2)."""
    return dt.datetime(2026, 9, day, hh, mm, tzinfo=core.WARSAW)


def test_an_rcb_alert_stands_overnight_until_its_end():
    # 24/25.09: the alert of 22:01 stood after midnight, and its end came at 05:40. The sensor went
    # off at 00:00 and automations fired "end".
    alert = {"source": "rcb", "class": "precaution", "title": "Alert RCB", "regions": ["lubelskie", "podkarpackie"],
             "date": "2026-09-24", "cancelled": False, "url": "u", "first_seen": "2026-09-24T20:01:00Z", "updates": []}
    for now in (at_warsaw(24, 22, 5), at_warsaw(25, 0, 30), at_warsaw(25, 5, 39)):
        assert [m["url"] for m in core.current_official(state(official=[alert]), "lubelskie", now)] == ["u"], now
    end = {"class": "cancellation", "text": "…", "regions": [], "ended": True, "again": False, "seen": "2026-09-25T03:40:00Z"}
    ended = {**alert, "cancelled": True, "cancelled_seen": "2026-09-25T03:40:00Z", "updates": [end], "regions_in_force": []}
    assert core.current_official(state(official=[ended]), "lubelskie", at_warsaw(25, 5, 41)) == []
    # With no end at all, 12 hours after its latest sending; an end is not a sending.
    assert core.current_official(state(official=[alert]), "lubelskie", at_warsaw(25, 10, 0))
    assert core.current_official(state(official=[alert]), "lubelskie", at_warsaw(25, 10, 1)) == []
    again = {**alert, "updates": [{"class": "precaution", "text": "…", "regions": ["lubelskie"], "ended": False,
                                   "again": True, "seen": "2026-09-25T06:13:00Z"}]}
    assert core.current_official(state(official=[again]), "lubelskie", at_warsaw(25, 12, 0))   # sent again: 12 h again


def test_an_end_for_part_of_the_area_leaves_the_rest_in_force():
    # 24.09, 07:05: the end went to lubelskie; podkarpackie stood (`regions_in_force`).
    alert = {"source": "rcb", "class": "heightened", "title": "Alert RCB", "regions": ["lubelskie", "podkarpackie"],
             "regions_in_force": ["podkarpackie"], "date": "2026-09-24", "cancelled": False, "url": "u",
             "first_seen": "2026-09-24T04:10:00Z",
             "updates": [{"class": "cancellation", "text": "…", "regions": ["lubelskie"], "ended": True, "again": False,
                          "seen": "2026-09-24T05:05:00Z"}]}
    now = at_warsaw(24, 7, 30)
    assert core.current_official(state(official=[alert]), "lubelskie", now) == []
    assert [m["tier"] for m in core.current_official(state(official=[alert]), "podkarpackie", now)] == [2]
    # `null`: the page's messages could not be told apart, so the whole of `regions` stands.
    unread = {**alert, "regions_in_force": None}
    assert core.current_official(state(official=[unread]), "lubelskie", now)


def test_the_official_layer_is_not_told_from_an_old_document_or_a_dead_feed():
    assert core.official_available(state(age_s=59), NOW)
    assert not core.official_available(None, NOW)
    assert not core.official_available(state(age_s=61), NOW)
    assert not core.official_available(state(health={"status": "ok", "sources": {"rcb": {"status": "unknown", "age_s": None}}}), NOW)
    assert not core.official_available(state(health={"status": "ok", "sources": {"rso": {"status": "unknown", "age_s": None}}}), NOW)
    # NEPTUN blind is not RCB blind: the official layer still stands on its own feeds.
    assert core.official_available(state(levels_valid=False, health={"status": "unknown", "sources": {
        "neptun": {"status": "unknown", "age_s": None}, "rcb": {"status": "ok", "age_s": 30}}}), NOW)
    # The level sensor says None, not "no message", when it cannot be told.
    assert core.summary(state(age_s=120), "511:156", "lubelskie", NOW, "pl")["official"] is None
    assert core.summary(state(), "511:156", "lubelskie", NOW, "pl")["official"] == []


def test_the_reason_in_three_languages():
    d = [{"code": "object_toward", "kind": "drone", "km": 61, "eta_min": 20}]
    assert core.explain("pl", "approaching", d) == "Dron leci w tę stronę: około 20 min, 61 km."
    assert core.explain("en", "approaching", d) == "Drone is heading this way: about 20 min, 61 km."
    assert core.explain("uk", "approaching", d) == "Дрон летить у цей бік: приблизно 20 хв, 61 км."
    a = [{"code": "ua_alarm_adjacent", "oblast": "volyn", "raion": "Volodymyrskyi", "threat": "drone"}]
    assert core.explain("pl", "activity", a) == "Alarm w obwodzie wołyńskim za granicą, rejon Volodymyrskyi: zagrożenie dronami."
    assert core.explain("uk", "activity", a) == "Тривога у Волинській області, за кордоном, Volodymyrskyi район: загроза від дронів."
    w = [{"code": "area_warning", "kind": "drone", "oblast": "crimea"}]
    assert core.explain("uk", "activity", w) == "Попередження для всього Криму: дрони. Джерело не знає, де вони."
    assert core.explain("en", "no_data", []).startswith("We have no data")
    assert core.explain("pl", "activity", [{"code": "something_new"}]) == ""


def test_summary_for_automations():
    s = state(cells={"511:156": {"level": "near", "risk": 90, "confidence": "high",
                                 "drivers": [{"code": "object_near", "kind": "cruise_missile", "km": 18}]}})
    got = core.summary(s, "511:156", "lubelskie", NOW, "en")
    assert got["level"] == "near" and got["rank"] == 3 and got["km"] == 18 and got["risk"] == 90
    assert got["reason"] == "Cruise missile is near, about 18 km from here."
    assert got["notice"] == "Unofficial." and "NEPTUN (https://neptun.in.ua)" in got["attribution"]
    blind = core.summary(state(age_s=120, cells=s["cells"]), "511:156", "lubelskie", NOW, "pl")
    assert blind["level"] == "no_data" and blind["rank"] is None and blind["risk"] is None and blind["km"] is None
