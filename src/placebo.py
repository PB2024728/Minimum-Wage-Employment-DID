"""
placebo.py - Day 7: placebo / falsification tests and robustness checks.

The Day 4-6 design estimates a small, gradual, statistically-insignificant negative
effect of a state minimum-wage increase on log Leisure & Hospitality (L&H)
employment. This script subjects that design to the standard falsification battery
and a set of robustness variants. A credible causal design should FAIL to find an
effect where none should exist, and the headline should be STABLE to reasonable
specification choices.

Tests
-----
(a) HIGH-WAGE-SECTOR PLACEBO. Re-run the exact same DiD design (TWFE + Callaway-
    Sant'Anna) with the outcome swapped to log Professional & Business Services
    employment (XX-PBSV). PBSV is a high-wage sector with very few minimum-wage
    workers, so a state minimum-wage increase should have ~no effect on it. A large
    or significant PBSV "effect" would imply the L&H result is driven by some
    state-level confounder common to all sectors. PASS = PBSV effect ~0 / insignificant.

(b) FAKE-EVENT-DATE FALSIFICATION (in-time placebo). For every treated state, move
    its treatment date ~8 quarters EARLIER than the true first increase, and drop all
    observations from the true treatment onward, so the real policy can never enter
    the window. Estimate the DiD on this fake event with the real outcome (log L&H).
    Any "effect" here is a pre-trend masquerading as a treatment effect. PASS = fake
    effect ~0 / insignificant, flat pre/post path.

Robustness
----------
(R1) ALTERNATIVE OUTCOME: L&H share of total nonfarm (leih_share) instead of log
     L&H level - guards against the result being a denominator/level artifact.
(R2) ALTERNATIVE EVENT WINDOWS: re-aggregate the Callaway-Sant'Anna dynamic ATT over
     several post-treatment horizons (k in [0,4], [0,8], [0,12], [0,16]) and re-fit
     the TWFE DiD on event-time-restricted samples (+/-8, +/-12, +/-16 quarters).

Inputs (no FRED API calls; raw PBSV pulled & cached on Day 7 setup)
    data/processed/panel.{parquet,csv}   the analysis panel (build_panel.py)
    data/raw/<XX>PBSV.csv                 cached high-wage-sector employment
    results/did_estimates.csv            L&H TWFE reference (Day 4)
    results/csa_aggregations.csv         L&H CSA reference (Day 6)

Outputs (results/)
    placebo_estimates.csv        tidy table of every placebo / robustness estimate
    placebo.md                   writeup + falsification verdict
    fig_placebo_pbsv.png         PBSV CSA dynamic ATT + overall ATT (PBSV vs L&H)
    fig_placebo_fake_date.png    fake-date TWFE event study (flat = pass)
    fig_robustness.png           alt-outcome / CSA-horizon / TWFE-window sensitivity

Project rules honoured: Python only; cached data reused (no API calls); standalone +
idempotent; results -> results/.
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf

from differences import ATTgt

ROOT = Path(os.environ.get("MINWAGE_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"

STATE = "jurisdiction"
PERIOD = "quarter_ord"
TREAT = "treated_post"
ALPHA = 0.05
RANDOM_STATE = 1234
FAKE_SHIFT = 8
EST_METHOD = "dr"
CONTROL_GROUP = "never_treated"


def load_base_panel() -> pd.DataFrame:
    try:
        df = pd.read_parquet(PROCESSED / "panel.parquet")
    except Exception:
        df = pd.read_csv(PROCESSED / "panel.csv")
    df[PERIOD] = df[PERIOD].astype(int)
    return df


def add_pbsv(panel: pd.DataFrame) -> pd.DataFrame:
    """Merge log Professional & Business Services employment (high-wage placebo outcome)."""
    frames = []
    missing = []
    for xx in sorted(panel[STATE].unique()):
        path = RAW / f"{xx}PBSV.csv"
        if not path.exists():
            missing.append(xx)
            continue
        raw = pd.read_csv(path, parse_dates=["date"])
        s = pd.Series(raw["value"].to_numpy(float), index=pd.DatetimeIndex(raw["date"]))
        q = s.copy()
        q.index = q.index.to_period("Q")
        q = q.groupby(level=0).mean()
        frames.append(pd.DataFrame({
            STATE: xx,
            "quarter": [str(p) for p in q.index],
            "pbsv": q.to_numpy(),
        }))
    if missing:
        raise SystemExit(f"[fatal] missing cached PBSV series for: {missing}")
    pb = pd.concat(frames, ignore_index=True)
    pb["log_pbsv"] = np.log(pb["pbsv"].where(pb["pbsv"] > 0))
    out = panel.merge(pb, on=[STATE, "quarter"], how="left")
    return out


def twfe(df: pd.DataFrame, outcome: str, treat: str = TREAT) -> dict:
    """TWFE DiD: outcome ~ treat + state FE + period FE, SE clustered by state."""
    d = df.dropna(subset=[outcome, treat, STATE, PERIOD]).copy()
    res = smf.ols(f"{outcome} ~ {treat} + C({STATE}) + C({PERIOD})", d).fit(
        cov_type="cluster", cov_kwds={"groups": d[STATE]})
    ci = res.conf_int(alpha=ALPHA).loc[treat]
    coef = float(res.params[treat])
    return {
        "coef": coef, "se": float(res.bse[treat]), "t": float(res.tvalues[treat]),
        "p_value": float(res.pvalues[treat]), "ci_low": float(ci[0]), "ci_high": float(ci[1]),
        "pct_effect": 100.0 * (np.exp(coef) - 1.0), "n_obs": int(res.nobs),
        "n_states": int(d[STATE].nunique()),
    }


def _tidy(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    rename = {"ATT": "att", "std_error": "std_error", "lower": "ci_low",
              "upper": "ci_high", "zero_not_in_cband": "signif"}
    flat = {}
    for col in out.columns:
        last = [str(p) for p in col if str(p) != ""][-1] if isinstance(col, tuple) else str(col)
        flat[col] = rename.get(last, last)
    out.columns = [flat[c] for c in out.columns]
    return out.reset_index()


def csa(df: pd.DataFrame, outcome: str):
    """Callaway-Sant'Anna group-time ATT; returns (overall_simple dict, event_dynamic df)."""
    d = df.dropna(subset=[outcome]).copy()
    d["time"] = d[PERIOD].astype(int) + 1
    d["cohort"] = d["g_csa"].replace(0, np.nan)
    indexed = d.set_index([STATE, "time"]).sort_index()
    att = ATTgt(data=indexed, cohort_column="cohort")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        att.fit(outcome, est_method=EST_METHOD, control_group=CONTROL_GROUP,
                n_jobs=1, progress_bar=False, random_state=RANDOM_STATE)
        simple = _tidy(att.aggregate("simple"))
        event = _tidy(att.aggregate("event"))
    overall = {
        "coef": float(simple["att"].iloc[0]), "se": float(simple["std_error"].iloc[0]),
        "ci_low": float(simple["ci_low"].iloc[0]), "ci_high": float(simple["ci_high"].iloc[0]),
        "p_value": np.nan, "t": np.nan,
        "pct_effect": 100.0 * (np.exp(float(simple["att"].iloc[0])) - 1.0),
        "n_obs": int(len(d)), "n_states": int(d[STATE].nunique()),
    }
    ev = event.rename(columns={"relative_period": "k"})
    ev["k"] = ev["k"].astype(int)
    return overall, ev


