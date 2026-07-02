# EDA Summary - Project #4 (Day 3)

Descriptive pass over `data/processed/panel.parquet` (51 jurisdictions x 64 quarters, 2010Q1-2025Q4). Figures in `results/`. Nothing here is causal - it sets up the DiD.

## Treatment structure

- **31 treated** jurisdictions (>=1 genuine state min-wage increase above the federal floor) vs **20 never-treated controls** (incl. the 5 no-statute states).
- **307 increase events** span 2010Q1 -> 2025Q1 (`fig_treatment_timeline.png`).
- Adoption is **staggered across 8 yearly cohorts**; the largest single cohort is **2011 (7 states)** (`fig_adoption_cohorts.png`). Staggered timing is exactly why a naive TWFE can be biased and why the Day 6 Callaway-Sant'Anna estimator is on the plan.
- By 2025Q4 the treated-state mean effective minimum wage is **$13.71** vs the **$7.25** federal floor that binds the controls (`fig_minwage_paths.png`) - clear policy variation to exploit.

## Raw outcome trends (treated vs control)

- In indexed terms (2010Q1 = 100), treated and control L&H employment track each other closely through the pre-2014 window: **mean absolute index gap = 0.24 points** (`fig_trends_treated_control.png`). That visual co-movement is the eyeball parallel-trends check; Day 5 tests it formally.
- The descriptive event study (within-state demeaned, recentred to k=-1) shows pre-event coefficients near zero (**mean |k in [-8,-2]| = 0.0128**) (`fig_raw_event_study.png`). Encouraging, but not a substitute for the regression version.
- The L&H share of nonfarm (`fig_leih_share_trends.png`) shows the **2020 COVID collapse** in both groups - a common shock the design must absorb via period fixed effects.

## Data-quality checks

- **Panel is balanced:** 3264 rows = expected 51 x 64 (3264). No quarters drop states (gap quarters = 0).
- **No missing cells** across leih / log_leih / nonfarm / leih_share / ur / min_wage_level (`fig_coverage_quality.png`).
- **Outlier scan:** 60 quarter-on-quarter Δlog moves exceed 4σ (σ = 0.0766). The largest swings are the 2020Q2 COVID drop and 2020Q3 rebound, not data errors - they are real and should be retained (period FE absorb them):
  - DC 2020Q2: Δlog = -0.920
  - NY 2020Q2: Δlog = -0.850
  - MA 2020Q2: Δlog = -0.799
  - HI 2020Q2: Δlog = -0.784
  - NJ 2020Q2: Δlog = -0.758
  - VT 2020Q2: Δlog = -0.754
  - RI 2020Q2: Δlog = -0.722
  - PA 2020Q2: Δlog = -0.709

## Caveats carried forward

- Min-wage events are dated to **Q1** (annual FRED series resolution); mid-year statutory changes can't be timed more precisely - a known limitation for event timing.
- COVID-2020 is a large common shock; pre-2020 windows may give cleaner parallel-trends reads. Worth a robustness cut on Day 7.
- 'Treated' here is *ever-treated*; many treated states raise the wage repeatedly, so the binary `post` collapses a dose. Day 6's group-time ATT handles staggered onset properly.

_Checkpoint (Day 3): EDA figures saved._
