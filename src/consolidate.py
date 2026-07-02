"""Day 8 - Consolidate all estimates into one comparison table + final figures.

Reads the per-day result CSVs in results/ and produces:
  - results/comparison_table.csv / .md  (pooled OLS vs TWFE vs Callaway-Sant'Anna)
  - results/fig_summary.png             (estimator forest plot + CSA event study)

Idempotent, standalone. Python only; no FRED calls (pure consolidation of
already-saved results).
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"


def pct(x: float) -> float:
    """Log points -> percent effect via exp transform."""
    return (math.exp(x) - 1.0) * 100.0


# ---------------------------------------------------------------- load sources
did = pd.read_csv(RES / "did_estimates.csv")
csa = pd.read_csv(RES / "csa_aggregations.csv")

ols = did[did["model"].str.startswith("Pooled OLS")].iloc[0]
twfe = did[did["model"].str.startswith("TWFE")].iloc[0]
csa_overall = csa[csa["aggregation"] == "overall_simple"].iloc[0]

# ----------------------------------------------------------- comparison table
rows = []
rows.append(
    dict(
        Estimator="Pooled OLS (no FE)",
        Coef_logpts=ols["coef"],
        SE=ols["se"],
        CI_low=ols["ci_low"],
        CI_high=ols["ci_high"],
        pct_effect=pct(ols["coef"]),
        pct_CI_low=pct(ols["ci_low"]),
        pct_CI_high=pct(ols["ci_high"]),
        p_value=ols["p_value"],
        Staggered_robust="no",
        Notes="Cross-sectional; confounded by which states raise wages.",
    )
)
rows.append(
    dict(
        Estimator="TWFE DiD (state+period FE)",
        Coef_logpts=twfe["coef"],
        SE=twfe["se"],
        CI_low=twfe["ci_low"],
        CI_high=twfe["ci_high"],
        pct_effect=pct(twfe["coef"]),
        pct_CI_low=pct(twfe["ci_low"]),
        pct_CI_high=pct(twfe["ci_high"]),
        p_value=twfe["p_value"],
        Staggered_robust="no",
        Notes="SE clustered by state (51 clusters). Two-way FE.",
    )
)
rows.append(
    dict(
        Estimator="Callaway-Sant'Anna (2021)",
        Coef_logpts=csa_overall["att"],
        SE=csa_overall["std_error"],
        CI_low=csa_overall["ci_low"],
        CI_high=csa_overall["ci_high"],
        pct_effect=pct(csa_overall["att"]),
        pct_CI_low=pct(csa_overall["ci_low"]),
        pct_CI_high=pct(csa_overall["ci_high"]),
        p_value=np.nan,  # CSA reports CI; no single analytic p in source
        Staggered_robust="yes",
        Notes="Group-size-weighted ATT; doubly-robust; never-treated controls.",
    )
)

tab = pd.DataFrame(rows)
tab.to_csv(RES / "comparison_table.csv", index=False)

# --- markdown rendering
def fmt_ci(lo, hi, p=False):
    if p:
        return f"[{lo:+.2f}%, {hi:+.2f}%]"
    return f"[{lo:+.4f}, {hi:+.4f}]"


md = []
md.append("# Consolidated estimator comparison - minimum-wage increase -> log L&H employment\n")
md.append(
    "Outcome: `log_leih` (log Leisure & Hospitality employment). Treatment: a state's "
    "first minimum-wage increase above its prior level. Panel: 51 jurisdictions x quarter, "
    "2010Q1-2025Q4 (N = 3,264 state-quarters).\n"
)
md.append("| Estimator | Coef (log pts) | SE | 95% CI (log pts) | % effect | 95% CI (%) | Staggered-robust |")
md.append("|---|---|---|---|---|---|---|")
for _, r in tab.iterrows():
    pstr = "" if math.isnan(r["p_value"]) else f" (p={r['p_value']:.3f})"
    md.append(
        f"| {r['Estimator']} | {r['Coef_logpts']:+.4f}{pstr} | {r['SE']:.4f} | "
        f"{fmt_ci(r['CI_low'], r['CI_high'])} | {r['pct_effect']:+.2f}% | "
        f"{fmt_ci(r['pct_CI_low'], r['pct_CI_high'], p=True)} | {r['Staggered_robust']} |"
    )
md.append("")
md.append(
    "All three estimators agree on a small, negative, statistically insignificant relative "
    "decline in low-wage-sector employment after a minimum-wage increase. The TWFE and "
    "Callaway-Sant'Anna point estimates differ by only "
    f"{abs(twfe['coef'] - csa_overall['att']):.4f} log points "
    f"({100*abs(twfe['coef']-csa_overall['att'])/abs(twfe['coef']):.0f}% of the TWFE magnitude), "
    "so the staggered-adoption correction barely moves the headline."
)
(RES / "comparison_table.md").write_text("\n".join(md), encoding="utf-8")
print("Wrote comparison_table.csv / .md")
print(tab[["Estimator", "Coef_logpts", "SE", "pct_effect"]].to_string(index=False))

# ------------------------------------------------------------- final summary fig
# Panel A: forest plot of the three estimators (% effect with 95% CI)
# Panel B: Callaway-Sant'Anna dynamic event study, interior window k in [-12, 16]
ev = csa[csa["aggregation"] == "event_dynamic"].copy()
ev["k"] = ev["key"].astype(int)
ev = ev[(ev["k"] >= -12) & (ev["k"] <= 16)].sort_values("k")

fig = plt.figure(figsize=(13, 5.2))
gs = GridSpec(1, 2, width_ratios=[1.0, 1.25], wspace=0.28)

# --- Panel A
axA = fig.add_subplot(gs[0, 0])
labels = ["Pooled OLS\n(no FE)", "TWFE DiD\n(state+period FE)", "Callaway-\nSant'Anna"]
ys = np.arange(len(labels))[::-1]
eff = tab["pct_effect"].values
lo = tab["pct_CI_low"].values
hi = tab["pct_CI_high"].values
colors = ["#9e9e9e", "#1f77b4", "#d62728"]
for y, e, l, h, c in zip(ys, eff, lo, hi, colors):
    axA.plot([l, h], [y, y], color=c, lw=2.4, solid_capstyle="round")
    axA.plot(e, y, "o", color=c, ms=9, zorder=5)
    axA.annotate(f"{e:+.2f}%", (e, y), textcoords="offset points", xytext=(0, 11),
                 ha="center", fontsize=9, color=c, fontweight="bold")
axA.axvline(0, color="black", lw=1, ls="--", alpha=0.7)
axA.set_yticks(ys)
axA.set_yticklabels(labels, fontsize=9)
axA.set_xlabel("Effect on L&H employment (%, 95% CI)")
axA.set_title("A. Estimator comparison", fontsize=11, fontweight="bold", loc="left")
axA.set_ylim(-0.6, len(labels) - 0.2)
axA.grid(axis="x", alpha=0.25)

# --- Panel B
axB = fig.add_subplot(gs[0, 1])
k = ev["k"].values
att = ev["att"].values * 100  # to percent-ish (log pts ~ %)
clo = ev["ci_low"].values * 100
chi = ev["ci_high"].values * 100
axB.fill_between(k, clo, chi, color="#d62728", alpha=0.15, label="95% pointwise CI")
axB.plot(k, att, "-o", color="#d62728", ms=4, lw=1.6, label="CSA dynamic ATT")
axB.axhline(0, color="black", lw=1, ls="--", alpha=0.7)
axB.axvline(-0.5, color="gray", lw=1, ls=":", alpha=0.8)
axB.annotate("adoption", (-0.5, axB.get_ylim()[1]), fontsize=8, color="gray",
             ha="left", va="top", rotation=0, xytext=(2, -2), textcoords="offset points")
axB.set_xlabel("Quarters relative to first minimum-wage increase (k)")
axB.set_ylabel("ATT (log pts x100)")
axB.set_title("B. Cohort-robust event study (Callaway-Sant'Anna)",
              fontsize=11, fontweight="bold", loc="left")
axB.legend(fontsize=8, loc="lower left")
axB.grid(alpha=0.25)

fig.suptitle(
    "Minimum-wage increases and low-wage (L&H) employment: a small, insignificant relative decline",
    fontsize=12.5, fontweight="bold", y=1.02,
)
fig.savefig(RES / "fig_summary.png", dpi=150, bbox_inches="tight")
print("Wrote fig_summary.png")
