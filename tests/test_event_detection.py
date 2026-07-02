"""
Treatment-event detection tests.

The single most error-prone step in this design is deciding what counts as a state
minimum-wage *increase event*. The rule (build_panel.detect_events) records an event only
when, in year y, the state wage both (a) rose above its prior year and (b) sits strictly above
the binding federal floor. This excludes the mechanical 2009->2010 federal step and states
that merely track the $7.25 floor. These tests pin that logic with synthetic series and then
cross-check the committed events_table.csv against the panel.
"""
from __future__ import annotations

import pandas as pd
import pytest

import build_panel as bp


def _annual(d: dict) -> pd.Series:
    return pd.Series(d, dtype=float)


# fed floor flat at 7.25 across the whole window (as it was 2010-2025)
FED = _annual({y: 7.25 for y in range(2009, 2026)})


def test_genuine_state_increase_above_floor_is_detected():
    mw = _annual({2009: 8.00, 2010: 8.00, 2011: 8.25, 2012: 8.25})
    ev = bp.detect_events(mw, FED, "CA")
    years = {e["event_year"] for e in ev}
    assert 2011 in years          # 8.00 -> 8.25, above floor
    assert 2012 not in years      # flat, no event


def test_increase_that_stays_at_or_below_floor_is_not_an_event():
    # state rises 7.00 -> 7.20 but never exceeds the 7.25 federal floor
    mw = _annual({2009: 7.00, 2010: 7.10, 2011: 7.20})
    ev = bp.detect_events(mw, FED, "CA")
    assert ev == [], "increase below federal floor must not be an event"


def test_federal_floor_step_is_not_a_state_event():
    # classic federal-floor state: jumps with the 2009->2010 federal hike then sits at 7.25
    mw = _annual({2009: 6.55, 2010: 7.25, 2011: 7.25, 2012: 7.25})
    ev = bp.detect_events(mw, FED, "CA")
    assert ev == [], "tracking the federal floor must not register as a state policy event"


def test_event_size_is_computed_correctly():
    mw = _annual({2009: 10.00, 2010: 11.00})
    ev = bp.detect_events(mw, FED, "CA")
    assert len(ev) == 1
    e = ev[0]
    assert e["prev_wage"] == pytest.approx(10.00)
    assert e["new_wage"] == pytest.approx(11.00)
    assert e["increase_abs"] == pytest.approx(1.00)
    assert e["increase_pct"] == pytest.approx(10.0, abs=0.01)
    assert e["event_quarter"] == "2010Q1"


def test_decrease_is_never_an_event():
    mw = _annual({2009: 12.00, 2010: 11.00, 2011: 11.00})
    ev = bp.detect_events(mw, FED, "CA")
    assert ev == []


def test_multiple_increases_each_register():
    mw = _annual({2009: 8.0, 2010: 9.0, 2011: 9.0, 2012: 10.0})
    ev = bp.detect_events(mw, FED, "CA")
    assert {e["event_year"] for e in ev} == {2010, 2012}


# ---- cross-checks against the committed artifacts -------------------------

def test_events_table_matches_documented_totals(events):
    assert len(events) == 307, f"expected 307 events, got {len(events)}"
    assert events["jurisdiction"].nunique() == 31


def test_every_event_is_above_federal_floor(events):
    assert (events["new_wage"] > events["fed_floor"]).all()


def test_every_event_is_an_increase(events):
    assert (events["new_wage"] > events["prev_wage"]).all()
    assert (events["increase_abs"] > 0).all()
    assert (events["increase_pct"] > 0).all()


def test_no_statute_states_never_appear_as_events(events):
    no_statute = {"AL", "LA", "MS", "SC", "TN"}
    assert not (set(events["jurisdiction"]) & no_statute)


def test_event_states_are_flagged_treated_in_panel(panel, events):
    treated_states = set(panel.loc[panel["treated"] == 1, "jurisdiction"])
    event_states = set(events["jurisdiction"])
    assert event_states <= treated_states, event_states - treated_states


def test_first_event_quarter_matches_panel_cohort(panel, events):
    # the earliest event year per state should match that state's cohort_year in the panel
    first_event_yr = events.groupby("jurisdiction")["event_year"].min()
    cohort_yr = (panel[panel["treated"] == 1]
                 .groupby("jurisdiction")["cohort_year"].first())
    common = first_event_yr.index.intersection(cohort_yr.index)
    assert len(common) > 0
    for st in common:
        assert int(first_event_yr[st]) == int(cohort_yr[st]), st