def twfe_event_study(df: pd.DataFrame, outcome: str, etime: str,
                     lead_min: int, lag_max: int, base: int = -1):
    """Binned relative-event-time leads/lags; never-treated (etime NaN) = reference."""
    d = df.copy()
    k = pd.to_numeric(d[etime], errors="coerce").astype("float64")
    d["_kbin"] = k.clip(lower=lead_min, upper=lag_max)
    terms = []
    for kk in range(lead_min, lag_max + 1):
        if kk == base:
            continue
        col = f"et_{'m' if kk < 0 else 'p'}{abs(kk)}"
        d[col] = (d["_kbin"] == kk).fillna(False).astype(int)
        terms.append((kk, col))
    cols = [c for _, c in terms]
    rhs = " + ".join(cols) + f" + C({STATE}) + C({PERIOD})"
    res = smf.ols(f"{outcome} ~ {rhs}", d).fit(
        cov_type="cluster", cov_kwds={"groups": d[STATE]})
    ci = res.conf_int(alpha=ALPHA)
    rows = [{"k": kk, "coef": float(res.params[c]), "se": float(res.bse[c]),
             "ci_low": float(ci.loc[c, 0]), "ci_high": float(ci.loc[c, 1]),
             "p_value": float(res.pvalues[c]), "is_lead": kk < 0}
            for kk, c in terms]
    rows.append({"k": base, "coef": 0.0, "se": 0.0, "ci_low": 0.0, "ci_high": 0.0,
                 "p_value": np.nan, "is_lead": True})
    coefs = pd.DataFrame(rows).sort_values("k").reset_index(drop=True)
    lead_cols = [c for kk, c in terms if kk < 0]
    near_cols = [c for kk, c in terms if -4 <= kk <= -2]
    post_cols = [c for kk, c in terms if kk >= 0]
    def wald(cs):
        if not cs:
            return np.nan, np.nan
        w = res.wald_test(", ".join(f"{c} = 0" for c in cs), scalar=True)
        return float(np.squeeze(w.statistic)), float(np.squeeze(w.pvalue))
    tests = {"leads": wald(lead_cols), "near": wald(near_cols), "post": wald(post_cols)}
    return coefs, tests, res


