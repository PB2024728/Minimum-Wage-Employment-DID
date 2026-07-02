"""
Panel-integrity tests.

These guard the structural invariants the whole DiD design relies on: a balanced
51-jurisdiction x 64-quarter panel, no missing values in the model fields, a sane log
transform, and internally consistent treatment encoding (treated / post / treated_post /
event_time / cohort). If any of these break, every downstream estimate is suspect.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

N_JURIS = 51
N_QUARTERS = 64          # 2010Q1 .. 2025Q4
N_ROWS = N_JURIS * N_QUARTERS


def test_panel_shape_is_balanced(panel):
    assert len(panel) == N_ROWS, f"expected {N_ROWS} rows, got {len(panel)}"
    assert panel["jurisdiction"].nunique() == N_JURIS
    assert panel["quarter_ord"].nunique() == N_QUARTERS


def test_panel_is_strictly_balanced_per_state(panel):
    # every jurisdiction must appear in exactly all 64 quarters, no gaps, no dups
    counts = panel.groupby("jurisdiction")["quarter_ord"].nunique()
    assert (counts == N_QUARTERS).all(), counts[counts != N_QUARTERS].to_dict()
    dup = panel.duplicated(subset=["jurisdiction", "quarter_ord"]).sum()
    assert dup == 0, f"{dup} duplicate state-quarter rows"


def test_window_bounds(panel):
    assert panel["year"].min() == 2010
    assert panel["year"].max() == 2025
    assert panel["quarter_ord"].min() == 0
    assert panel["quarter_ord"].max() == N_QUARTERS - 1


def test_no_missing_in_model_fields(panel):
    for col in ["log_leih", "treated_post", "jurisdiction", "quarter_ord", "min_wage_level"]:
        assert panel[col].isna().sum() == 0, f"NA found in {col}"


def test_log_leih_matches_leih(panel):
    # log_leih must be the natural log of the employment level
    assert (panel["leih"] > 0).all()
    np.testing.assert_allclose(
        panel["log_leih"].to_numpy(),
        np.log(panel["leih"].to_numpy()),
        rtol=0, atol=1e-9,
    )


def test_leih_share_in_unit_interval(panel):
    s = panel["leih_share"]
    assert s.between(0, 1).all(), "leih_share outside [0,1]"
    # L&H is a real but minority slice of nonfarm employment
    assert 0.02 < s.mean() < 0.20


def test_treatment_dummies_are_binary(panel):
    for col in ["treated", "post", "treated_post"]:
        assert set(panel[col].unique()).issubset({0, 1}), col


def test_treated_post_is_interaction(panel):
    # treated_post must equal treated AND post, exactly
    expected = (panel["treated"].astype(int) & panel["post"].astype(int))
    assert (panel["treated_post"].astype(int) == expected).all()


def test_never_treated_have_no_post(panel):
    nt = panel[panel["treated"] == 0]
    assert (nt["post"] == 0).all()
    assert (nt["treated_post"] == 0).all()
    # never-treated jurisdictions have no relative event time
    assert nt["event_time"].isna().all()


def test_counts_match_documented_design(panel):
    treated_states = panel.loc[panel["treated"] == 1, "jurisdiction"].nunique()
    control_states = panel.loc[panel["treated"] == 0, "jurisdiction"].nunique()
    assert treated_states == 31, f"expected 31 treated states, got {treated_states}"
    assert control_states == 20, f"expected 20 never-treated, got {control_states}"


def test_post_turns_on_at_first_treat(panel):
    # for treated states, post must be 0 strictly before cohort and 1 from cohort onward
    treated = panel[panel["treated"] == 1].copy()
    g = treated.groupby("jurisdiction")
    for state, grp in g:
        grp = grp.sort_values("quarter_ord")
        first_ord = grp.loc[grp["post"] == 1, "quarter_ord"]
        if first_ord.empty:
            continue
        cut = first_ord.min()
        assert (grp.loc[grp["quarter_ord"] < cut, "post"] == 0).all(), state
        assert (grp.loc[grp["quarter_ord"] >= cut, "post"] == 1).all(), state


def test_event_time_zero_aligns_with_first_post(panel):
    treated = panel[(panel["treated"] == 1) & panel["event_time"].notna()].copy()
    # event_time == 0 rows should be exactly the first post quarter for that state
    z = treated[treated["event_time"] == 0]
    assert (z["post"] == 1).all()
