"""
estimate_did.py - Day 4 first-pass DiD estimation for the minimum-wage project.

Reads the analysis panel (data/processed/panel.parquet, built by build_panel.py) and estimates
the effect of a state minimum-wage increase on log Leisure & Hospitality employment with two
specifications, side by side:

    (1) Pooled OLS  -  log_leih ~ treated_post           (no fixed effects)
                       The naive baseline. With no controls for which states raise their minimum
                       wage or for common time shocks, the coefficient is contaminated by
                       cross-state confounding (high-wage coastal states both raise minimums AND
                       have structurally different L&H employment levels). Shown so the bias is
                       visible, not to be believed.

    (2) Two-way fixed-effects (TWFE) DiD  -  log_leih ~ treated_post + StateFE + PeriodFE
                       State fixed effects absorb time-invariant level differences across states;
                       period (quarter) fixed effects absorb common national shocks (e.g. the
                       2020 COVID collapse). Standard errors are CLUSTERED BY STATE to allow
                       arbitrary within-state serial correlation - the appropriate inference for a
                       state-level panel policy (Bertrand-Duflo-Mullainathan 2004).

The treatment variable `treated_post` is the DiD interaction (ever-treated x post-first-increase),
already built in the panel. Under state + period FE its main effects (`treated`, `post`) are
absorbed, so `treated_post` is the DiD estimate.

Outputs (results/)
------------------
    results/did_estimates.csv   tidy table: model, coef, cluster_se, t, p, ci_low, ci_high, n, ...
    results/did_estimates.md    same, formatted, with a plain-language comparison/interpretation.

Caveats logged at runtime and in the .md:
  * 6 states are "always-treated" (first increase at the 2010Q1 panel start) so contribute no
    clean pre-period; they are kept (drop-sensitivity is a Day 5+ robustness item, noted not done).
  * TWFE with staggered timing and heterogeneous effects can be biased (Goodman-Bacon 2021); the
    Callaway-Sant'Anna estimator on Day 6 is the robustness check, not this script.

Project rules honoured: Python only; reads cached processed panel (no API calls); standalone +
idempotent (safe to re-run); results -> results/.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
PROCESSED = ROOT / "data" / "processed"

OUTCOME = "log_leih"
TREAT = "treated_post"        # DiD interaction: ever-treated x post-first-increase
STATE = "jurisdiction"        # entity / state fixed effect
PERIOD = "quarter_ord"        # time / period fixed effect
ALPHA = 0.05


def load_panel() -> pd.DataFrame:
    """Load the processed panel, preferring parquet, falling back to csv."""
    pq = PROCESSED / "panel.parquet"
    csv = PROCESSED / "panel.csv"
    try:
        df = pd.read_parquet(pq)
        src = pq
    except Exception:
        df = pd.read_csv(csv)
        src = csv
    print(f"[load] panel from {src.name}: {df.shape[0]} rows x {df.shape[1]} cols")
    needed = {OUTCOME, TREAT, STATE, PERIOD}
    missing = needed - set(df.columns)
    if missing:
        raise SystemExit(f"[fatal] panel missing required columns: {missing}")
    # required-field integrity: estimation cannot proceed with NA in the model fields
    na = df[list(needed)].isna().sum()
    if na.any():
        print(f"[warn] dropping rows with NA in model fields:\n{na[na>0]}")
        df = df.dropna(subset=list(needed)).copy()
    # period FE must be categorical, not a linear trend
    df[PERIOD] = df[PERIOD].astype(int)
    return df


def fit_pooled_ols(df: pd.DataFrame):
    """Naive pooled OLS, no fixed effects. HC1 robust SEs (still wrong inference; for display)."""
    model = smf.ols(f"{OUTCOME} ~ {TREAT}", data=df)
    res = model.fit(cov_type="HC1")
    return res


def fit_twfe(df: pd.DataFrame):
    """TWFE DiD: treated_post + state FE + period FE, SEs clustered by state."""
    formula = f"{OUTCOME} ~ {TREAT} + C({STATE}) + C({PERIOD})"
    model = smf.ols(formula, data=df)
    res = model.fit(
        cov_type="cluster",
        cov_kwds={"groups": df[STATE]},
    )
    return res


def extract(res, model_name: str, df: pd.DataFrame, n_clusters: int | None = None) -> dict:
    """Pull the treated_post row out of a fitted result into a tidy dict."""
    coef = res.params[TREAT]
    se = res.bse[TREAT]
    t = res.tvalues[TREAT]
    p = res.pvalues[TREAT]
    ci = res.conf_int(alpha=ALPHA).loc[TREAT]
    return {
        "model": model_name,
        "coef": coef,
        "se": se,
        "t": t,
        "p_value": p,
        "ci_low": ci[0],
        "ci_high": ci[1],
        "pct_effect": 100.0 * (np.exp(coef) - 1.0),     # log outcome -> approx % change
        "pct_ci_low": 100.0 * (np.exp(ci[0]) - 1.0),
        "pct_ci_high": 100.0 * (np.exp(ci[1]) - 1.0),
        "n_obs": int(res.nobs),
        "n_states": int(df[STATE].nunique()),
        "n_periods": int(df[PERIOD].nunique()),
        "n_clusters": n_clusters,
        "se_type": res.cov_type,
        "r2_within_or_overall": res.rsquared,
    }


def write_outputs(table: pd.DataFrame) -> None:
    RESULTS.mkdir(exist_ok=True)
    csv_path = RESULTS / "did_estimates.csv"
    table.to_csv(csv_path, index=False)
    print(f"[save] {csv_path}")

    pooled = table[table.model == "Pooled OLS (no FE)"].iloc[0]
    twfe = table[table.model == "TWFE DiD (state+period FE, clustered SE)"].iloc[0]

    def fmt(r):
        sig = "***" if r.p_value < 0.01 else "**" if r.p_value < 0.05 else "*" if r.p_value < 0.10 else ""
        return (
            f"| {r.model} | {r.coef:+.4f}{sig} | {r.se:.4f} | {r.t:+.2f} | {r.p_value:.3f} | "
            f"[{r.ci_low:+.4f}, {r.ci_high:+.4f}] | {r.pct_effect:+.2f}% | {int(r.n_obs)} |"
        )

    md = []
    md.append("# Day 4 - DiD estimates: minimum-wage increase -> log L&H employment\n")
    md.append(f"Outcome: `{OUTCOME}` (log Leisure & Hospitality employment). "
              f"Treatment: `{TREAT}` (ever-treated state x post-first-increase).\n")
    md.append("## Results table\n")
    md.append("| Model | Coef (log pts) | SE | t | p | 95% CI | % effect | N |")
    md.append("|---|---|---|---|---|---|---|---|")
    md.append(fmt(pooled))
    md.append(fmt(twfe))
    md.append("\nSignificance: `***` p<0.01, `**` p<0.05, `*` p<0.10. "
              "Pooled-OLS SE is HC1 (heteroskedasticity-robust); TWFE SE is clustered by state "
              f"({int(twfe.n_clusters)} clusters).\n")

    md.append("## Headline (TWFE)\n")
    md.append(
        f"A state minimum-wage increase is associated with a **{twfe.pct_effect:+.2f}%** change in "
        f"low-wage-sector (L&H) employment "
        f"(95% CI [{twfe.pct_ci_low:+.2f}%, {twfe.pct_ci_high:+.2f}%]), "
        f"clustered-by-state SE = {twfe.se:.4f} log points, "
        f"{'statistically significant' if twfe.p_value < 0.05 else 'not statistically significant'} "
        f"at the 5% level (p = {twfe.p_value:.3f}).\n"
    )

    shift = twfe.coef - pooled.coef
    md.append("## Comparison / interpretation\n")
    md.append(
        f"- **Pooled OLS** gives {pooled.coef:+.4f} log points ({pooled.pct_effect:+.2f}%). With no "
        f"fixed effects this conflates the policy with *which* states raise their minimum wage: "
        f"high-cost states (CA, NY, WA, MA...) both adopt higher minimums and have structurally "
        f"different L&H employment levels, so the raw cross-sectional gap is confounding, not effect.\n"
    )
    md.append(
        f"- **TWFE DiD** gives {twfe.coef:+.4f} log points ({twfe.pct_effect:+.2f}%). State FE remove "
        f"fixed level differences across states; period FE remove common shocks (notably the 2020 "
        f"COVID collapse that hit L&H everywhere). The estimate moves by {shift:+.4f} log points "
        f"relative to pooled OLS, the size of the confounding the design removes.\n"
    )
    md.append(
        f"- Inference: clustering by state ({int(twfe.n_clusters)} clusters) inflates the SE from the "
        f"naive iid value, the standard correction for serially correlated state panels "
        f"(Bertrand-Duflo-Mullainathan 2004). The TWFE point estimate is the Day-4 checkpoint.\n"
    )

    md.append("## Caveats (this is a first pass, not the final number)\n")
    md.append(
        "- **Always-treated states:** 6 jurisdictions have their first increase at the 2010Q1 panel "
        "start, so they contribute no clean pre-period and act partly as controls-by-timing. Kept here; "
        "drop-sensitivity is a robustness item.\n"
    )
    md.append(
        "- **Staggered timing + heterogeneous effects:** the TWFE coefficient is a variance-weighted "
        "average of 2x2 DiDs and can be biased when effects vary over time/cohort (Goodman-Bacon 2021; "
        "de Chaisemartin-D'Haultfoeuille 2020). The Callaway-Sant'Anna estimator (Day 6) is the "
        "designed robustness check; treat this number as provisional until that reconciliation.\n"
    )
    md.append(
        "- **No controls yet:** `ur` and `min_wage_gap` are available but excluded to keep the "
        "checkpoint spec clean (`log_leih ~ treated_post + FE`). Adding them is a Day 7 robustness pass.\n"
    )
    md.append(
        "- **Binary treatment:** `treated_post` is an on/off indicator, not the size of the increase; "
        "it estimates an average post-adoption shift, not a per-dollar elasticity.\n"
    )

    md_path = RESULTS / "did_estimates.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(f"[save] {md_path}")


def main() -> None:
    df = load_panel()
    n_states = df[STATE].nunique()
    n_periods = df[PERIOD].nunique()
    ever_treated = int(df.groupby(STATE)["treated"].max().sum()) if "treated" in df else None
    print(f"[panel] {n_states} states x {n_periods} periods; ever-treated states: {ever_treated}; "
          f"treated_post share: {df[TREAT].mean():.3f}")

    print("[fit] pooled OLS (no FE)...")
    pooled_res = fit_pooled_ols(df)
    pooled_row = extract(pooled_res, "Pooled OLS (no FE)", df, n_clusters=None)

    print("[fit] TWFE DiD (state FE + period FE, clustered SE)...")
    twfe_res = fit_twfe(df)
    twfe_row = extract(twfe_res, "TWFE DiD (state+period FE, clustered SE)", df,
                       n_clusters=df[STATE].nunique())

    table = pd.DataFrame([pooled_row, twfe_row])
    pd.set_option("display.float_format", lambda x: f"{x:.4f}")
    print("\n=== DiD estimates (treated_post on log_leih) ===")
    print(table[["model", "coef", "se", "t", "p_value", "ci_low", "ci_high",
                 "pct_effect", "n_obs", "n_clusters"]].to_string(index=False))

    write_outputs(table)
    print("\n[done] Day 4 estimation complete.")


if __name__ == "__main__":
    main()