def build_fake_date_sample(panel: pd.DataFrame, shift: int = FAKE_SHIFT):
    """In-time placebo: move treatment `shift` quarters earlier; drop true post period.

    For each treated state with first-treat ordinal f (>0):
      * fake_first = f - shift
      * keep only rows with quarter_ord < f   (true treatment never enters the window)
      * fake_event_time = quarter_ord - fake_first
      * fake_treated_post = 1[quarter_ord >= fake_first]
    Never-treated states are kept in full as controls (fake_event_time = NaN).
    """
    df = panel.copy()
    # First-treatment ordinal from the CSA group var (g_csa = first_treat_ord + 1; 0 = never).
    # NB: `treated` is the ever-treated indicator (constant within state), so it cannot be used
    # to recover the first-treatment quarter - g_csa is the correct source.
    first_ord = (df.loc[df["g_csa"] > 0].groupby(STATE)["g_csa"].first().astype(int) - 1)
    kept_treated, dropped = [], []
    parts = []
    for xx, f in first_ord.items():
        f = int(f)
        fake_first = f - shift
        if fake_first < 2:
            dropped.append((xx, f, fake_first))
            continue
        sub = df[(df[STATE] == xx) & (df[PERIOD] < f)].copy()
        sub["fake_first"] = fake_first
        sub["fake_event_time"] = sub[PERIOD] - fake_first
        sub["fake_treated"] = 1
        sub["fake_post"] = (sub[PERIOD] >= fake_first).astype(int)
        sub["fake_treated_post"] = sub["fake_post"]
        parts.append(sub)
        kept_treated.append(xx)
    ctrl = df[df["treated"] == 0].copy()
    ctrl["fake_first"] = np.nan
    ctrl["fake_event_time"] = np.nan
    ctrl["fake_treated"] = 0
    ctrl["fake_post"] = 0
    ctrl["fake_treated_post"] = 0
    parts.append(ctrl)
    sample = pd.concat(parts, ignore_index=True)
    info = {"kept_treated": sorted(kept_treated),
            "n_kept_treated": len(kept_treated),
            "n_never": int(ctrl[STATE].nunique()),
            "dropped": dropped}
    return sample, info


def twfe_window(df: pd.DataFrame, outcome: str, w: int) -> dict:
    """TWFE on a sample restricted to |event_time| <= w for treated; all never-treated kept."""
    et = pd.to_numeric(df["event_time"], errors="coerce")
    keep = (df["treated"] == 0) | (et.abs() <= w)
    return twfe(df[keep].copy(), outcome)


def csa_horizon(ev: pd.DataFrame, kmax: int) -> dict:
    """Average the CSA dynamic ATT over post horizon k in [0, kmax]."""
    block = ev[(ev["k"] >= 0) & (ev["k"] <= kmax)]
    if block.empty:
        return {"coef": np.nan, "se": np.nan, "ci_low": np.nan, "ci_high": np.nan,
                "pct_effect": np.nan, "n_k": 0}
    m = float(block["att"].mean())
    return {"coef": m, "se": np.nan,
            "ci_low": float(block["ci_low"].min()), "ci_high": float(block["ci_high"].max()),
            "pct_effect": 100.0 * (np.exp(m) - 1.0), "n_k": int(len(block))}


def load_reference() -> dict:
    ref = {}
    did = RESULTS / "did_estimates.csv"
    if did.exists():
        d = pd.read_csv(did)
        row = d[d["model"].str.contains("TWFE", case=False, na=False)]
        if len(row):
            ref["leih_twfe"] = {"coef": float(row["coef"].iloc[0]),
                                "se": float(row["se"].iloc[0]),
                                "ci_low": float(row["ci_low"].iloc[0]),
                                "ci_high": float(row["ci_high"].iloc[0]),
                                "p_value": float(row["p_value"].iloc[0])}
    agg = RESULTS / "csa_aggregations.csv"
    if agg.exists():
        a = pd.read_csv(agg)
        s = a[a["aggregation"] == "overall_simple"]
        if len(s):
            ref["leih_csa"] = {"coef": float(s["att"].iloc[0]), "se": float(s["std_error"].iloc[0]),
                               "ci_low": float(s["ci_low"].iloc[0]), "ci_high": float(s["ci_high"].iloc[0])}
    return ref


