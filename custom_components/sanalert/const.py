"""SanAlert for Home Assistant: constants."""
from datetime import timedelta

DOMAIN = "sanalert"
VERSION = "0.1.0"
STATE_URL = "https://api.sanalert.pl/v1/state"
GRID_URL = "https://api.sanalert.pl/v1/grid/1.json"
# SanAlert's API contract, rule 6: a surface that is always on polls on its own schedule and says which of
# ours is asking in the User-Agent, nothing else about anybody. Home Assistant runs day and night and
# drives automations, so it asks every 10 s, like the Mac's menu bar label; the document is CDN-cached.
USER_AGENT = f"SanAlert-HomeAssistant/{VERSION}"
SCAN_INTERVAL = timedelta(seconds=10)

CONF_LANGUAGE = "language"
CONF_CELL = "cell"
CONF_VOIVODESHIP = "voivodeship"
