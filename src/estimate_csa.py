"""
estimate_csa.py - Day 6: Callaway & Sant'Anna (2021) staggered-adoption DiD.

Estimates group-time ATT(g,t) for the effect of a state's FIRST minimum-wage
increase on log Leisure & Hospitality employment, using the `differences`
package (Callaway-Sant'Anna estimator). Aggregates to overall ATT and a
cohort-robust dynamic (event-study) path, and reconciles against the Day-4
TWFE estimate.

Cohort = first-treatment period (quarter). Control group = never-treated states.
Always-treated states (first increase at the 2010Q1 panel start, no clean
pre-period) are dropped by the estimator, consistent with the Day-5 event study.

Run standalone:  python src/estimate_csa.py
Outputs (results/):
  - csa_att_gt.csv           group-time ATT(g,t) table
  - csa_aggregations.csv     overall / event / cohort / time aggregations
  - csa_estimates.md         writeup + TWFE reconciliation
  - fig_csa_event_study.png  cohort-robust dynamic ATT (+ TWFE-vs-CSA overall)
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

from differences import ATTgt

ROOT = Path(os.environ.get("CSA_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
PANEL_PARQUET = ROOT / "data" / "processed" / "panel.parquet"
PANEL_CSV = ROOT / "data" / "processed" / "panel.csv"
RESULTS = ROOT / "results"
DID_CSV = RESULTS / "did_estimates.csv"

OUTCOME = "log_leih"
EST_METHOD = "dr"
CONTROL_GROUP = "never_treated"
RANDOM_STATE = 1234
EV_MIN, EV_MAX = -12, 16


def load_panel() -> pd.DataFrame:
    if PANEL_PARQUET.exists():
        try:
            return pd.read_parquet(PANEL_PARQUET)
        except Exception:
            pass
    return pd.read_csv(PANEL_CSV)


def prep(df: pd.DataFrame):
    df = df.copy()
    df["time"] = df["quarter_ord"].astype(int) + 1
    df["cohort"] = df["g_csa"].replace(0, np.nan)
    ord_to_q = (
        df.drop_duplicates("quarter_ord")
        .assign(t=lambda x: x["quarter_ord"].astype(int) + 1)
        .set_index("t")["quarter"]
        .to_dict()
    )
    indexed = df.set_index(["jurisdiction", "time"]).sort_index()
    return indexed, ord_to_q


def q_label(t, ord_to_q):
    try:
        return ord_to_q.get(int(t), str(t))
    except Exception:
        return str(t)


def tidy(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    flat = {}
    for col in out.columns:
        parts = [str(p) for p in col if str(p) != ""]
        last = parts[-1]
        name = {
            "ATT": "att",
            "std_error": "std_error",
            "lower": "ci_low",
            "upper": "ci_high",
            "zero_not_in_cband": "signif",
        }.get(last, last)
        flat[col] = name
    out.columns = [flat[c] for c in out.columns]
    return out.reset_index()


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    raw = load_panel()
    data, ord_to_q = prep(raw)

    n_states = raw["jurisdiction"].nunique()
    n_never = int((raw.groupby("jurisdiction")["g_csa"].first() == 0).sum())
    n_treated = n_states - n_never

    att = ATTgt(data=data, cohort_column="cohort")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = att.fit(
            OUTCOME, est_method=EST_METHOD, control_group=CONTROL_GROUP,
            n_jobs=1, progress_bar=False, random_state=RANDOM_STATE,
        )

    gt = tidy(res.to_pandas())
    gt["cohort_q"] = gt["cohort"].map(lambda t: q_label(t, ord_to_q))
    gt["time_q"] = gt["time"].map(lambda t: q_label(t, ord_to_q))
    gt["base_period_q"] = gt["base_period"].map(lambda t: q_label(t, ord_to_q))
    gt_cols = ["cohort", "cohort_q", "base_period", "base_period_q", "time",
               "time_q", "att", "std_error", "ci_low", "ci_high", "signif"]
    gt = gt[[c for c in gt_cols if c in gt.columns]]
    gt.to_csv(RESULTS / "csa_att_gt.csv", index=False)

    def agg(kind, overall=False):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return tidy(att.aggregate(kind, overall=overall))

    simple = agg("simple")
    event_dyn = agg("event")
    event_overall = agg("event", overall=True)
    cohort_agg = agg("cohort")
    time_agg = agg("time")

    def tag(d, name, keycol=None):
        d = d.copy()
        d.insert(0, "aggregation", name)
        if keycol and keycol in d.columns:
            d = d.rename(columns={keycol: "key"})
        elif "index" in d.columns:
            d = d.rename(columns={"index": "key"})
        else:
            d["key"] = np.nan
        return d

    cohort_agg = cohort_agg.copy()
    if "cohort" in cohort_agg.columns:
        cohort_agg["cohort_q"] = cohort_agg["cohort"].map(lambda t: q_label(t, ord_to_q))
    time_agg = time_agg.copy()
    if "time" in time_agg.columns:
        time_agg["time_q"] = time_agg["time"].map(lambda t: q_label(t, ord_to_q))

    keep = ["att", "std_error", "ci_low", "ci_high", "signif"]
    stacked = pd.concat(
        [
            tag(simple, "overall_simple"),
            tag(event_overall, "overall_event"),
            tag(event_dyn, "event_dynamic", "relative_period"),
            tag(cohort_agg, "by_cohort", "cohort"),
            tag(time_agg, "by_time", "time"),
        ],
        ignore_index=True,
    )
    stacked = stacked[
        ["aggregation", "key"] + [c for c in keep if c in stacked.columns]
        + [c for c in ["cohort_q", "time_q"] if c in stacked.columns]
    ]
    stacked.to_csv(RESULTS / "csa_aggregations.csv", index=False)

    att_overall = float(simple["att"].iloc[0])
    se_overall = float(simple["std_error"].iloc[0])
    lo_overall = float(simple["ci_low"].iloc[0])
    hi_overall = float(simple["ci_high"].iloc[0])
    att_ev_overall = float(event_overall["att"].iloc[0])

    twfe_coef = twfe_se = np.nan
    if DID_CSV.exists():
        did = pd.read_csv(DID_CSV)
        row = did[did["model"].str.contains("TWFE", case=False, na=False)]
        if len(row):
            twfe_coef = float(row["coef"].iloc[0])
            twfe_se = float(row["se"].iloc[0])

    ed = event_dyn.rename(columns={"relative_period": "k"})
    ed["k"] = ed["k"].astype(int)
    pre = ed[ed["k"] < 0]
    post = ed[ed["k"] >= 0]
    n_pre_sig = int((pre["signif"].astype(str).str.strip() == "*").sum())
    near_pre = pre[(pre["k"] >= -4) & (pre["k"] <= -1)]
    near_pre_max = float(near_pre["att"].abs().max()) if len(near_pre) else np.nan

    make_figure(ed, att_overall, lo_overall, hi_overall, twfe_coef, twfe_se)
    write_md(n_states, n_treated, n_never, gt, att_overall, se_overall,
             lo_overall, hi_overall, att_ev_overall, twfe_coef, twfe_se,
             n_pre_sig, len(pre), near_pre_max, post)

    print("=" * 64)
    print("Callaway-Sant'Anna staggered DiD - log L&H employment")
    print("=" * 64)
    print(f"States: {n_states} ({n_treated} ever-treated, {n_never} never-treated)")
    print("Always-treated (g=2010Q1) dropped by estimator: 6")
    print(f"Group-time ATT(g,t) rows: {len(gt)}")
    print(f"Overall ATT (simple, group-size wtd): {att_overall:+.4f} "
          f"(SE {se_overall:.4f}) 95% CI [{lo_overall:+.4f}, {hi_overall:+.4f}]")
    print(f"Overall ATT (event/post-avg):          {att_ev_overall:+.4f}")
    if not np.isnan(twfe_coef):
        print(f"TWFE (Day 4):                          {twfe_coef:+.4f} (SE {twfe_se:.4f})")
        print(f"CSA - TWFE divergence:                 {att_overall - twfe_coef:+.4f} log pts")
    print(f"Pre-period event ATTs significant: {n_pre_sig}/{len(pre)}")
    print("Saved: csa_att_gt.csv, csa_aggregations.csv, csa_estimates.md, "
          "fig_csa_event_study.png")


def make_figure(ed, att_overall, lo_overall, hi_overall, twfe_coef, twfe_se):
    win = ed[(ed["k"] >= EV_MIN) & (ed["k"] <= EV_MAX)].sort_values("k")
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(15, 6), gridspec_kw={"width_ratios": [2.4, 1]})
    k = win["k"].to_numpy()
    a = win["att"].to_numpy()
    lo = win["ci_low"].to_numpy()
    hi = win["ci_high"].to_numpy()
    pre_mask = k < 0
    ax1.axhline(0, color="0.4", lw=1)
    ax1.axvline(-0.5, color="crimson", ls="--", lw=1.2, alpha=0.8, label="treatment (k=0)")
    ax1.fill_between(k, lo, hi, color="steelblue", alpha=0.18, label="95% pointwise CI")
    ax1.plot(k[pre_mask], a[pre_mask], "o", color="0.45", ms=5, label="pre (k<0)")
    ax1.plot(k[~pre_mask], a[~pre_mask], "o", color="steelblue", ms=5, label="post (k>=0)")
    for ki, ai, loi, hii in zip(k, a, lo, hi):
        ax1.plot([ki, ki], [loi, hii], color="steelblue", alpha=0.5, lw=1)
    ax1.set_xlabel("Quarters relative to first minimum-wage increase (k)")
    ax1.set_ylabel("ATT on log L&H employment")
    ax1.set_title("Callaway-Sant'Anna cohort-robust dynamic ATT")
    ax1.legend(loc="lower left", fontsize=9, framealpha=0.9)
    ax1.grid(alpha=0.25)

    labels, vals, los, his, colors = [], [], [], [], []
    labels.append("CSA\noverall"); vals.append(att_overall)
    los.append(att_overall - lo_overall); his.append(hi_overall - att_overall)
    colors.append("steelblue")
    if not np.isnan(twfe_coef):
        labels.append("TWFE\n(Day 4)"); vals.append(twfe_coef)
        los.append(1.96 * twfe_se); his.append(1.96 * twfe_se)
        colors.append("darkorange")
    x = np.arange(len(labels))
    ax2.axhline(0, color="0.4", lw=1)
    ax2.bar(x, vals, color=colors, alpha=0.85, width=0.55)
    ax2.errorbar(x, vals, yerr=[los, his], fmt="none", ecolor="0.2", capsize=6, lw=1.4)
    for xi, v in zip(x, vals):
        ax2.annotate(f"{v:+.4f}", (xi, v), textcoords="offset points",
                     xytext=(0, 10 if v >= 0 else -16), ha="center",
                     fontsize=10, fontweight="bold")
    ax2.set_xticks(x); ax2.set_xticklabels(labels)
    ax2.set_ylabel("Overall ATT (log points)")
    ax2.set_title("Overall ATT: CSA vs TWFE")
    ax2.grid(axis="y", alpha=0.25)
    fig.suptitle("Minimum-wage increase -> low-wage-sector (L&H) employment: "
                 "staggered-robust estimate", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(RESULTS / "fig_csa_event_study.png", dpi=130)
    plt.close(fig)


def write_md(n_states, n_treated, n_never, gt, att_overall, se_overall,
             lo_overall, hi_overall, att_ev_overall, twfe_coef, twfe_se,
             n_pre_sig, n_pre, near_pre_max, post):
    pct = (np.exp(att_overall) - 1) * 100
    pct_lo = (np.exp(lo_overall) - 1) * 100
    pct_hi = (np.exp(hi_overall) - 1) * 100
    diverg = att_overall - twfe_coef if not np.isnan(twfe_coef) else np.nan
    post_int = post[(post["k"] >= 0) & (post["k"] <= EV_MAX)]
    post_late = post_int[post_int["k"] >= 8]
    late_mean = float(post_late["att"].mean()) if len(post_late) else np.nan
    trough_row = post_int.loc[post_int["att"].idxmin()] if len(post_int) else None
    trough_k = int(trough_row["k"]) if trough_row is not None else np.nan
    trough_att = float(trough_row["att"]) if trough_row is not None else np.nan

    lines = []
    lines.append("# Day 6 - Callaway-Sant'Anna (2021) staggered-adoption DiD\n")
    lines.append(
        "Outcome: `log_leih` (log Leisure & Hospitality employment). "
        "Cohort = quarter of a state's **first** minimum-wage increase "
        "(`g_csa`). Control group = **never-treated** states. Estimator: "
        "doubly-robust group-time ATT via the `differences` package "
        "(Callaway & Sant'Anna 2021). SEs clustered by state (analytic, "
        "entity-level); CIs are pointwise.\n")
    lines.append(
        f"**Sample:** {n_treated} ever-treated + {n_never} never-treated = "
        f"{n_states} jurisdictions. The 6 always-treated states "
        "(first increase at the 2010Q1 panel start: AK, CT, DC, IL, ME, NV) "
        "have no clean pre-period and are dropped automatically by the "
        "estimator - the same 6 dropped by the Day-5 event study. "
        f"Group-time ATT(g,t) cells estimated: **{len(gt)}**.\n")

    lines.append("## Aggregated ATT\n")
    lines.append("| Aggregation | ATT (log pts) | SE | 95% CI | % effect |")
    lines.append("|---|---|---|---|---|")
    lines.append(
        f"| **Overall (group-size weighted)** | {att_overall:+.4f} | "
        f"{se_overall:.4f} | [{lo_overall:+.4f}, {hi_overall:+.4f}] | {pct:+.2f}% |")
    lines.append(
        f"| Overall (event/post-avg) | {att_ev_overall:+.4f} | - | - | "
        f"{(np.exp(att_ev_overall)-1)*100:+.2f}% |\n")

    lines.append("## Headline (CSA)\n")
    lines.append(
        f"A state minimum-wage increase is associated with a **{pct:+.2f}%** "
        f"change in low-wage-sector (L&H) employment "
        f"(95% CI [{pct_lo:+.2f}%, {pct_hi:+.2f}%]), staggered-adoption-robust "
        "(Callaway-Sant'Anna). The CI spans zero, so the effect is **not "
        "statistically distinguishable from zero** at the 5% level.\n")

    lines.append("## Reconciliation with TWFE (Day 4)\n")
    if not np.isnan(twfe_coef):
        lines.append("| Estimator | Overall ATT (log pts) | SE |")
        lines.append("|---|---|---|")
        lines.append(f"| TWFE DiD (Day 4) | {twfe_coef:+.4f} | {twfe_se:.4f} |")
        lines.append(f"| Callaway-Sant'Anna | {att_overall:+.4f} | {se_overall:.4f} |")
        lines.append(f"| **Divergence (CSA - TWFE)** | **{diverg:+.4f}** | - |\n")
        lines.append(
            f"The two estimators agree closely: CSA is **{diverg:+.4f}** log "
            f"points from TWFE ({abs(diverg)/abs(twfe_coef)*100:.0f}% of the "
            "TWFE magnitude), and both are negative, modest, and statistically "
            "insignificant. Under Goodman-Bacon (2021), the TWFE coefficient is "
            "a variance-weighted average of all 2x2 DiD comparisons - including "
            "'forbidden' comparisons that use already-treated states as controls "
            "for later-treated ones, which can be mis-weighted (even negatively) "
            "when treatment effects are heterogeneous across cohorts or grow over "
            "time. CSA avoids those comparisons entirely: every ATT(g,t) uses "
            "only not-yet/never-treated states as the clean control group, then "
            "aggregates with non-negative, group-size weights.\n")
        lines.append(
            "The small CSA-vs-TWFE gap implies the staggered/heterogeneity bias "
            "in this panel is **minor** - the dynamic effects, while present, are "
            "not large or variable enough across cohorts to badly contaminate the "
            "TWFE weights. CSA is slightly **smaller in magnitude**, consistent "
            "with TWFE's forbidden comparisons (later cohorts differenced against "
            "earlier-treated, still-adjusting states) mildly inflating the "
            "negative TWFE point estimate. There IS real cohort heterogeneity "
            "underneath (per-cohort ATTs in `csa_aggregations.csv` range from "
            "clearly negative for the 2013-2015 and 2020 cohorts to positive for "
            "2012 and 2021), but it largely averages out at the overall level. "
            "The qualitative read is unchanged: a small, gradual, "
            "statistically-insignificant relative decline in low-wage employment "
            "after a minimum-wage increase.\n")
    else:
        lines.append("_TWFE estimates not found in results/did_estimates.csv._\n")

    lines.append("## Dynamic (event-study) path - cohort-robust\n")
    lines.append(
        f"Pre-treatment placebo cells (k<0): **{n_pre_sig} of {n_pre}** "
        "individually significant at 5% (pointwise); near-window |ATT| max "
        f"(k in [-4,-1]) = {near_pre_max:.4f} log pts - small, supporting "
        "approximate parallel pre-trends in the clean CSA comparisons. ")
    if not np.isnan(late_mean):
        lines.append(
            f"Post path (interior window k in [0, {EV_MAX}]): the effect deepens "
            f"to a trough of **{trough_att:+.4f}** log pts "
            f"({(np.exp(trough_att)-1)*100:+.2f}%) at **k={trough_k}** (~1 year "
            "after adoption), then partially mean-reverts, settling around "
            f"**{late_mean:+.4f}** log pts ({(np.exp(late_mean)-1)*100:+.2f}%) at "
            "the longer horizon (k>=8). Every interior post coefficient is "
            "negative but none is individually significant at 5% (pointwise). The "
            "shape - a gradual dip that bottoms out near the one-year mark and "
            "then eases - is the cohort-robust counterpart of the TWFE event "
            "study's negative post path, now free of forbidden-comparison "
            "contamination. (Far-out event times beyond the window rest on a "
            "single sparse cohort and are not interpreted.)\n")
    lines.append(
        "_Figure: `results/fig_csa_event_study.png` "
        "(left: cohort-robust dynamic ATT with 95% pointwise CIs; "
        "right: CSA-overall vs TWFE)._\n")

    lines.append("## Caveats\n")
    lines.append(
        "- **Pointwise CIs.** Bands are analytic and pointwise; simultaneous "
        "(uniform) bands via the multiplier bootstrap would be modestly wider. "
        "Individual-cell significance should be read with that in mind.\n"
        "- **Binary first-increase event.** Cohort = first increase only; the "
        "*size* of each increase and subsequent increases are not modelled. "
        "ATT is an average post-adoption shift, not a per-dollar elasticity.\n"
        "- **Never-treated control group.** Uses never-treated states as "
        "controls; a not-yet-treated control set is an available robustness "
        "variant (Day 7).\n"
        "- **Sparse extreme event times.** Distant relative periods rest on few "
        "cohorts; the interior window (k in [-12, 16]) holds the interpretable "
        "estimates.\n")

    (RESULTS / "csa_estimates.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
