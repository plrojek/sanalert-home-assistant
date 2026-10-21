"""The time Home Assistant has held a document, on both clocks, with no Home Assistant (freshness.py)."""
from custom_components.sanalert.freshness import Held


class Clock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def doc(at="2026-10-20T12:00:00Z"):
    return {"generated_at": at, "cells": {}}


def held():
    clock, wall = Clock(), Clock(1_800_000_000.0)
    return Held(clock=clock, wall=wall), clock, wall


def tick(clock, wall, mono_s, wall_s=None):
    clock.t += mono_s
    wall.t += mono_s if wall_s is None else wall_s


def test_nothing_held_before_the_first_document():
    h, _, _ = held()
    assert h.held_s() is None and h.current(None) is None


def test_held_past_60_s_the_rules_see_no_document():
    h, clock, wall = held()
    d = doc()
    h.saw(d)
    tick(clock, wall, 60)
    assert h.current(d) is d
    tick(clock, wall, 1)
    assert h.held_s() == 61 and h.current(d) is None


def test_the_same_generated_at_keeps_its_first_sighting_and_a_new_one_starts_again():
    h, clock, wall = held()
    h.saw(doc())
    tick(clock, wall, 50)
    h.saw(doc())                                   # a 200 with the same document: still held since the first
    tick(clock, wall, 11)
    assert h.current(doc()) is None
    h.saw(doc("2026-10-20T12:01:01Z"))             # a new document
    assert h.held_s() == 0 and h.current(doc()) is not None


def test_a_machine_that_slept_counts_the_wall_clock():
    """The monotonic clock stops while the machine sleeps; the wall clock does not, and the larger wins."""
    h, clock, wall = held()
    h.saw(doc())
    tick(clock, wall, 6, 3600)
    assert h.held_s() == 3600 and h.current(doc()) is None


def test_a_wall_clock_set_back_counts_the_monotonic_clock():
    h, clock, wall = held()
    h.saw(doc())
    tick(clock, wall, 61, -3600)
    assert h.held_s() == 61 and h.current(doc()) is None
