"""
Estimator-sanity tests.

Two jobs: (1) confirm the estimation code reproduces the *published* headline numbers from
results/comparison_table.csv when re-run on the committed panel, so the deck and findings can
be trusted; (2) confirm the TWFE machinery behaves correctly on synthetic data with a known
planted effect (recovers it) and a known-null design (returns ~0). The second job catches
regressions in the estimator that a single real-data point estimate could hide.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import estimate_did as ed


# ---- reproduce published estimates on the real panel ----------------------

def test_twfe_reproduces_published_estimate(panel):
    df = ed.load_panel()
    res = ed.fit_twfe(df)
    coef = res.params[ed.TREAT]
    # published TWFE: -0.0268 log pts, SE 0.0140 (comparison_table.csv)
    assert coef == pytest.approx(-0.0268, abs=2e-3), coef
    assert res.bse[ed.TREAT] == pytest.approx(0.0140, abs=3e-3)
    # clustered on the 51 jurisdictions
    assert res.cov_type == "cluster"


def test_pooled_ols_reproduces_published_estimate(panel):
    df = ed.load_panel()
    res = ed.fit_pooled_ols(df)
    coef = res.params[ed.TREAT]
    # published pooled OLS: -0.0063 log pts
    assert coef == pytest.approx(-0.0063, abs=2e-3), coef


def test_pooled_and_twfe_differ_as_documented(panel):
    # the whole point of the design: fixed effects move the estimate (strip confounding)
    df = ed.load_panel()
    pooled = ed.fit_pooled_ols(df).params[ed.TREAT]
    twfe = ed.fit_twfe(df).params[ed.TREAT]
    assert abs(twfe - pooled) > 0.01, "FE should shift the estimate by ~0.02 log pts"


def test_twfe_is_more_precise_than_pooled(panel):
    df = ed.load_panel()
    pooled = ed.fit_pooled_ols(df)
    twfe = ed.fit_twfe(df)
    # absorbing state/period variation tightens the SE substantially
    assert twfe.bse[ed.TREAT] < pooled.bse[ed.TREAT]


# ---- synthetic recovery / null tests --------------------------------------

def _make_synthetic_panel(effect: float, n_states: int = 30, n_periods: int = 40,
                          n_treated: int = 15, seed: int = 7) -> pd.DataFrame:
    """Staggered-adoption synthetic panel with state + period FE and a known ATT `effect`
    (in log points) applied additively to treated_post == 1 cells."""
    rng = np.random.default_rng(seed)
    state_fe = rng.normal(0, 0.5, n_states)
    period_fe = np.linspace(0, 0.3, n_periods) + rng.normal(0, 0.01, n_periods)
    # staggered cohorts spread across the middle of the window
    cohorts = {s: (rng.integers(n_periods // 4, 3 * n_periods // 4) if s < n_treated else None)
               for s in range(n_states)}
    rows = []
    for s in range(n_states):
        for t in range(n_periods):
            treated = int(cohorts[s] is not None)
            post = int(treated and t >= cohorts[s])
            tp = treated * post
            y = (3.5 + state_fe[s] + period_fe[t]
                 + effect * tp
                 + rng.normal(0, 0.02))
            rows.append({"log_leih": y, "treated_post": tp,
                         "jurisdiction": f"S{s:02d}", "quarter_ord": t})
    return pd.DataFrame(rows)


def test_twfe_recovers_planted_negative_effect():
    df = _make_synthetic_panel(effect=-0.05)
    res = ed.fit_twfe(df)
    assert res.params[ed.TREAT] == pytest.approx(-0.05, abs=0.01)


def test_twfe_recovers_planted_positive_effect():
    df = _make_synthetic_panel(effect=+0.08)
    res = ed.fit_twfe(df)
    assert res.params[ed.TREAT] == pytest.approx(+0.08, abs=0.01)


def test_twfe_returns_null_when_no_effect():
    df = _make_synthetic_panel(effect=0.0)
    res = ed.fit_twfe(df)
    coef = res.params[ed.TREAT]
    assert coef == pytest.approx(0.0, abs=0.01)
    # and the null should not be flagged significant
    assert res.pvalues[ed.TREAT] > 0.05


def test_pct_effect_conversion_is_consistent():
    # extract() converts log coef -> approx pct via exp(coef)-1
    df = _make_synthetic_panel(effect=-0.05)
    res = ed.fit_twfe(df)
    row = ed.extract(res, "twfe", df, n_clusters=df["jurisdiction"].nunique())
    assert row["pct_effect"] == pytest.approx(100 * (np.exp(row["coef"]) - 1), abs=1e-6)
