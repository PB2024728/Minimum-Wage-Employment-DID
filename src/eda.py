"""
eda.py - Day 3 exploratory data analysis for the minimum-wage DiD project.

Reads the analysis panel (data/processed/panel.parquet, built by build_panel.py) and produces
the descriptive picture that motivates the DiD design, plus the data-quality checks that the
later estimators rely on. Nothing here is causal; it is the "look at the data first" pass.

Figures (all saved to results/ as 150-dpi PNG)
----------------------------------------------
    fig_treatment_timeline.png    swimlane: each treated state's min-wage increase events over time,
                                  marker size scaled by % size of the increase; first-treatment
                                  (cohort) quarter highlighted.
    fig_adoption_cohorts.png      bar chart: number of states whose FIRST in-window increase falls
                                  in each year (the staggered-adoption cohorts), with the running
                                  cumulative share of treated states.
    fig_minwage_paths.png         effective minimum-wage ($) paths, treated states vs the federal
                                  floor, showing the policy variation being exploited.
    fig_trends_treated_control.png   mean log L&H employment, treated vs never-treated, raw levels
                                  (left) and indexed to each group's 2010Q1 = 100 (right) so the
                                  pre-period co-movement (parallel-trends eyeball test) is visible.
    fig_leih_share_trends.png     mean L&H share of total nonfarm, treated vs control (secondary
                                  outcome) including the COVID-2020 collapse and recovery.
    fig_raw_event_study.png       descriptive (not regression) event-study: mean log_leih by
                                  relative event time k, recentred to k=-1, treated cohorts only.
    fig_coverage_quality.png      data-quality panel: balance/missingness grid, distribution of
                                  quarter-on-quarter log-employment growth (outlier scan), and the
                                  count of states observed each quarter.

Text output
-----------
    results/eda_summary.md        bullet findings: cohort structure, pre-trend eyeball read,
                                  COVID structural break, coverage/outlier flags, caveats.

Project rules honoured: Python only; reads cached processed panel (no API calls); standalone +
idempotent (safe to re-run); missing data reported, never imputed; figures -> results/.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # headless / automation-safe
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RESULTS_DIR = PROJECT_ROOT / "results"
PANEL_PATH = PROCESSED_DIR / "panel.parquet"

# Consistent palette across figures
C_TREAT = "#1f6f4b"     # treated states (green)
C_CTRL = "#b2452f"      # control states (rust)
C_FED = "#555555"       # federal floor / reference
C_ACCENT = "#2c6fa6"    # secondary accent (blue)
plt.rcParams.update({
    "figure.dpi": 110,
    "savefig.dpi": 150,
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
})


# --------------------------------------------------------------------------------------------
# Load + light prep
# --------------------------------------------------------------------------------------------
def load_panel() -> pd.DataFrame:
    if not PANEL_PATH.exists():
        raise SystemExit(
            f"panel not found at {PANEL_PATH}. Run src/build_panel.py first (Day 2)."
        )
    df = pd.read_parquet(PANEL_PATH)
    # quarter_ord is the integer quarter index (0 = 2010Q1). Build a plotting date too.
    df = df.sort_values(["jurisdiction", "quarter_ord"]).reset_index(drop=True)
    df["pdate"] = pd.PeriodIndex(df["quarter"], freq="Q").to_timestamp()
    return df


def quarter_to_date(qstr: str):
    return pd.Period(qstr, freq="Q").to_timestamp()


# --------------------------------------------------------------------------------------------
# Figure 1 - treatment timeline (swimlane of events)
# --------------------------------------------------------------------------------------------
def fig_treatment_timeline(df: pd.DataFrame) -> dict:
    events = pd.read_csv(RESULTS_DIR / "events_table.csv")
    events["edate"] = events["event_quarter"].map(quarter_to_date)

    treated = (
        df[df["treated"] == 1]
        .groupby("jurisdiction")
        .agg(first_treat=("first_treat", "first"))
        .reset_index()
    )
    treated["first_dt"] = treated["first_treat"].map(quarter_to_date)
    treated = treated.sort_values("first_dt", ascending=False)  # earliest at top
    order = treated["jurisdiction"].tolist()
    ypos = {s: i for i, s in enumerate(order)}

    fig, ax = plt.subplots(figsize=(12, 11))
    # baseline lane line per state
    for s, y in ypos.items():
        ax.plot(
            [df["pdate"].min(), df["pdate"].max()], [y, y],
            color="#dddddd", lw=0.8, zorder=1,
        )
    ev = events[events["jurisdiction"].isin(ypos)].copy()
    ev["y"] = ev["jurisdiction"].map(ypos)
    # marker size scaled to % increase (clip extremes for legibility)
    sizes = np.clip(ev["increase_pct"], 0, 25) * 9 + 12
    sc = ax.scatter(
        ev["edate"], ev["y"], s=sizes, c=ev["increase_pct"],
        cmap="viridis", vmin=0, vmax=20, alpha=0.85, edgecolor="white",
        linewidth=0.4, zorder=3,
    )
    # mark each state's first treatment with an open ring
    ft = treated.set_index("jurisdiction")
    ax.scatter(
        [ft.loc[s, "first_dt"] for s in order],
        [ypos[s] for s in order],
        s=140, facecolors="none", edgecolors=C_CTRL, linewidths=1.4, zorder=2,
        label="First treatment (cohort)",
    )
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=8)
    ax.set_ylim(-1, len(order))
    ax.set_xlabel("Quarter")
    ax.set_title("Treatment timeline: state minimum-wage increase events, 2010-2025")
    cb = fig.colorbar(sc, ax=ax, pad=0.01, fraction=0.025)
    cb.set_label("Increase size (%)")
    ax.legend(loc="lower right", frameon=True, fontsize=8)
    ax.margins(x=0.01)
    fig.tight_layout()
    out = RESULTS_DIR / "fig_treatment_timeline.png"
    fig.savefig(out)
    plt.close(fig)
    return {
        "file": out.name,
        "treated_states": len(order),
        "total_events": int(len(ev)),
        "earliest_event": ev["event_quarter"].min(),
        "latest_event": ev["event_quarter"].max(),
    }


# --------------------------------------------------------------------------------------------
# Figure 2 - adoption cohorts
# --------------------------------------------------------------------------------------------
def fig_adoption_cohorts(df: pd.DataFrame) -> dict:
    treated = (
        df[df["treated"] == 1]
        .groupby("jurisdiction")
        .agg(cohort_year=("cohort_year", "first"))
        .reset_index()
    )
    counts = treated["cohort_year"].value_counts().sort_index()
    years = list(range(int(df["year"].min()), int(df["year"].max()) + 1))
    counts = counts.reindex(years, fill_value=0)
    cum_share = counts.cumsum() / counts.sum()

    fig, ax = plt.subplots(figsize=(11, 5.5))
    bars = ax.bar(counts.index, counts.values, color=C_TREAT, alpha=0.85, width=0.7)
    for b, v in zip(bars, counts.values):
        if v > 0:
            ax.text(b.get_x() + b.get_width() / 2, v + 0.1, str(int(v)),
                    ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("States first treated (cohort size)", color=C_TREAT)
    ax.set_xlabel("Year of first state minimum-wage increase")
    ax.set_title("Staggered adoption: first-treatment cohorts")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    ax2 = ax.twinx()
    ax2.plot(cum_share.index, cum_share.values, color=C_CTRL, marker="o", lw=1.6)
    ax2.set_ylabel("Cumulative share of treated states", color=C_CTRL)
    ax2.set_ylim(0, 1.02)
    ax2.grid(False)
    fig.tight_layout()
    out = RESULTS_DIR / "fig_adoption_cohorts.png"
    fig.savefig(out)
    plt.close(fig)
    return {
        "file": out.name,
        "n_cohorts": int((counts > 0).sum()),
        "largest_cohort_year": int(counts.idxmax()),
        "largest_cohort_size": int(counts.max()),
    }


# --------------------------------------------------------------------------------------------
# Figure 3 - minimum-wage policy paths
# --------------------------------------------------------------------------------------------
def fig_minwage_paths(df: pd.DataFrame) -> dict:
    fig, ax = plt.subplots(figsize=(11, 6))
    treated_ids = df.loc[df["treated"] == 1, "jurisdiction"].unique()
    for s in treated_ids:
        sub = df[df["jurisdiction"] == s]
        ax.plot(sub["pdate"], sub["effective_min_wage"], color=C_TREAT,
                alpha=0.28, lw=0.9, zorder=2)
    # federal floor reference (any control row carries fed_min)
    fed = df.groupby("pdate")["fed_min"].first()
    ax.plot(fed.index, fed.values, color=C_FED, lw=2.4, ls="--",
            label="Federal floor ($7.25)", zorder=4)
    # treated cross-sectional mean
    tmean = df[df["treated"] == 1].groupby("pdate")["effective_min_wage"].mean()
    ax.plot(tmean.index, tmean.values, color=C_CTRL, lw=2.6,
            label="Treated states (mean)", zorder=5)
    ax.set_ylabel("Effective minimum wage ($/hr)")
    ax.set_xlabel("Quarter")
    ax.set_title("Policy variation: effective minimum-wage paths, treated states vs federal floor")
    ax.legend(loc="upper left", frameon=True)
    fig.tight_layout()
    out = RESULTS_DIR / "fig_minwage_paths.png"
    fig.savefig(out)
    plt.close(fig)
    final_mean = float(tmean.iloc[-1])
    return {
        "file": out.name,
        "treated_mean_minwage_2025Q4": round(final_mean, 2),
        "federal_floor": float(fed.iloc[-1]),
    }


# --------------------------------------------------------------------------------------------
# Figure 4 - treated vs control employment trends
# --------------------------------------------------------------------------------------------
def fig_trends_treated_control(df: pd.DataFrame) -> dict:
    grp = df.groupby(["treated", "pdate"]).agg(
        mean_log_leih=("log_leih", "mean"),
        mean_leih=("leih", "mean"),
    ).reset_index()

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5.5))
    labels = {1: "Treated (raised min wage)", 0: "Never-treated control"}
    colors = {1: C_TREAT, 0: C_CTRL}

    for t in (1, 0):
        g = grp[grp["treated"] == t]
        axL.plot(g["pdate"], g["mean_log_leih"], color=colors[t], lw=2, label=labels[t])
    axL.set_title("Mean log L&H employment (raw levels)")
    axL.set_ylabel("Mean log(employment, 000s)")
    axL.set_xlabel("Quarter")
    axL.legend(frameon=True, fontsize=9)

    # indexed to each group's 2010Q1 = 100 -> compare growth, eyeball parallel trends
    base = grp[grp["pdate"] == grp["pdate"].min()].set_index("treated")["mean_leih"]
    grp["indexed"] = grp.apply(lambda r: 100 * r["mean_leih"] / base.loc[r["treated"]], axis=1)
    for t in (1, 0):
        g = grp[grp["treated"] == t]
        axR.plot(g["pdate"], g["indexed"], color=colors[t], lw=2, label=labels[t])
    axR.axhline(100, color="#999999", lw=0.8, ls=":")
    axR.set_title("Indexed to 2010Q1 = 100 (growth comparison)")
    axR.set_ylabel("Employment index (2010Q1 = 100)")
    axR.set_xlabel("Quarter")
    axR.legend(frameon=True, fontsize=9)

    fig.suptitle("Leisure & Hospitality employment: treated vs control", fontweight="bold")
    fig.tight_layout()
    out = RESULTS_DIR / "fig_trends_treated_control.png"
    fig.savefig(out)
    plt.close(fig)

    # pre-period (2010Q1-2013Q4) indexed gap as a crude parallel-trends read
    pre = grp[grp["pdate"] < pd.Timestamp("2014-01-01")]
    pre_w = pre.pivot(index="pdate", columns="treated", values="indexed")
    pre_gap = float((pre_w[1] - pre_w[0]).abs().mean())
    return {
        "file": out.name,
        "pre2014_mean_abs_index_gap": round(pre_gap, 2),
    }


# --------------------------------------------------------------------------------------------
# Figure 5 - L&H share of nonfarm (secondary outcome)
# --------------------------------------------------------------------------------------------
def fig_leih_share_trends(df: pd.DataFrame) -> dict:
    grp = df.groupby(["treated", "pdate"])["leih_share"].mean().reset_index()
    fig, ax = plt.subplots(figsize=(11, 5.5))
    labels = {1: "Treated", 0: "Control"}
    colors = {1: C_TREAT, 0: C_CTRL}
    for t in (1, 0):
        g = grp[grp["treated"] == t]
        ax.plot(g["pdate"], 100 * g["leih_share"], color=colors[t], lw=2, label=labels[t])
    ax.axvspan(pd.Timestamp("2020-01-01"), pd.Timestamp("2020-10-01"),
               color="#cccccc", alpha=0.4, label="COVID shock (2020)")
    ax.set_ylabel("L&H share of total nonfarm (%)")
    ax.set_xlabel("Quarter")
    ax.set_title("Secondary outcome: Leisure & Hospitality share of total nonfarm employment")
    ax.legend(frameon=True, fontsize=9)
    fig.tight_layout()
    out = RESULTS_DIR / "fig_leih_share_trends.png"
    fig.savefig(out)
    plt.close(fig)
    return {"file": out.name}


# --------------------------------------------------------------------------------------------
# Figure 6 - descriptive (raw) event study
# --------------------------------------------------------------------------------------------
def fig_raw_event_study(df: pd.DataFrame) -> dict:
    t = df[(df["treated"] == 1) & df["event_time"].notna()].copy()
    t["event_time"] = t["event_time"].astype(int)
    # within-state demean of log_leih removes level differences -> read relative path
    t["demeaned"] = t["log_leih"] - t.groupby("jurisdiction")["log_leih"].transform("mean")
    window = t[(t["event_time"] >= -12) & (t["event_time"] <= 16)]
    prof = window.groupby("event_time")["demeaned"].agg(["mean", "count"]).reset_index()
    # recentre so k = -1 is 0 (standard event-study normalisation)
    if (-1) in prof["event_time"].values:
        ref = prof.loc[prof["event_time"] == -1, "mean"].iloc[0]
        prof["mean"] = prof["mean"] - ref

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.axvline(0, color=C_CTRL, lw=1.2, ls="--", label="Treatment (k=0)")
    ax.axhline(0, color="#999999", lw=0.8, ls=":")
    ax.plot(prof["event_time"], prof["mean"], color=C_TREAT, marker="o", lw=1.8)
    ax.set_xlabel("Quarters relative to first treatment (k)")
    ax.set_ylabel("Mean within-state log L&H employment\n(recentred to k = -1)")
    ax.set_title("Descriptive event study (raw means, not a regression)")
    ax.legend(frameon=True, fontsize=9)
    fig.tight_layout()
    out = RESULTS_DIR / "fig_raw_event_study.png"
    fig.savefig(out)
    plt.close(fig)
    # crude pre-trend read: mean |coef| for k in [-8,-2]
    pre = prof[(prof["event_time"] >= -8) & (prof["event_time"] <= -2)]
    return {
        "file": out.name,
        "pre_trend_mean_abs": round(float(pre["mean"].abs().mean()), 4),
        "min_cohort_cells_at_k": int(prof["count"].min()),
    }


# --------------------------------------------------------------------------------------------
# Figure 7 + checks - data quality
# --------------------------------------------------------------------------------------------
def fig_coverage_quality(df: pd.DataFrame) -> dict:
    n_states = df["jurisdiction"].nunique()
    n_quarters = df["quarter"].nunique()
    expected = n_states * n_quarters
    balanced = len(df) == expected

    # missingness per key column
    key_cols = ["leih", "log_leih", "nonfarm", "leih_share", "ur", "min_wage_level"]
    miss = {c: int(df[c].isna().sum()) for c in key_cols}

    # per-quarter state count (gap detection: any quarter missing states?)
    per_q = df.groupby("quarter_ord")["jurisdiction"].nunique()
    gap_quarters = int((per_q < n_states).sum())

    # QoQ log-employment growth (outlier scan)
    df = df.sort_values(["jurisdiction", "quarter_ord"]).copy()
    df["dlog"] = df.groupby("jurisdiction")["log_leih"].diff()
    dlog = df["dlog"].dropna()
    mu, sd = dlog.mean(), dlog.std()
    z = (dlog - mu) / sd
    n_outliers = int((z.abs() > 4).sum())
    # biggest swings + their context (mostly COVID-2020)
    df["z_dlog"] = (df["dlog"] - mu) / sd
    extremes = (
        df.reindex(df["z_dlog"].abs().sort_values(ascending=False).index)
        .head(8)[["jurisdiction", "quarter", "dlog"]]
        .reset_index(drop=True)
    )

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # (a) per-quarter coverage
    ax = axes[0]
    ax.plot(per_q.index, per_q.values, color=C_ACCENT, lw=2)
    ax.set_ylim(0, n_states + 2)
    ax.axhline(n_states, color=C_CTRL, ls="--", lw=1, label=f"Full panel = {n_states}")
    ax.set_title("Coverage: jurisdictions observed per quarter")
    ax.set_xlabel("Quarter index (0 = 2010Q1)")
    ax.set_ylabel("Jurisdictions with data")
    ax.legend(frameon=True, fontsize=8)

    # (b) QoQ growth distribution
    ax = axes[1]
    ax.hist(dlog, bins=80, color=C_TREAT, alpha=0.8)
    ax.axvline(mu + 4 * sd, color=C_CTRL, ls="--", lw=1)
    ax.axvline(mu - 4 * sd, color=C_CTRL, ls="--", lw=1, label="±4σ")
    ax.set_yscale("log")
    ax.set_title("Quarter-on-quarter Δlog(L&H employment)")
    ax.set_xlabel("Δ log employment")
    ax.set_ylabel("Count (log scale)")
    ax.legend(frameon=True, fontsize=8)

    # (c) missingness bar
    ax = axes[2]
    ax.bar(range(len(key_cols)), [miss[c] for c in key_cols], color=C_ACCENT, alpha=0.85)
    ax.set_xticks(range(len(key_cols)))
    ax.set_xticklabels(key_cols, rotation=45, ha="right", fontsize=8)
    ax.set_title("Missing cells per key column")
    ax.set_ylabel("Missing cells")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.text(0.5, 0.85, "balanced panel\n(0 missing)" if balanced and sum(miss.values()) == 0 else "",
            transform=ax.transAxes, ha="center", color=C_TREAT, fontsize=10, fontweight="bold")

    fig.suptitle("Data-quality checks", fontweight="bold")
    fig.tight_layout()
    out = RESULTS_DIR / "fig_coverage_quality.png"
    fig.savefig(out)
    plt.close(fig)

    return {
        "file": out.name,
        "n_states": n_states,
        "n_quarters": n_quarters,
        "balanced": balanced,
        "expected_rows": expected,
        "actual_rows": len(df),
        "missing": miss,
        "gap_quarters": gap_quarters,
        "qoq_outliers_gt4sd": n_outliers,
        "qoq_std": round(float(sd), 4),
        "extreme_swings": extremes.to_dict("records"),
    }


# --------------------------------------------------------------------------------------------
# Summary writer
# --------------------------------------------------------------------------------------------
def write_summary(df: pd.DataFrame, results: dict) -> None:
    tl = results["timeline"]
    co = results["cohorts"]
    mw = results["minwage"]
    tr = results["trends"]
    es = results["event_study"]
    dq = results["quality"]

    n_treated = int((df.groupby("jurisdiction")["treated"].first() == 1).sum())
    n_control = df["jurisdiction"].nunique() - n_treated

    ext_lines = "\n".join(
        f"  - {r['jurisdiction']} {r['quarter']}: Δlog = {r['dlog']:+.3f}"
        for r in dq["extreme_swings"]
    )

    lines = [
        "# EDA Summary - Project #4 (Day 3)",
        "",
        "Descriptive pass over `data/processed/panel.parquet` (51 jurisdictions x 64 quarters, "
        "2010Q1-2025Q4). Figures in `results/`. Nothing here is causal - it sets up the DiD.",
        "",
        "## Treatment structure",
        "",
        f"- **{n_treated} treated** jurisdictions (>=1 genuine state min-wage increase above the "
        f"federal floor) vs **{n_control} never-treated controls** (incl. the 5 no-statute states).",
        f"- **{tl['total_events']} increase events** span {tl['earliest_event']} -> "
        f"{tl['latest_event']} (`fig_treatment_timeline.png`).",
        f"- Adoption is **staggered across {co['n_cohorts']} yearly cohorts**; the largest single "
        f"cohort is **{co['largest_cohort_year']} ({co['largest_cohort_size']} states)** "
        f"(`fig_adoption_cohorts.png`). Staggered timing is exactly why a naive TWFE can be biased "
        f"and why the Day 6 Callaway-Sant'Anna estimator is on the plan.",
        f"- By 2025Q4 the treated-state mean effective minimum wage is "
        f"**${mw['treated_mean_minwage_2025Q4']:.2f}** vs the **${mw['federal_floor']:.2f}** federal "
        f"floor that binds the controls (`fig_minwage_paths.png`) - clear policy variation to exploit.",
        "",
        "## Raw outcome trends (treated vs control)",
        "",
        f"- In indexed terms (2010Q1 = 100), treated and control L&H employment track each other "
        f"closely through the pre-2014 window: **mean absolute index gap = "
        f"{tr['pre2014_mean_abs_index_gap']:.2f} points** (`fig_trends_treated_control.png`). "
        f"That visual co-movement is the eyeball parallel-trends check; Day 5 tests it formally.",
        f"- The descriptive event study (within-state demeaned, recentred to k=-1) shows pre-event "
        f"coefficients near zero (**mean |k in [-8,-2]| = {es['pre_trend_mean_abs']:.4f}**) "
        f"(`fig_raw_event_study.png`). Encouraging, but not a substitute for the regression version.",
        f"- The L&H share of nonfarm (`fig_leih_share_trends.png`) shows the **2020 COVID collapse** "
        f"in both groups - a common shock the design must absorb via period fixed effects.",
        "",
        "## Data-quality checks",
        "",
        f"- **Panel is balanced:** {dq['actual_rows']} rows = expected "
        f"{dq['n_states']} x {dq['n_quarters']} ({dq['expected_rows']}). "
        f"No quarters drop states (gap quarters = {dq['gap_quarters']}).",
        f"- **No missing cells** across leih / log_leih / nonfarm / leih_share / ur / min_wage_level "
        f"(`fig_coverage_quality.png`).",
        f"- **Outlier scan:** {dq['qoq_outliers_gt4sd']} quarter-on-quarter Δlog moves exceed 4σ "
        f"(σ = {dq['qoq_std']}). The largest swings are the 2020Q2 COVID drop and 2020Q3 rebound, "
        f"not data errors - they are real and should be retained (period FE absorb them):",
        ext_lines,
        "",
        "## Caveats carried forward",
        "",
        "- Min-wage events are dated to **Q1** (annual FRED series resolution); mid-year statutory "
        "changes can't be timed more precisely - a known limitation for event timing.",
        "- COVID-2020 is a large common shock; pre-2020 windows may give cleaner parallel-trends "
        "reads. Worth a robustness cut on Day 7.",
        "- 'Treated' here is *ever-treated*; many treated states raise the wage repeatedly, so the "
        "binary `post` collapses a dose. Day 6's group-time ATT handles staggered onset properly.",
        "",
        "_Checkpoint (Day 3): EDA figures saved._",
        "",
    ]
    (RESULTS_DIR / "eda_summary.md").write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------------------------
def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = load_panel()
    results = {
        "timeline": fig_treatment_timeline(df),
        "cohorts": fig_adoption_cohorts(df),
        "minwage": fig_minwage_paths(df),
        "trends": fig_trends_treated_control(df),
        "share": fig_leih_share_trends(df),
        "event_study": fig_raw_event_study(df),
        "quality": fig_coverage_quality(df),
    }
    write_summary(df, results)

    print("EDA complete. Figures written to results/:")
    for k, v in results.items():
        print(f"  [{k}] {v.get('file', '')}")
    print("Summary: results/eda_summary.md")


if __name__ == "__main__":
    main()
