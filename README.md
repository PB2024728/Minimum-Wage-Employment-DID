# Minimum Wage & Low-Wage Employment — A State-Panel Difference-in-Differences

**Focus area:** `ECONOMETRICS` (causal inference) ·

## Research question
Do statutory state minimum-wage increases reduce employment in low-wage industries? We estimate the effect of state minimum-wage increases on state-level Leisure & Hospitality employment, relative to states with no change.

## Headline result
Across pooled OLS, TWFE, and the staggered-robust Callaway–Sant'Anna estimator, a state's first minimum-wage increase is associated with a small (**≈ −2%**) relative decline in Leisure & Hospitality employment that is **not statistically distinguishable from zero** (Callaway–Sant'Anna ATT −2.1%, 95% CI [−5.3%, +1.1%]). The staggered-adoption correction barely moves the estimate, and the result survives high-wage-sector and fake-date placebos. Read it as *no evidence of large minimum-wage disemployment*, with the data unable to rule out a small negative effect. Full write-up in [`results/findings.md`](results/findings.md).

> **Note on data:** raw FRED pulls are **not** committed to this repo (they are regenerated from the FRED API — see Setup). After cloning you will need a free FRED API key to run the pipeline end-to-end; the test suite and the committed `results/` artifacts require neither.

## Identification strategy

**Setting and estimand.** We treat each state's statutory minimum-wage increase as a discrete policy event and estimate its causal effect on employment in the Leisure & Hospitality sector — the industry with the highest share of minimum-wage workers, and therefore the sector where an employment response, if one exists, should be most detectable. The estimand is the average treatment effect on the treated (ATT): the percent change in low-wage-sector employment in states that raised their minimum wage, relative to the counterfactual path they would have followed absent the increase. The outcome is `log(employment)`, so coefficients read approximately as percent changes.

**Panel.** A state × quarter panel, 2010Q1–2025Q4, covering 50 states + DC (51 jurisdictions). Monthly FRED series are collapsed to quarterly means. Treatment is defined per jurisdiction as the first quarter in which the state minimum wage (`STTMINWG<XX>`) rises above its prior level; the *size* of each increase is recorded for dose-response checks. Because states raise wages in different quarters, treatment timing is **staggered**.

**Why DiD identifies a causal effect.** A simple before/after comparison conflates the policy with national shocks (recessions, COVID, secular L&H growth); a simple treated-vs-untreated cross-section conflates the policy with fixed state differences (cost of living, industry mix). Difference-in-differences removes both: **state fixed effects** absorb time-invariant level differences across jurisdictions, and **period fixed effects** absorb shocks common to all states in a given quarter. What remains identifies the treatment effect *under the parallel-trends assumption* — that, absent treatment, treated and control states' log-employment would have evolved in parallel.

**Estimators (in increasing robustness).**

1. **Pooled OLS** (no fixed effects) — a deliberately biased baseline that shows the confounding the design is meant to remove.
2. **Two-way fixed effects (TWFE)** — `log_leih ~ post_treat + StateFE + PeriodFE`, standard errors clustered by state. This is the headline specification.
3. **Event study** — replace the single `post` indicator with leads and lags of relative event time `k = period − first-treatment period`. Pre-treatment coefficients (`k < 0`) provide a direct, falsifiable test of parallel trends; post-treatment coefficients (`k ≥ 0`) trace the dynamic response.
4. **Callaway & Sant'Anna (2021)** — group-time ATT estimator. Canonical TWFE is biased when treatment is staggered *and* effects are heterogeneous across cohorts/time, because already-treated units enter the comparison group with "forbidden" weights. CSA estimates clean ATT(g,t) using not-yet-treated (or never-treated) controls and aggregates them, providing the key robustness cross-check.

**Controls and the comparison group.** State unemployment rate (`<XX>UR`) captures local labor-demand conditions; total nonfarm employment (`<XX>NA`) normalizes for state size and supplies the secondary outcome (L&H share of total nonfarm). The federal minimum (`FEDMINNFRWG`) flags **federal-floor states** — jurisdictions whose binding wage is the federal minimum because they have no higher state statute; these act as controls until/unless their own binding wage changes.

**Falsification.** (a) Apply the identical design to a **high-wage sector** (Professional & Business Services, `<XX>PBSV`), where a minimum-wage effect should be near zero — a non-zero estimate would signal a confounded design. (b) Assign **fake event dates** 8 quarters before the true increases; a "significant" pre-event effect would indicate anticipation or pre-trend contamination.

**Key threats (carried as caveats).** Endogenous timing (states may raise wages in strong local economies), spillovers to neighboring/control states, simultaneous policy changes, and the well-known staggered-TWFE bias — the last addressed directly by estimator (4).

## Data (all free, via FRED API)
| Role | Series pattern | Notes |
|---|---|---|
| Treatment | `STTMINWG<XX>` | State minimum wage, per state |
| Outcome | `<XX>LEIH` | All Employees: Leisure & Hospitality, by state |
| Normalizer | `<XX>NA` | Total Nonfarm employment, by state |
| Control | `<XX>UR` | State unemployment rate |
| Flag | `FEDMINNFRWG` | Federal minimum (identify federal-floor states) |

Coverage: 50 states + DC, monthly 2010–2025, collapsed to quarterly/annual panel.

## Setup

Requires **Python 3.10+**.

```bash
# 1. Clone and enter the project
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

**FRED API key.** The data comes from the Federal Reserve's [FRED](https://fred.stlouisfed.org/) service. Request a free API key at <https://fredaccount.stlouisfed.org/apikeys>, then create a file named `.env` in the project root containing:

```
FRED_API_KEY=your_32_character_key_here
```

`.env` is gitignored and must never be committed. You only need the key to pull fresh data (`fetch_fred.py`); the committed `results/` and the test suite run without it.

## Pipeline
```
src/series_map.py        # exact FRED series IDs for 51 jurisdictions + validator
src/fetch_fred.py        # pull series -> data/raw
src/build_panel.py       # assemble state x period panel, define treatment events -> data/processed
src/eda.py               # descriptive plots, treatment timeline
src/estimate_did.py      # pooled OLS, TWFE, event study
src/estimate_csa.py      # Callaway-Sant'Anna staggered DiD
src/placebo.py           # high-wage sector + fake-date falsification
src/consolidate.py       # merge estimates -> comparison_table.*, fig_summary.png, findings.md
src/build_dashboard.py   # comprehensive self-contained dashboard.html (all tables + figures)
```

## Reproducing the results

The pipeline is standalone and idempotent — each `src/` script can be run on its own, and
re-runs reuse the cached raw pulls in `data/raw/` rather than re-hitting FRED. Because the raw
data is not committed, **run `fetch_fred.py` first** (this is the only step that needs the FRED
key); every step after it is fully offline. From the project root, with the venv active:

```bash
python src/series_map.py         # (optional) --validate to re-check all 205 series IDs
python src/fetch_fred.py         # pull series -> data/raw   (REQUIRES FRED_API_KEY in .env)
python src/build_panel.py        # -> data/processed/panel.parquet + results/events_table.*
python src/eda.py                # -> results/fig_*.png descriptive figures
python src/estimate_did.py       # -> results/did_estimates.*, event_study.*, fig_event_study.png
python src/estimate_csa.py       # -> results/csa_*.*, fig_csa_event_study.png
python src/placebo.py            # -> results/placebo.*, fig_placebo_*.png, fig_robustness.png
python src/consolidate.py        # -> results/comparison_table.*, fig_summary.png, findings.md
python src/build_dashboard.py    # -> dashboard.html (open in any browser)
```

On Windows you can substitute the `py` launcher for `python`. Outputs land in `results/` and
`data/processed/` with the filenames referenced throughout `results/findings.md`. Then open
`dashboard.html` in a browser for the interactive results.

## Tests

`tests/` holds the regression suite (run with `pytest -q` from the project root):

- **`test_panel_integrity.py`** — the panel is a strictly balanced 51×64 grid (3,264 rows),
  no NA in model fields, `log_leih == log(leih)`, `leih_share ∈ [0,1]`, treatment dummies
  binary, `treated_post == treated & post`, `post` turns on exactly at each state's cohort,
  and the 31-treated / 20-control split matches the design.
- **`test_event_detection.py`** — `detect_events` registers a genuine above-floor increase,
  ignores the mechanical 2009→2010 federal step and any rise that stays at/below the $7.25
  floor, never fires on a decrease, and sizes events correctly; the committed
  `events_table.csv` (307 events, 31 states) is cross-checked against the panel cohorts.
- **`test_estimator_sanity.py`** — `fit_twfe` / `fit_pooled_ols` reproduce the published
  headline numbers (TWFE −0.0268, pooled OLS −0.0063), fixed effects shift and tighten the
  estimate as documented, and on synthetic staggered panels the TWFE estimator recovers a
  planted ±effect and returns an insignificant ~0 under the null.

The suite reads the committed artifacts and synthetic fixtures only — it does **not** require
network access or a FRED key. As of Day 9: **32 passed**.

## What's in this repo

```
src/         pipeline scripts (see Pipeline above)
tests/       pytest regression suite (32 tests, no network needed)
results/     all outputs: estimates, figures, findings.md, dashboard inputs
data/        raw/ and processed/ (empty on clone — regenerated by the pipeline)
dashboard.html   interactive results dashboard (open in a browser)
requirements.txt
```

Key outputs to look at after running (or in the committed `results/`):

- **`results/findings.md`** — the full written analysis and headline result.
- **`results/comparison_table.md`** — pooled OLS vs. TWFE vs. Callaway–Sant'Anna, side by side.
- **`results/event_study.md`** + `fig_event_study.png` / `fig_csa_event_study.png` — pre-trends and dynamic effects with CIs.
- **`results/placebo.md`** + `fig_robustness.png` — high-wage-sector and fake-date falsification checks.
- **`dashboard.html`** — self-contained interactive dashboard: Plotly charts built from the real data (hover for values), a light/dark toggle, every estimate, the full 307-event log, and all source figures embedded. Data is inline; Plotly loads from CDN, so it needs internet only to render the chart library.

## Data notes

Mixed source frequencies are reconciled in `build_panel.py`: treatment (`STTMINWG`) is **annual** ($/hr) and forward-filled to quarterly; outcome/normalizer (`LEIH`/`NA`) and the control (`UR`) are **monthly**, collapsed to quarterly means. Five `STTMINWG` treatment series don't exist on FRED — `AL`, `LA`, `MS`, `SC`, `TN` — because those states have no state minimum-wage statute; they remain in the panel as never-treated federal-floor controls (their `LEIH`/`NA`/`UR` series resolve normally). Run `python src/series_map.py --validate` to re-check all 205 series IDs against FRED.
