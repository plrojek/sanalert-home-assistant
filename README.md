# SanAlert for Home Assistant

The unofficial threat level from the air for a place in Poland, as a Home Assistant sensor, so the
house can react: lights, a speaker, waking people at "Blisko". Not an official warning system: it
does not replace sirens, Alert RCB or instructions from the services.

## What it does, and what it sends

- Every 10 s it fetches `https://api.sanalert.pl/v1/state`, the same public document the website and
  the apps read, with `If-None-Match` and the User-Agent `SanAlert-HomeAssistant/<version>`.
- It looks the place's level up in that document (the rules SanAlert's website and apps follow, sanalert.pl/jak-to-dziala). **The place stays
  in Home Assistant**: no request carries it. Adding a place fetches the public grid
  (`/v1/grid/1.json`) once, to find its ~11 km square and its voivodeship.
- The privacy page says the same (sanalert.pl/prywatnosc, "Integracja SanAlert dla Home Assistant").
  [Terms](https://sanalert.pl/en/terms/) ([Regulamin](https://sanalert.pl/regulamin/),
  [Умови](https://sanalert.pl/ua/terms/)).

## Entities, per place

Entity ids follow Home Assistant's language when the place is added: `sensor.dom_poziom` in Polish,
`sensor.home_level` in English.

| Entity | State | Attributes |
|---|---|---|
| `sensor.<place>_level` (Poziom / Рівень) | `quiet`, `activity`, `approaching`, `near`, `no_data`, `out_of_range` | `rank` (0–3, none without data), `reason` (the website's sentence, in the chosen language), `reason_code`, `kind`, `km`, `eta_min`, `course_known`, `lost_at`, `oblast`, `raion`, `threat`, `risk`, `confidence`, `degraded`, `official` (none while the official layer cannot be told), `notice`, `attribution` |
| `binary_sensor.<place>_official` (Komunikat oficjalny dla województwa) | on while an RCB or RSO message about a threat from the air is in force for the voivodeship; unavailable while that cannot be told | `messages` (source, RCB tier 1–3, title, url, `first_seen`), `highest_rcb_tier` |

**Blind is not calm.** When the document is missing, invalid or older than 60 s, the level reads
`no_data`, never `quiet`, and the level entity stays available so an automation can act on it.

The official sensor is the official layer, apart from the level: it never changes the level, and it
is for the whole voivodeship, even when a message names only some powiats. An RCB alert stays on
until its end, or 12 hours after it was last sent if no end comes; when an end goes to part of its
area, it stays on only for the rest. The sensor is **unavailable**, never off, when the document is
older than 60 s or RCB's or RSO's messages could not be read: off means no message is in force, not
that SanAlert cannot see.

`reason_code` is one of `object_near`, `object_toward`, `object_nearby` (`course_known` false: its
direction is unknown), `ua_alarm_adjacent`, `area_warning` and `track_lost` (the sources lost an
object that was heading this way, at `lost_at`). A code this version does not know leaves `reason`
empty; the level still holds.

## Install

With [HACS](https://hacs.xyz): HACS → the three dots → Custom repositories → add
`https://github.com/plrojek/sanalert-home-assistant` as an Integration → install SanAlert → restart Home Assistant.

By hand: copy `custom_components/sanalert` into your Home Assistant `config/custom_components/` and
restart Home Assistant.

Then: Settings → Devices & services → Add integration → SanAlert. Choose the name, the point on the
map (your home by default) and the language of the descriptions (Polski, English, Українська).
Add it again for another place, even one in the same ~11 km square. To move a place or change its
language later: SanAlert → the place → Configure.

## An automation

```yaml
automation:
  - alias: "SanAlert: wake the house at Blisko"
    trigger:
      - platform: state
        entity_id: sensor.dom_poziom
        to: "near"
    action:
      - service: light.turn_on
        target: { area_id: sypialnia }
        data: { brightness_pct: 100, color_name: red }
      - service: tts.speak
        target: { entity_id: tts.google_translate_pl_pl }
        data:
          media_player_entity_id: media_player.salon
          message: "{{ state_attr('sensor.dom_poziom', 'reason') }}"
```

Say what the level is, not that someone must shelter: SanAlert is an estimate from open sources.

And when SanAlert cannot see, say so, rather than let a quiet house read as a quiet sky:

```yaml
automation:
  - alias: "SanAlert: say when there is no data"
    trigger:
      - platform: state
        entity_id: sensor.dom_poziom
        to: "no_data"
        for: { minutes: 2 }
    action:
      - service: notify.notify
        data:
          title: "SanAlert: brak danych"
          message: "{{ state_attr('sensor.dom_poziom', 'reason') }} Sprawdzaj komunikaty RCB."
```

## Tests

```sh
uv venv --python 3.13 .venv && uv pip install --python .venv/bin/python pytest-homeassistant-custom-component
.venv/bin/python -m pytest          # from integrations/home-assistant/
```

`tests/test_core.py` checks the contract's rules with no Home Assistant; `tests/test_integration.py`
adds a place, reads both entities, and checks the 304 path, "no data" after 60 s, the official
sensor going unavailable, two places in one square and the options.

## Licence

MIT, © 2026 Applied AI sp. z o.o. The data it reads is SanAlert's public API; its sources are named on
sanalert.pl/jak-to-dziala.
