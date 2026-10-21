"""How long Home Assistant has held the state document, so a clock that runs behind cannot keep an old
level fresh. The same rule as SanAlert's website (web/src/lib/freshness.ts) and its local MCP server.

core.py takes the document's age from this machine's clock. With that clock 2 h behind the server's,
the document looks 2 h "in the future": if the API then goes down, the last "quiet" stays fresh for
2 h and automations act on it. So the age is never less than the time held: once Home Assistant has
held one `generated_at` for more than rule 2's 60 s, the rules see no document at all, whatever the
clock says. Held time is counted on both clocks and the larger wins: the monotonic one stops while
the machine sleeps, the wall one can be set back.

No Home Assistant import, and kept out of core.py, which the MCP server copies byte for byte."""
from __future__ import annotations

import time
from collections.abc import Callable

from .core import MAX_AGE_S


class Held:
    def __init__(self, clock: Callable[[], float] | None = None, wall: Callable[[], float] | None = None) -> None:
        # Looked up at each call, not bound once, so a patched clock (Home Assistant's tests) is counted.
        self._clock = clock or (lambda: time.monotonic())
        self._wall = wall or (lambda: time.time())
        # When this `generated_at` was first seen, on both clocks.
        self._seen: tuple[object, float, float] | None = None

    def saw(self, doc: dict) -> None:
        """Call for every document accepted; keeps the first sighting of each `generated_at`."""
        at = doc.get("generated_at")
        if self._seen is None or self._seen[0] != at:
            self._seen = (at, self._clock(), self._wall())

    def held_s(self) -> float | None:
        """Seconds since the document's `generated_at` was first seen (None before the first one)."""
        if self._seen is None:
            return None
        return max(self._clock() - self._seen[1], self._wall() - self._seen[2])

    def current(self, state: dict | None) -> dict | None:
        """The document the rules may see: none once it has been held for more than 60 s."""
        held = self.held_s()
        return None if held is not None and held > MAX_AGE_S else state