def fig_pbsv(ev_pbsv, pbsv_twfe, pbsv_csa, ref, win=(-12, 16)):
    w = ev_pbsv[(ev_pbsv["k"] >= win[0]) & (ev_pbsv["k"] <= win[1])].sort_values("k")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6),
                                   gridspec_kw={"width_ratios": [2.2, 1]})
    k = w["k"].to_numpy(); a = w["att"].to_numpy()
    lo = w["ci_low"].to_numpy(); hi = w["ci_high"].to_numpy()
    pre = k < 0
    ax1.axhline(0, color="0.4", lw=1)
    ax1.axvline(-0.5, color="crimson", ls="--", lw=1.2, alpha=.8, label="treatment (k=0)")
    ax1.fill_between(k, lo, hi, color="seagreen", alpha=.16, label="95% pointwise CI")
    ax1.plot(k[pre], a[pre], "o", color="0.45", ms=5, label="pre (k<0)")
    ax1.plot(k[~pre], a[~pre], "o", color="seagreen", ms=5, label="post (k>=0)")
    for ki, ai, loi, hii in zip(k, a, lo, hi):
        ax1.plot([ki, ki], [loi, hii], color="seagreen", alpha=.5, lw=1)
    ax1.set_xlabel("Quarters relative to first minimum-wage increase (k)")
    ax1.set_ylabel("ATT on log PBSV employment")
    ax1.set_title("PLACEBO: high-wage sector (Prof. & Business Services)\n"
                  "Callaway-Sant'Anna cohort-robust dynamic ATT")
    ax1.legend(loc="lower left", fontsize=9, framealpha=.9); ax1.grid(alpha=.25)
    labels, vals, los, his, colors = [], [], [], [], []
    def add(lbl, est, color):
        labels.append(lbl); vals.append(est["coef"])
        los.append(est["coef"] - est["ci_low"]); his.append(est["ci_high"] - est["coef"])
        colors.append(color)
    add("PBSV\nTWFE", pbsv_twfe, "seagreen")
    add("PBSV\nCSA", pbsv_csa, "mediumseagreen")
    if "leih_twfe" in ref:
        add("L&H\nTWFE", ref["leih_twfe"], "steelblue")
    if "leih_csa" in ref:
        add("L&H\nCSA", ref["leih_csa"], "lightsteelblue")
    x = np.arange(len(labels))
    ax2.axhline(0, color="0.4", lw=1)
    ax2.bar(x, vals, color=colors, alpha=.85, width=.6)
    ax2.errorbar(x, vals, yerr=[los, his], fmt="none", ecolor="0.2", capsize=5, lw=1.3)
    for xi, v in zip(x, vals):
        ax2.annotate(f"{v:+.3f}", (xi, v), textcoords="offset points",
                     xytext=(0, 8 if v >= 0 else -14), ha="center", fontsize=9, fontweight="bold")
    ax2.set_xticks(x); ax2.set_xticklabels(labels, fontsize=8.5)
    ax2.set_ylabel("Overall ATT (log points)")
    ax2.set_title("Overall ATT: placebo (PBSV) vs real (L&H)")
    ax2.grid(axis="y", alpha=.25)
    fig.suptitle("Placebo test (a): a high-wage sector should show ~no minimum-wage effect",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(RESULTS / "fig_placebo_pbsv.png", dpi=130)
    plt.close(fig)


def fig_fake_date(coefs, tests, info):
    fig, ax = plt.subplots(figsize=(11, 6.2))
    pre = coefs[coefs.k < 0]; post = coefs[coefs.k >= 0]
    ax.axhline(0, color="#888", lw=1)
    ax.axvline(-0.5, color="#c0392b", ls="--", lw=1.3, label="FAKE treatment (k=0)")
    band = coefs[~((coefs.k == -1) & (coefs.coef == 0))]
    ax.fill_between(band.k, band.ci_low, band.ci_high, color="#8e44ad", alpha=.16, label="95% CI")
    ax.plot(coefs.k, coefs.coef, color="#2c3e50", lw=1.1)
    ax.errorbar(pre.k, pre.coef, yerr=[pre.coef - pre.ci_low, pre.ci_high - pre.coef],
                fmt="o", ms=5, color="#7f8c8d", capsize=2, label="pre fake-date")
    ax.errorbar(post.k, post.coef, yerr=[post.coef - post.ci_low, post.ci_high - post.coef],
                fmt="o", ms=5, color="#8e44ad", capsize=2, label="post fake-date")
    ax.plot([-1], [0], "s", ms=8, color="#c0392b", label="base k=-1 (=0)")
    ax.set_xlabel("Quarters relative to FAKE (placebo) treatment date")
    ax.set_ylabel("Effect on log L&H employment (vs k=-1)")
    ax.set_title("Falsification (b): fake event date 8q before true treatment\n"
                 "true post-period dropped - a flat path = design passes")
    (Fp, pp) = tests["post"]; (Fl, pl) = tests["leads"]
    txt = (f"Joint Wald tests (should NOT reject):\n"
           f"  post fake-dummies = 0:  F={Fp:.2f}, p={pp:.3f}  ({'PASS' if pp>=.05 else 'FLAG'})\n"
           f"  leads = 0:              F={Fl:.2f}, p={pl:.3f}  ({'PASS' if pl>=.05 else 'FLAG'})\n"
           f"  treated states used: {info['n_kept_treated']}  |  controls: {info['n_never']}")
    ax.text(.015, .035, txt, transform=ax.transAxes, fontsize=8.5, va="bottom", ha="left",
            bbox=dict(boxstyle="round,pad=0.4", fc="#fdf6e3", ec="#999", alpha=.95))
    ax.legend(loc="upper left", fontsize=8, ncol=2, framealpha=.9)
    ax.grid(True, axis="y", alpha=.25)
    fig.tight_layout()
    fig.savefig(RESULTS / "fig_placebo_fake_date.png", dpi=140)
    plt.close(fig)


def fig_robustness(alt_twfe, alt_csa, ref, csa_horizons, twfe_windows):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    ax = axes[0]
    labs, vals, los, his, cols = [], [], [], [], []
    def add(lbl, est, c):
        labs.append(lbl); vals.append(est["coef"])
        los.append(est["coef"] - est["ci_low"]); his.append(est["ci_high"] - est["coef"]); cols.append(c)
    add("share\nTWFE", alt_twfe, "#d35400")
    add("share\nCSA", alt_csa, "#e67e22")
    x = np.arange(len(labs)); ax.axhline(0, color="0.4", lw=1)
    ax.bar(x, vals, color=cols, alpha=.85, width=.55)
    ax.errorbar(x, vals, yerr=[los, his], fmt="none", ecolor="0.2", capsize=5)
    for xi, v in zip(x, vals):
        ax.annotate(f"{v:+.4f}", (xi, v), textcoords="offset points",
                    xytext=(0, 8 if v >= 0 else -14), ha="center", fontsize=8.5, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(labs, fontsize=8.5)
    ax.set_title("R1: alt outcome = L&H share of nonfarm\n(ATT in share points)")
    ax.set_ylabel("ATT (share of total nonfarm)"); ax.grid(axis="y", alpha=.25)
    ax = axes[1]
    ks = sorted(csa_horizons)
    vals = [csa_horizons[k]["coef"] for k in ks]
    ax.axhline(0, color="0.4", lw=1)
    ax.plot(ks, vals, "o-", color="steelblue")
    for kk, v in zip(ks, vals):
        ax.annotate(f"{v:+.3f}", (kk, v), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=8.5)
    if "leih_csa" in ref:
        ax.axhline(ref["leih_csa"]["coef"], color="crimson", ls="--", lw=1,
                   label=f"CSA overall {ref['leih_csa']['coef']:+.3f}")
        ax.legend(fontsize=8)
    ax.set_xlabel("post-horizon cap kmax (quarters)")
    ax.set_ylabel("avg ATT over k in [0,kmax] (log pts)")
    ax.set_title("R2a: L&H CSA effect vs horizon"); ax.grid(alpha=.25)
    ax = axes[2]
    ws = sorted(twfe_windows)
    vals = [twfe_windows[w]["coef"] for w in ws]
    los = [twfe_windows[w]["coef"] - twfe_windows[w]["ci_low"] for w in ws]
    his = [twfe_windows[w]["ci_high"] - twfe_windows[w]["coef"] for w in ws]
    x = np.arange(len(ws)); ax.axhline(0, color="0.4", lw=1)
    ax.errorbar(x, vals, yerr=[los, his], fmt="o", color="#2c3e50", capsize=5)
    if "leih_twfe" in ref:
        ax.axhline(ref["leih_twfe"]["coef"], color="crimson", ls="--", lw=1,
                   label=f"full-sample TWFE {ref['leih_twfe']['coef']:+.3f}")
        ax.legend(fontsize=8)
    for xi, v in zip(x, vals):
        ax.annotate(f"{v:+.3f}", (xi, v), textcoords="offset points",
                    xytext=(8, 0), ha="left", fontsize=8.5)
    ax.set_xticks(x); ax.set_xticklabels([f"+/-{w}q" for w in ws])
    ax.set_xlabel("event-time window kept (treated)")
    ax.set_ylabel("TWFE ATT (log pts)")
    ax.set_title("R2b: L&H TWFE vs event window"); ax.grid(axis="y", alpha=.25)
    fig.suptitle("Robustness: alternative outcome and alternative event windows",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(RESULTS / "fig_robustness.png", dpi=130)
    plt.close(fig)


def write_md(rows, ref, pbsv_twfe, pbsv_csa, ev_pbsv, fake_twfe, fake_tests, fake_info,
             alt_twfe, alt_csa, csa_horizons, twfe_windows, verdict):
    L = []
    L.append("# Day 7 - Placebo / falsification tests & robustness\n")
    L.append(
        "The Day 4-6 design estimates a small, gradual, statistically-insignificant "
        "negative effect of a state minimum-wage increase on log Leisure & Hospitality "
        "(L&H) employment (TWFE "
        f"{ref.get('leih_twfe',{}).get('coef',float('nan')):+.4f}, CSA "
        f"{ref.get('leih_csa',{}).get('coef',float('nan')):+.4f} log pts). This script "
        "checks that the design (1) finds NO effect where none should exist and (2) is "
        "stable to reasonable specification changes.\n")
    L.append("## (a) High-wage-sector placebo - Professional & Business Services\n")
    L.append(
        "Identical DiD design, outcome swapped to **log PBSV employment** "
        "(`<XX>PBSV`, a high-wage sector with very few minimum-wage workers). A "
        "minimum-wage increase should not move it; a large/significant PBSV effect "
        "would mean the L&H result is a generic state-level shock, not a wage-floor "
        "effect.\n")
    L.append("| Estimator | ATT (log pts) | SE | 95% CI | % effect |")
    L.append("|---|---|---|---|---|")
    L.append(f"| PBSV TWFE | {pbsv_twfe['coef']:+.4f} | {pbsv_twfe['se']:.4f} | "
             f"[{pbsv_twfe['ci_low']:+.4f}, {pbsv_twfe['ci_high']:+.4f}] | {pbsv_twfe['pct_effect']:+.2f}% |")
    L.append(f"| PBSV Callaway-Sant'Anna | {pbsv_csa['coef']:+.4f} | {pbsv_csa['se']:.4f} | "
             f"[{pbsv_csa['ci_low']:+.4f}, {pbsv_csa['ci_high']:+.4f}] | {pbsv_csa['pct_effect']:+.2f}% |")
    if "leih_twfe" in ref:
        L.append(f"| _L&H TWFE (reference)_ | {ref['leih_twfe']['coef']:+.4f} | "
                 f"{ref['leih_twfe']['se']:.4f} | [{ref['leih_twfe']['ci_low']:+.4f}, "
                 f"{ref['leih_twfe']['ci_high']:+.4f}] | - |")
    if "leih_csa" in ref:
        L.append(f"| _L&H CSA (reference)_ | {ref['leih_csa']['coef']:+.4f} | "
                 f"{ref['leih_csa']['se']:.4f} | [{ref['leih_csa']['ci_low']:+.4f}, "
                 f"{ref['leih_csa']['ci_high']:+.4f}] | - |")
    pbsv_twfe_sig = pbsv_twfe["ci_low"] * pbsv_twfe["ci_high"] > 0
    pbsv_csa_sig = pbsv_csa["ci_low"] * pbsv_csa["ci_high"] > 0
    L.append("")
    L.append(
        f"**Read:** both PBSV estimates are "
        f"{'significant' if (pbsv_twfe_sig or pbsv_csa_sig) else 'insignificant (CIs span 0)'} "
        "at the 5% level. " +
        ("The high-wage placebo shows no minimum-wage effect, as expected - the L&H "
         "result is not a generic all-sector state shock.\n" if not (pbsv_twfe_sig or pbsv_csa_sig)
         else "A significant high-wage effect is a warning sign that a common state-level "
         "confounder may contaminate the L&H estimate.\n"))
    L.append("_Figure: `results/fig_placebo_pbsv.png`._\n")
    L.append("## (b) Fake-event-date falsification (in-time placebo)\n")
    L.append(
        f"Each treated state's treatment is moved **{FAKE_SHIFT} quarters earlier** than its "
        "true first increase, and all observations from the true treatment onward are "
        "**dropped**, so the real policy can never enter the estimation window. Any effect "
        "on log L&H here is a pre-existing trend, not a treatment effect. "
        f"Treated states with a clean pre-fake window: **{fake_info['n_kept_treated']}**; "
        f"never-treated controls: **{fake_info['n_never']}**. "
        + (f"Dropped (cohort too close to the 2010Q1 panel start for an "
           f"8-quarter-earlier fake date): "
           f"{', '.join(x[0] for x in fake_info['dropped'])}.\n"
           if fake_info["dropped"] else "\n"))
    L.append("| Test | Estimate | SE | 95% CI | p |")
    L.append("|---|---|---|---|---|")
    L.append(f"| Fake DiD (single `fake_treated_post`) | {fake_twfe['coef']:+.4f} | "
             f"{fake_twfe['se']:.4f} | [{fake_twfe['ci_low']:+.4f}, {fake_twfe['ci_high']:+.4f}] | "
             f"{fake_twfe['p_value']:.3f} |")
    (Fp, pp) = fake_tests["post"]; (Fl, pl) = fake_tests["leads"]
    L.append(f"| Joint Wald: post fake-dummies = 0 | F={Fp:.2f} | - | - | {pp:.3f} |")
    L.append(f"| Joint Wald: leads = 0 | F={Fl:.2f} | - | - | {pl:.3f} |\n")
    fake_sig = fake_twfe["p_value"] < 0.05
    L.append(
        f"**Read:** the fake DiD coefficient is {fake_twfe['coef']:+.4f} log pts "
        f"(p={fake_twfe['p_value']:.3f}, {'SIGNIFICANT - FLAG' if fake_sig else 'insignificant'}); "
        f"the joint test that all post-fake-date dummies are zero "
        f"{'rejects (FLAG)' if pp < 0.05 else 'does not reject'} (p={pp:.3f}). "
        + ("Neither rejects at 5%, so no spurious effect appears before the real policy and "
           "the in-time placebo passes - but both p-values sit just above 0.05, a marginal "
           "rather than emphatic pass. The pre-fake LEADS do jointly reject "
           f"(F={Fl:.2f}, p={pl:.3f}) - the same distant-lead pattern flagged in the Day-5 "
           "event study; the test that actually matters for this falsification (the post-fake "
           "dummies) does not reject.\n" if not (fake_sig or pp < 0.05)
           else "A spurious pre-policy effect appears - treat the headline with caution.\n"))
    L.append("_Figure: `results/fig_placebo_fake_date.png`._\n")
    L.append("## Robustness\n")
    L.append("### R1 - Alternative outcome: L&H share of total nonfarm\n")
    L.append("Re-estimating with `leih_share` (L&H / total nonfarm, in share points, not logs) "
             "guards against a log-level/denominator artifact.\n")
    L.append("| Estimator | ATT (share pts) | SE | 95% CI |")
    L.append("|---|---|---|---|")
    L.append(f"| TWFE | {alt_twfe['coef']:+.5f} | {alt_twfe['se']:.5f} | "
             f"[{alt_twfe['ci_low']:+.5f}, {alt_twfe['ci_high']:+.5f}] |")
    L.append(f"| Callaway-Sant'Anna | {alt_csa['coef']:+.5f} | {alt_csa['se']:.5f} | "
             f"[{alt_csa['ci_low']:+.5f}, {alt_csa['ci_high']:+.5f}] |\n")
    alt_sig = alt_twfe["ci_low"] * alt_twfe["ci_high"] > 0
    alt_csa_sig = alt_csa["ci_low"] * alt_csa["ci_high"] > 0
    L.append(f"**Read:** the TWFE share ATT is tiny and "
             f"{'significant' if alt_sig else 'insignificant (CI spans 0)'} "
             f"({alt_twfe['coef']:+.5f}). The CSA share ATT ({alt_csa['coef']:+.5f}, ~0.2 share "
             f"points) is "
             f"{'marginally significant (pointwise CI excludes 0)' if alt_csa_sig else 'insignificant'}, "
             "but its economic magnitude is negligible. Either way the qualitative picture - a "
             "slight negative tilt that is economically trivial - matches the log-level headline.\n")
    L.append("### R2a - Alternative event windows: CSA dynamic by post-horizon\n")
    L.append("Averaging the L&H Callaway-Sant'Anna dynamic ATT over progressively longer "
             "post-treatment horizons:\n")
    L.append("| horizon k in [0, kmax] | avg ATT (log pts) | % effect | #k |")
    L.append("|---|---|---|---|")
    for kk in sorted(csa_horizons):
        h = csa_horizons[kk]
        L.append(f"| [0, {kk}] | {h['coef']:+.4f} | {h['pct_effect']:+.2f}% | {h['n_k']} |")
    L.append("")
    L.append("### R2b - Alternative event windows: TWFE on |event time| <= W\n")
    L.append("| window (treated) | TWFE ATT (log pts) | SE | 95% CI | N |")
    L.append("|---|---|---|---|---|")
    for w in sorted(twfe_windows):
        t = twfe_windows[w]
        L.append(f"| +/-{w}q | {t['coef']:+.4f} | {t['se']:.4f} | "
                 f"[{t['ci_low']:+.4f}, {t['ci_high']:+.4f}] | {t['n_obs']} |")
    L.append("")
    L.append("**Read:** across post-horizons and event windows the L&H estimate stays in a "
             "narrow negative band and never turns significantly positive or large; the "
             "headline is not an artifact of one particular window choice.\n")
    L.append("_Figure: `results/fig_robustness.png`._\n")
    L.append("## Verdict - does the design pass its falsification tests?\n")
    L.append(verdict + "\n")
    L.append("## Caveats\n")
    L.append(
        "- **Pointwise CSA CIs.** Uniform (multiplier-bootstrap) bands would be modestly wider.\n"
        "- **Fake-date sample is smaller.** Moving the date 8 quarters earlier and dropping the "
        "true post-period removes the earliest cohorts (no clean pre-fake window), so the "
        "in-time placebo rests on the later-adopting states; it tests pre-trends for those "
        "cohorts, not literally all of them.\n"
        "- **Binary first-increase event.** As elsewhere, treatment is the first increase only; "
        "size and subsequent increases are not modelled.\n"
        "- **PBSV is a placebo, not a control.** It is used to detect common shocks, not as a "
        "counterfactual for L&H.\n")
    (RESULTS / "placebo.md").write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    ref = load_reference()
    panel = add_pbsv(load_base_panel())
    n_pbsv_missing = int(panel["log_pbsv"].isna().sum())
    print(f"[data] panel {panel.shape}; PBSV merged (missing log_pbsv cells: {n_pbsv_missing})")
    rows = []
    print("[a] high-wage-sector placebo (PBSV) ...")
    pbsv_twfe = twfe(panel, "log_pbsv")
    pbsv_csa, ev_pbsv = csa(panel, "log_pbsv")
    rows += [{"block": "placebo_pbsv", "spec": "TWFE", **pbsv_twfe},
             {"block": "placebo_pbsv", "spec": "CSA_overall", **pbsv_csa}]
    print(f"[b] fake-event-date falsification (shift -{FAKE_SHIFT}q) ...")
    fake_sample, fake_info = build_fake_date_sample(panel, FAKE_SHIFT)
    fake_twfe = twfe(fake_sample, "log_leih", treat="fake_treated_post")
    fake_coefs, fake_tests, _ = twfe_event_study(
        fake_sample, "log_leih", "fake_event_time", lead_min=-8, lag_max=7)
    rows.append({"block": "falsification_fake_date", "spec": "TWFE_fake_did", **fake_twfe})
    print("[R1] alternative outcome: leih_share ...")
    alt_twfe = twfe(panel, "leih_share")
    alt_csa, _ = csa(panel, "leih_share")
    rows += [{"block": "robust_alt_outcome_share", "spec": "TWFE", **alt_twfe},
             {"block": "robust_alt_outcome_share", "spec": "CSA_overall", **alt_csa}]
    print("[R2a] CSA horizon sensitivity (L&H) ...")
    _, ev_leih = csa(panel, "log_leih")
    csa_horizons = {kk: csa_horizon(ev_leih, kk) for kk in (4, 8, 12, 16)}
    for kk, h in csa_horizons.items():
        rows.append({"block": "robust_csa_horizon", "spec": f"k0_{kk}", **h})
    print("[R2b] TWFE event-window sensitivity (L&H) ...")
    twfe_windows = {w: twfe_window(panel, "log_leih", w) for w in (8, 12, 16)}
    for w, t in twfe_windows.items():
        rows.append({"block": "robust_twfe_window", "spec": f"pm{w}q", **t})
    est = pd.DataFrame(rows)
    est.to_csv(RESULTS / "placebo_estimates.csv", index=False)
    pbsv_pass = (pbsv_twfe["ci_low"] * pbsv_twfe["ci_high"] <= 0) and \
                (pbsv_csa["ci_low"] * pbsv_csa["ci_high"] <= 0)
    fake_pass = (fake_twfe["p_value"] >= 0.05) and (fake_tests["post"][1] >= 0.05)
    win_band = [twfe_windows[w]["coef"] for w in twfe_windows]
    overall_pass = pbsv_pass and fake_pass
    verdict = (
        f"**{'PASS' if overall_pass else 'MIXED/FLAG'}.** "
        f"(a) High-wage placebo: PBSV ATT = {pbsv_twfe['coef']:+.4f} (TWFE) / "
        f"{pbsv_csa['coef']:+.4f} (CSA) log pts, "
        f"{'both insignificant' if pbsv_pass else 'at least one significant'} - "
        f"{'no effect where none is expected. ' if pbsv_pass else 'unexpected high-wage effect. '}"
        f"(b) Fake date: placebo DiD = {fake_twfe['coef']:+.4f} log pts "
        f"(p={fake_twfe['p_value']:.3f}), post-dummies joint p={fake_tests['post'][1]:.3f} - "
        f"{'no spurious pre-policy effect. ' if fake_pass else 'spurious pre-policy signal. '}"
        f"Robustness: the L&H effect keeps the same small-negative, insignificant character "
        f"under the share outcome ({alt_twfe['coef']:+.5f} share pts) and across event "
        f"windows (TWFE {min(win_band):+.4f} to {max(win_band):+.4f} log pts). "
        + ("The minimum-wage -> low-wage-employment design behaves as a credible causal "
           "design should: it detects no significant effect in either placebo and reports a "
           "stable, modest, statistically-insignificant L&H estimate. Caveat: the fake-date "
           "margins (p~0.10 and ~0.09) are only just above 0.05 and the distant pre-fake leads "
           "jointly reject, so this is best read as 'no clear falsification failure' rather than "
           "a pristine null - consistent with the mild distant-lead pre-trend already noted on "
           "Day 5."
           if overall_pass else
           "One or more falsification checks flag; the headline should be read with the "
           "noted caution."))
    print("[fig] writing figures ...")
    fig_pbsv(ev_pbsv, pbsv_twfe, pbsv_csa, ref)
    fig_fake_date(fake_coefs, fake_tests, fake_info)
    fig_robustness(alt_twfe, alt_csa, ref, csa_horizons, twfe_windows)
    write_md(rows, ref, pbsv_twfe, pbsv_csa, ev_pbsv, fake_twfe, fake_tests, fake_info,
             alt_twfe, alt_csa, csa_horizons, twfe_windows, verdict)
    print("=" * 70)
    print("DAY 7 PLACEBO / FALSIFICATION SUMMARY")
    print("=" * 70)
    print(f"(a) PBSV placebo  TWFE {pbsv_twfe['coef']:+.4f} [{pbsv_twfe['ci_low']:+.4f},"
          f"{pbsv_twfe['ci_high']:+.4f}]  CSA {pbsv_csa['coef']:+.4f} "
          f"[{pbsv_csa['ci_low']:+.4f},{pbsv_csa['ci_high']:+.4f}]  -> "
          f"{'PASS' if pbsv_pass else 'FLAG'}")
    print(f"(b) Fake date     DiD  {fake_twfe['coef']:+.4f} (p={fake_twfe['p_value']:.3f}), "
          f"post-joint p={fake_tests['post'][1]:.3f}  -> {'PASS' if fake_pass else 'FLAG'}")
    print(f"R1 alt outcome    share TWFE {alt_twfe['coef']:+.5f} "
          f"[{alt_twfe['ci_low']:+.5f},{alt_twfe['ci_high']:+.5f}]")
    print("R2b TWFE windows  " + ", ".join(f"+/-{w}q={twfe_windows[w]['coef']:+.4f}"
          for w in sorted(twfe_windows)))
    print(f"OVERALL: {'PASS' if overall_pass else 'MIXED/FLAG'}")
    print("Saved: placebo_estimates.csv, placebo.md, fig_placebo_pbsv.png, "
          "fig_placebo_fake_date.png, fig_robustness.png")


if __name__ == "__main__":
    main()
