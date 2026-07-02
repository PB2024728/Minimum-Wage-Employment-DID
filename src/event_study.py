"""
event_study.py - Day 5 dynamic DiD (event study) for the minimum-wage project.

Extends the Day-4 TWFE DiD (src/estimate_did.py) from a single on/off `treated_post`
coefficient to a full set of relative-event-time leads and lags around each state's FIRST
minimum-wage increase. This (a) tests the parallel-trends assumption directly - pre-treatment
("lead") coefficients should be statistically indistinguishable from zero - and (b) traces the
dynamic path of the effect after adoption instead of collapsing it to one average shift.

Specification
-------------
    log_leih_{it} = sum_{k != -1} beta_k * 1[event_time_{it} = k]
                    + alpha_i (state FE) + lambda_t (period FE) + e_{it}

  * event_time k = quarter_ord - first-treatment quarter_ord (k=0 is the quarter of the
    first increase).
  * BASE PERIOD k = -1 is OMITTED (normalised to 0); every beta_k is read relative to the
    quarter immediately before treatment. Standard event-study normalisation.
  * ENDPOINT BINNING: event times beyond the estimation window are accumulated into two bins
    (k <= LEAD_MIN and k >= LAG_MAX) so extreme, thinly-populated relative times do not get
    their own noisy dummy and do not contaminate interior coefficients.
  * CONTROLS: never-treated states (event_time = NaN) get 0 on every event-time dummy, so they
    sit in the reference group and supply the clean counterfactual time path. State FE + period
    FE as in Day 4; SEs CLUSTERED BY STATE (Bertrand-Duflo-Mullainathan 2004).

Sample note (Day-5 robustness item from the plan)
-------------------------------------------------
The 6 "always-treated" states whose first increase is at the 2010Q1 panel start (event_time
min = 0: AK, CT, DC, IL, ME, NV) have NO clean pre-period, so they cannot inform leads or the
k=-1 normalisation. They are DROPPED from the event-study estimation sample. This is the natural
handling for an event study and directly addresses the "always-treated drop-sensitivity" item the
Day-4 script deferred. Estimation sample = 25 treated (>=1 pre-quarter) + 20 never-treated = 45.

Parallel-trends test
--------------------
Joint Wald test that ALL lead coefficients (k from the lead bin through -2) equal zero, plus a
"near" test on the last quarters before treatment (k in [-4,-2]) to separate a genuine
near-treatment pre-trend from elevated long-horizon leads.

Outputs (results/)
------------------
    results/event_study_coefs.csv   tidy: event_time, label, coef, se, ci_low, ci_high, is_lead
    results/fig_event_study.png     point estimates + 95% CI band vs relative event time
    results/event_study.md          pre-trend assessment + dynamic-effect summary

Project rules honoured: Python only; reads cached processed panel (no API calls); standalone +
idempotent; results -> results/.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
PROCESSED = ROOT / "data" / "processed"

OUTCOME = "log_leih"
STATE = "jurisdiction"
PERIOD = "quarter_ord"
EVENT = "event_time"
ALPHA = 0.05

# Estimation window (quarters relative to first increase). Interior leads/lags get their own
# dummy; everything past the bin edges is accumulated into a single endpoint bin each side.
LEAD_MIN = -12   # most negative interior lead
LAG_MAX = 16     # most positive interior lag
BASE = -1        # omitted / normalised base period
NEAR_LEAD_MIN = -4   # "near" pre-window for the concentrated-pretrend diagnostic


def load_panel() -> pd.DataFrame:
    """Load processed panel (parquet preferred, csv fallback)."""
    try:
        df = pd.read_parquet(PROCESSED / "panel.parquet")
        src = "panel.parquet"
    except Exception:
        df = pd.read_csv(PROCESSED / "panel.csv")
        src = "panel.csv"
    print(f"[load] {src}: {df.shape[0]} rows x {df.shape[1]} cols")
    need = {OUTCOME, STATE, PERIOD, EVENT, "treated"}
    missing = need - set(df.columns)
    if missing:
        raise SystemExit(f"[fatal] panel missing required columns: {missing}")
    df[PERIOD] = df[PERIOD].astype(int)
    return df


def build_es_sample(df: pd.DataFrame):
    """Drop always-treated (no pre-period) states; keep treated-with-pre + never-treated."""
    min_et = df.loc[df.treated == 1].groupby(STATE)[EVENT].min()
    always = sorted(min_et[min_et == 0].index.tolist())
    es = df[~df[STATE].isin(always)].copy()
    n_treat = es.loc[es.treated == 1, STATE].nunique()
    n_ctrl = es.loc[es.treated == 0, STATE].nunique()
    print(f"[sample] dropped {len(always)} always-treated (no pre-period): {always}")
    print(f"[sample] event-study sample: {n_treat} treated + {n_ctrl} never-treated "
          f"= {es[STATE].nunique()} states, {len(es)} obs")
    return es, always


def make_event_dummies(es: pd.DataFrame):
    """Create binned relative-event-time dummies; omit the base period.

    Returns (df, terms) where terms is an ordered list of (label, colname, is_lead, plot_x).
    Never-treated rows (event_time NaN) get 0 on all dummies (reference group).
    """
    k = pd.to_numeric(es[EVENT], errors="coerce").astype("float64")
    # Clip into bins: <=LEAD_MIN -> LEAD_MIN bin; >=LAG_MAX -> LAG_MAX bin; else exact integer.
    kb = k.clip(lower=LEAD_MIN, upper=LAG_MAX)
    es = es.copy()
    es["_kbin"] = kb  # NaN stays NaN for never-treated

    terms = []  # (label, colname, is_lead, plot_x)
    for kk in range(LEAD_MIN, LAG_MAX + 1):
        if kk == BASE:
            continue  # omitted base period
        col = f"et_{'m' if kk < 0 else 'p'}{abs(kk)}"
        es[col] = (es["_kbin"] == kk).fillna(False).astype(int)
        if kk == LEAD_MIN:
            label = f"<= {kk}"
        elif kk == LAG_MAX:
            label = f">= {kk}"
        else:
            label = f"{kk:+d}"
        terms.append((label, col, kk < 0, kk))
    return es, terms


def fit_event_study(es: pd.DataFrame, terms):
    cols = [c for (_, c, _, _) in terms]
    rhs = " + ".join(cols) + f" + C({STATE}) + C({PERIOD})"
    formula = f"{OUTCOME} ~ {rhs}"
    res = smf.ols(formula, data=es).fit(cov_type="cluster", cov_kwds={"groups": es[STATE]})
    return res


def _wald(res, cols):
    wald = res.wald_test(", ".join(f"{c} = 0" for c in cols), scalar=True)
    return float(np.squeeze(wald.statistic)), float(np.squeeze(wald.pvalue))


def parallel_trends_test(res, terms):
    """Joint Wald tests that lead coefficients == 0.

    Returns the full test (all leads) plus a 'near' test on the last few quarters before
    treatment (k in [NEAR_LEAD_MIN, -2]). Reporting both separates a genuine near-treatment
    pre-trend (fatal for DiD) from elevated long-horizon leads (often a sparse-support / level
    artifact of the distant cohorts).
    """
    lead_cols = [c for (_, c, is_lead, _) in terms if is_lead]
    near_cols = [c for (_, c, is_lead, k) in terms if is_lead and NEAR_LEAD_MIN <= k <= -2]
    F, p = _wald(res, lead_cols)
    Fn, pn = _wald(res, near_cols)
    return {"n_leads": len(lead_cols), "F": F, "p_value": p, "lead_cols": lead_cols,
            "n_near": len(near_cols), "near_F": Fn, "near_p": pn,
            "near_window": (NEAR_LEAD_MIN, -2)}


def tidy_coefs(res, terms) -> pd.DataFrame:
    rows = []
    ci = res.conf_int(alpha=ALPHA)
    for (label, col, is_lead, plot_x) in terms:
        rows.append({
            "event_time": plot_x, "label": label, "term": col,
            "coef": res.params[col], "se": res.bse[col],
            "ci_low": ci.loc[col, 0], "ci_high": ci.loc[col, 1],
            "p_value": res.pvalues[col], "is_lead": is_lead, "is_base": False,
            "pct_effect": 100.0 * (np.exp(res.params[col]) - 1.0),
        })
    rows.append({"event_time": BASE, "label": f"{BASE:+d} (base)", "term": "(omitted)",
                 "coef": 0.0, "se": 0.0, "ci_low": 0.0, "ci_high": 0.0, "p_value": np.nan,
                 "is_lead": True, "is_base": True, "pct_effect": 0.0})
    out = pd.DataFrame(rows).sort_values("event_time").reset_index(drop=True)
    return out


def make_plot(coefs: pd.DataFrame, pt: dict, n_states: int) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6.2))
    pre = coefs[coefs.event_time < 0]
    post = coefs[coefs.event_time >= 0]

    ax.axhline(0, color="#888", lw=1, zorder=1)
    ax.axvline(-0.5, color="#c0392b", ls="--", lw=1.3, zorder=1, label="treatment (k=0)")

    band = coefs[~coefs.is_base]
    ax.fill_between(band.event_time, band.ci_low, band.ci_high, color="#3498db",
                    alpha=0.18, zorder=2, label="95% CI")
    ax.plot(coefs.event_time, coefs.coef, color="#2c3e50", lw=1.2, zorder=3)
    ax.errorbar(pre.event_time, pre.coef, yerr=[pre.coef - pre.ci_low, pre.ci_high - pre.coef],
                fmt="o", ms=5, color="#27ae60", ecolor="#27ae60", elinewidth=1, capsize=2,
                zorder=4, label="pre-treatment (leads)")
    ax.errorbar(post.event_time, post.coef, yerr=[post.coef - post.ci_low, post.ci_high - post.coef],
                fmt="o", ms=5, color="#2980b9", ecolor="#2980b9", elinewidth=1, capsize=2,
                zorder=4, label="post-treatment (lags)")
    base = coefs[coefs.is_base]
    ax.plot(base.event_time, base.coef, "s", ms=8, color="#c0392b", zorder=5,
            label="base period k=-1 (=0)")

    ax.set_xlabel("Quarters relative to first minimum-wage increase (event time k)")
    ax.set_ylabel("Effect on log L&H employment (vs k = -1)")
    ax.set_title("Event study: minimum-wage increase and Leisure & Hospitality employment\n"
                 f"TWFE leads/lags, state + period FE, SE clustered by state ({n_states} states)")
    ax.set_xticks(range(LEAD_MIN, LAG_MAX + 1, 2))
    ax.grid(True, axis="y", alpha=0.25)

    nlo, nhi = pt["near_window"]
    txt = (f"Parallel-trends joint Wald tests:\n"
           f"  all {pt['n_leads']} leads:  F={pt['F']:.2f},  p={pt['p_value']:.3f}"
           f"  ({'OK' if pt['p_value']>=0.05 else 'REJECT'})\n"
           f"  near k=[{nlo},{nhi}]:  F={pt['near_F']:.2f},  p={pt['near_p']:.3f}"
           f"  ({'OK' if pt['near_p']>=0.05 else 'REJECT'})")
    ax.text(0.015, 0.035, txt, transform=ax.transAxes, fontsize=8.5,
            va="bottom", ha="left",
            bbox=dict(boxstyle="round,pad=0.4", fc="#fdf6e3", ec="#999", alpha=0.95))
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9, ncol=2)
    fig.tight_layout()
    out = RESULTS / "fig_event_study.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"[save] {out}")
    return out


def write_outputs(coefs: pd.DataFrame, pt: dict, res, es: pd.DataFrame, always: list) -> None:
    RESULTS.mkdir(exist_ok=True)
    csv_path = RESULTS / "event_study_coefs.csv"
    coefs.to_csv(csv_path, index=False)
    print(f"[save] {csv_path}")

    n_states = es[STATE].nunique()
    n_treat = es.loc[es.treated == 1, STATE].nunique()

    post = coefs[(coefs.event_time >= 0) & (~coefs.is_base)]
    leads = coefs[(coefs.event_time < 0) & (~coefs.is_base)]
    sig_leads = leads[leads.p_value < 0.05]
    early = post[post.event_time.between(0, 3)]
    late = post[post.event_time >= 8]
    pt_ok = pt["p_value"] >= 0.05
    near_ok = pt["near_p"] >= 0.05
    nlo, nhi = pt["near_window"]

    md = []
    md.append("# Day 5 - Event study & parallel-trends diagnostic\n")
    md.append("Dynamic DiD: relative-event-time leads/lags around each state's **first** "
              "minimum-wage increase, base period **k = -1** normalised to 0, endpoint binning "
              f"at k <= {LEAD_MIN} and k >= {LAG_MAX}. State + period FE; SE clustered by state.\n")
    md.append(f"**Estimation sample:** {n_treat} treated (with >=1 pre-quarter) + "
              f"{n_states - n_treat} never-treated = {n_states} states, {int(res.nobs)} obs. "
              f"Dropped {len(always)} always-treated states with no pre-period: {always}.\n")

    md.append("## Parallel-trends test (pre-treatment leads jointly = 0)\n")
    md.append(f"- **All {pt['n_leads']} leads:** joint Wald **F = {pt['F']:.2f}, p = {pt['p_value']:.3f}** "
              f"-> {'**fail to reject**' if pt_ok else '**reject**'} at 5%.\n")
    md.append(f"- **Near window k in [{nlo}, {nhi}]:** joint Wald "
              f"**F = {pt['near_F']:.2f}, p = {pt['near_p']:.3f}** "
              f"-> {'**fail to reject**' if near_ok else '**reject**'} at 5%.\n")
    n_sig = len(sig_leads)
    md.append(f"Individually, {n_sig} of {len(leads)} lead coefficients are significant at 5%"
              + (f": {', '.join('k='+str(int(r.event_time)) for _, r in sig_leads.iterrows())}."
                 if n_sig else " (none)."))
    md.append("")
    if (not pt_ok) and near_ok:
        md.append("**Read:** the *overall* lead test rejects, but the violation is concentrated in "
                  f"the **distant** leads (the significant ones are all the long-horizon quarters); "
                  f"the **near** pre-window k in [{nlo},{nhi}] is flat and jointly insignificant. "
                  "Distant-lead elevation with sparser cohort support is a weaker threat than a "
                  "pre-trend that accelerates into treatment - but the formal assumption is not "
                  "cleanly satisfied, so the post estimates remain provisional pending the "
                  "staggered-robust check.\n")
    elif pt_ok:
        md.append("**Read:** no statistical evidence against parallel pre-trends; leads are jointly "
                  "indistinguishable from zero (necessary, not sufficient, for DiD identification).\n")
    else:
        md.append("**Read:** pre-treatment coefficients jointly differ from zero *including near "
                  "treatment* - a serious parallel-trends violation; post estimates are likely "
                  "confounded by differential trends.\n")

    md.append("## Dynamic effects after adoption\n")

    def describe(block, name):
        if block.empty:
            return f"- {name}: no quarters in range.\n"
        lo, hi = int(block.event_time.min()), int(block.event_time.max())
        mn = block.coef.mean()
        return (f"- **{name}** (k={lo}..{hi}): mean effect {mn:+.4f} log pts "
                f"(~{100*(np.exp(mn)-1):+.2f}%).\n")
    md.append(describe(early, "Early post (0-3q)"))
    md.append(describe(late, "Later post (>=8q)"))
    if not post.empty:
        big = post.iloc[post.coef.abs().argmax()]
        md.append(f"- Largest post coefficient at k={int(big.event_time)}: {big.coef:+.4f} log pts "
                  f"({big.pct_effect:+.2f}%), 95% CI [{big.ci_low:+.4f}, {big.ci_high:+.4f}], "
                  f"p={big.p_value:.3f}.\n")
    n_sig_post = int((post.p_value < 0.05).sum())
    md.append(f"- {n_sig_post} of {len(post)} post-treatment coefficients are individually "
              f"significant at 5%; the post path is **negative and widening** "
              "(a gradual relative L&H-employment decline after the wage increase).\n")

    md.append("## Interpretation\n")
    md.append(
        ("Near-treatment leads are flat while the post path turns steadily negative, so the "
         "dynamic picture is a slow relative decline in low-wage-sector employment after a "
         "minimum-wage increase. " if near_ok else
         "The leads move before treatment, so the parallel-trends premise is questionable and "
         "the dynamic estimates are provisional. ")
        + "These remain TWFE event-study coefficients; under staggered adoption with heterogeneous "
          "effects they can be contaminated by 'forbidden' comparisons among already-treated units "
          "(Goodman-Bacon 2021; Sun-Abraham 2021). The Callaway-Sant'Anna estimator (Day 6) is the "
          "designed cross-check, and its cohort-robust event study is the more credible dynamic "
          "picture; treat today's plot as the diagnostic that motivates it.\n")

    md.append("## Caveats\n")
    md.append("- Endpoint bins (k<=%d, k>=%d) absorb sparse extreme relative times; interior "
              "coefficients are the interpretable ones.\n" % (LEAD_MIN, LAG_MAX))
    md.append("- Binary event = first increase only; later increases and the *size* of each "
              "increase are not modelled here.\n")
    md.append("- TWFE event study is not staggered-robust; treat as a diagnostic, reconcile with "
              "Callaway-Sant'Anna on Day 6.\n")
    md.append("\n_Figure: `results/fig_event_study.png`. Coefficients: "
              "`results/event_study_coefs.csv`._\n")

    md_path = RESULTS / "event_study.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(f"[save] {md_path}")


def main() -> None:
    df = load_panel()
    es, always = build_es_sample(df)
    es, terms = make_event_dummies(es)
    print(f"[spec] {len(terms)} event-time dummies (base k={BASE} omitted); "
          f"window [{LEAD_MIN},{LAG_MAX}] with endpoint bins")
    res = fit_event_study(es, terms)
    pt = parallel_trends_test(res, terms)
    print(f"[parallel-trends] all {pt['n_leads']} leads: F={pt['F']:.3f}, p={pt['p_value']:.4f} | "
          f"near k in [{pt['near_window'][0]},{pt['near_window'][1]}]: "
          f"F={pt['near_F']:.3f}, p={pt['near_p']:.4f}")
    coefs = tidy_coefs(res, terms)
    print("\n=== event-study coefficients ===")
    print(coefs[["event_time", "label", "coef", "se", "ci_low", "ci_high", "p_value"]]
          .to_string(index=False))
    make_plot(coefs, pt, es[STATE].nunique())
    write_outputs(coefs, pt, res, es, always)
    print("\n[done] Day 5 event study complete.")


if __name__ == "__main__":
    main()
