"""
build_panel.py - Assemble the state x quarter DiD panel and detect minimum-wage events.

Reads the cached raw FRED CSVs (data/raw/, produced by fetch_fred.py) and builds a balanced
state x quarter panel over 2010Q1-2025Q4 for the 51 jurisdictions (50 states + DC):

    * Monthly series (LEIH, NA, UR, FEDMINNFRWG) -> collapsed to quarterly means.
    * Annual state minimum wage (STTMINWG<XX>) -> forward-filled to quarters within each year.
    * log_leih = log(quarterly-mean Leisure & Hospitality employment).
    * leih_share = LEIH / total nonfarm (secondary outcome).
    * min_wage_level (state statutory; federal floor for the 5 no-statute states),
      fed_min, min_wage_gap (state - federal), effective_min_wage = max(state, federal).

Minimum-wage INCREASE EVENT detection
-------------------------------------
The annual treatment series mechanically reflects the federal floor. Within 2010-2025 the
federal minimum is flat at $7.25, but a federal-floor state's annual series still shows the
2009->2010 step from the $6.55->$7.25 federal hike. That is NOT a state policy action. So an
event is recorded only when, in year y (2010..2025):

    state_mw[y] > state_mw[y-1] + EPS          (the state wage rose), AND
    state_mw[y] > fed[y] + EPS                 (the new level is a genuine state floor
                                                above the binding federal minimum)

This excludes (a) the 5 no-statute states (no STTMINWG series at all), and (b) states whose
series merely tracks the federal floor (e.g. TX flat at $7.25). Each event is dated to Q1 of
year y (the annual series is the finest resolution available; mid-year changes can't be timed
more precisely - a documented limitation). Event size = (new - old) / old.

Treatment encoding (for pooled OLS / TWFE / event study / Callaway-Sant'Anna)
    treated        1 if the state has >=1 qualifying event in-window (ever-treated)
    first_treat    earliest event quarter (the cohort), as a Period
    cohort         'YYYYQq' label of first_treat ('' for never-treated)
    cohort_year    integer year of first treatment (<NA> for never-treated)
    g_csa          CSA group var: first-treatment quarter ordinal (0 = never-treated)
    post           1 if treated and quarter >= first_treat
    treated_post   treated * post  (the DiD treatment dummy)
    event_time     quarter_ord - first_treat_ord  (<NA> for never-treated)

Outputs
-------
data/processed/panel.parquet     the analysis panel (one row per state x quarter)
data/processed/panel.csv         same, CSV convenience copy
results/events_table.csv         one row per detected min-wage increase event
results/events_table.md          printed events table + per-cohort summary
results/panel_summary.md         panel shape / coverage / treatment counts

Project rules honoured: Python only; cached raw reused; missing series dropped (never imputed);
standalone + idempotent.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from series_map import build_series_map, JURISDICTIONS, PROJECT_ROOT

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RESULTS_DIR = PROJECT_ROOT / "results"

# Panel window
START = pd.Period("2010Q1", freq="Q")
END = pd.Period("2025Q4", freq="Q")
EPS = 1e-6  # tolerance for "strictly greater" comparisons on dollar values

NO_STATUTE = {"AL", "LA", "MS", "SC", "TN"}  # default to federal floor (confirmed Day 1)


# ---------------------------------------------------------------------------
# Raw IO helpers
# ---------------------------------------------------------------------------
def _load_raw(sid: str) -> pd.Series | None:
    """Load a cached raw series as a date-indexed float Series, or None if absent."""
    path = RAW_DIR / f"{sid}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["date"])
    return pd.Series(df["value"].to_numpy(dtype=float),
                     index=pd.DatetimeIndex(df["date"]), name=sid).sort_index()


def _monthly_to_quarterly_mean(s: pd.Series) -> pd.Series:
    """Collapse a monthly (or higher-freq) series to quarterly means, indexed by Period[Q]."""
    q = s.copy()
    q.index = q.index.to_period("Q")
    return q.groupby(level=0).mean()


def _annual_to_quarterly_ffill(s: pd.Series) -> pd.Series:
    """Map an annual series to all quarters of each year (value held across the year)."""
    by_year = s.copy()
    by_year.index = by_year.index.year
    by_year = by_year.groupby(level=0).last()  # one value per calendar year
    quarters = pd.period_range(START, END, freq="Q")
    vals = pd.Series(index=quarters, dtype=float)
    for q in quarters:
        y = q.year
        if y in by_year.index:
            vals[q] = by_year[y]
    # forward/back fill across the window for years the annual series doesn't cover
    # (e.g. GA/WY series end 2023 -> hold last; series starting later -> back-fill earliest)
    vals = vals.ffill().bfill()
    return vals


# ---------------------------------------------------------------------------
# Event detection
# ---------------------------------------------------------------------------
def detect_events(state_mw_annual: pd.Series, fed_annual: pd.Series, xx: str) -> list[dict]:
    """Return list of qualifying state min-wage increase events for one state.

    state_mw_annual / fed_annual : year-indexed (int) annual dollar values.
    """
    events = []
    years = [y for y in range(START.year, END.year + 1)]
    for y in years:
        if y not in state_mw_annual.index or (y - 1) not in state_mw_annual.index:
            continue
        cur, prev = state_mw_annual[y], state_mw_annual[y - 1]
        fed_y = fed_annual.get(y, np.nan)
        if pd.isna(cur) or pd.isna(prev) or pd.isna(fed_y):
            continue
        rose = cur > prev + EPS
        above_federal = cur > fed_y + EPS
        if rose and above_federal:
            events.append({
                "jurisdiction": xx,
                "name": JURISDICTIONS[xx],
                "event_year": y,
                "event_quarter": f"{y}Q1",
                "prev_wage": round(float(prev), 4),
                "new_wage": round(float(cur), 4),
                "increase_abs": round(float(cur - prev), 4),
                "increase_pct": round(float((cur - prev) / prev * 100.0), 2),
                "fed_floor": round(float(fed_y), 4),
            })
    return events


# ---------------------------------------------------------------------------
# Panel assembly
# ---------------------------------------------------------------------------
def build() -> dict:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    smap = build_series_map()
    quarters = pd.period_range(START, END, freq="Q")
    qord = {q: i for i, q in enumerate(quarters)}  # 0..63

    # Federal minimum wage: monthly -> quarterly mean, and an annual (year->value) view.
    fed_q = _monthly_to_quarterly_mean(_load_raw("FEDMINNFRWG")).reindex(quarters).ffill().bfill()
    fed_annual_src = _load_raw("FEDMINNFRWG")
    fed_annual = fed_annual_src.copy()
    fed_annual.index = fed_annual.index.year
    fed_annual = fed_annual.groupby(level=0).mean()

    # --- pass 1: detect events for every state, set treatment cohorts ---
    all_events: list[dict] = []
    first_treat: dict[str, pd.Period | None] = {}
    state_mw_q: dict[str, pd.Series] = {}

    for xx in sorted(JURISDICTIONS):
        treat_sid = smap[xx]["treatment"]
        s_mw = _load_raw(treat_sid)
        if s_mw is None:
            # no-statute state: effective state floor = federal
            state_mw_q[xx] = fed_q.copy()
            first_treat[xx] = None
            continue

        # quarterly forward-filled state min wage
        state_mw_q[xx] = _annual_to_quarterly_ffill(s_mw).reindex(quarters)

        # annual (year->value) view for event detection
        ann = s_mw.copy()
        ann.index = ann.index.year
        ann = ann.groupby(level=0).last()

        evs = detect_events(ann, fed_annual, xx)
        all_events.extend(evs)
        first_treat[xx] = pd.Period(evs[0]["event_quarter"], freq="Q") if evs else None

    # --- pass 2: assemble the long panel ---
    rows = []
    for xx in sorted(JURISDICTIONS):
        leih = _monthly_to_quarterly_mean(_load_raw(smap[xx]["outcome"])).reindex(quarters)
        na = _monthly_to_quarterly_mean(_load_raw(smap[xx]["normalizer"])).reindex(quarters)
        ur = _monthly_to_quarterly_mean(_load_raw(smap[xx]["control"])).reindex(quarters)
        mw = state_mw_q[xx].reindex(quarters)

        ft = first_treat[xx]
        treated = int(ft is not None)
        ft_ord = qord[ft] if ft is not None else None

        for q in quarters:
            qo = qord[q]
            post = int(treated and ft_ord is not None and qo >= ft_ord)
            event_time = (qo - ft_ord) if (treated and ft_ord is not None) else pd.NA
            leih_v = leih.get(q, np.nan)
            na_v = na.get(q, np.nan)
            mw_v = mw.get(q, np.nan)
            fed_v = fed_q.get(q, np.nan)
            rows.append({
                "jurisdiction": xx,
                "name": JURISDICTIONS[xx],
                "quarter": str(q),
                "year": q.year,
                "q": q.quarter,
                "quarter_ord": qo,
                "leih": leih_v,
                "log_leih": np.log(leih_v) if pd.notna(leih_v) and leih_v > 0 else np.nan,
                "nonfarm": na_v,
                "leih_share": (leih_v / na_v) if (pd.notna(leih_v) and pd.notna(na_v) and na_v) else np.nan,
                "ur": ur.get(q, np.nan),
                "min_wage_level": mw_v,
                "fed_min": fed_v,
                "min_wage_gap": (mw_v - fed_v) if (pd.notna(mw_v) and pd.notna(fed_v)) else np.nan,
                "effective_min_wage": (max(mw_v, fed_v) if (pd.notna(mw_v) and pd.notna(fed_v)) else np.nan),
                "treated": treated,
                "post": post,
                "treated_post": int(treated and post),
                "event_time": event_time,
                "first_treat": str(ft) if ft is not None else "",
                "cohort": str(ft) if ft is not None else "",
                "cohort_year": (ft.year if ft is not None else pd.NA),
                # CSA group var: 1-based first-treat quarter ordinal; 0 = never-treated
                "g_csa": (ft_ord + 1) if (treated and ft_ord is not None) else 0,
                "no_statute_state": int(xx in NO_STATUTE),
            })

    panel = pd.DataFrame(rows)
    # tidy dtypes
    panel["cohort_year"] = panel["cohort_year"].astype("Int64")
    panel["event_time"] = panel["event_time"].astype("Int64")

    panel.to_parquet(PROCESSED_DIR / "panel.parquet", index=False)
    panel.to_csv(PROCESSED_DIR / "panel.csv", index=False)

    events_df = pd.DataFrame(all_events).sort_values(
        ["event_year", "jurisdiction"]).reset_index(drop=True) if all_events else pd.DataFrame()
    if not events_df.empty:
        events_df.to_csv(RESULTS_DIR / "events_table.csv", index=False)

    _write_event_report(events_df, first_treat)
    _write_panel_summary(panel, events_df, first_treat)

    return {
        "panel_rows": len(panel),
        "n_jurisdictions": panel["jurisdiction"].nunique(),
        "n_quarters": panel["quarter"].nunique(),
        "n_events": len(events_df),
        "n_treated_states": sum(1 for v in first_treat.values() if v is not None),
        "n_never_treated": sum(1 for v in first_treat.values() if v is None),
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def _write_event_report(events_df: pd.DataFrame, first_treat: dict) -> None:
    lines = ["# Minimum-Wage Increase Events - Project #4 (Day 2)", ""]
    if events_df.empty:
        lines.append("_No qualifying events detected._")
        (RESULTS_DIR / "events_table.md").write_text("\n".join(lines), encoding="utf-8")
        return

    n_states = events_df["jurisdiction"].nunique()
    lines += [
        f"- Total qualifying increase events: **{len(events_df)}**",
        f"- Distinct treated states: **{n_states}**",
        f"- Event-year span: **{int(events_df['event_year'].min())}-{int(events_df['event_year'].max())}**",
        f"- Median increase size: **{events_df['increase_pct'].median():.1f}%**",
        "",
        "An event = a state minimum-wage increase whose new level sits above the binding federal "
        "floor ($7.25 throughout 2010-2025). Federal-floor tracking and the 5 no-statute states "
        "(AL, LA, MS, SC, TN) are excluded. Events are dated to Q1 (annual series resolution).",
        "",
        "## All events",
        "",
        "| State | Event Qtr | Prev $ | New $ | Δ$ | Δ% | Fed $ |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, r in events_df.iterrows():
        lines.append(
            f"| {r['jurisdiction']} | {r['event_quarter']} | {r['prev_wage']:.2f} | "
            f"{r['new_wage']:.2f} | {r['increase_abs']:.2f} | {r['increase_pct']:.1f}% | "
            f"{r['fed_floor']:.2f} |")

    # cohort summary (first-treatment quarter)
    coh = {}
    for xx, ft in first_treat.items():
        if ft is not None:
            coh.setdefault(str(ft), []).append(xx)
    lines += ["", "## Treatment cohorts (first-treatment quarter)", "",
              "| Cohort | # States | States |", "|---|---|---|"]
    for c in sorted(coh):
        st = ", ".join(sorted(coh[c]))
        lines.append(f"| {c} | {len(coh[c])} | {st} |")
    never = sorted([xx for xx, ft in first_treat.items() if ft is None])
    lines += ["", f"**Never-treated controls ({len(never)}):** " + ", ".join(never), ""]

    (RESULTS_DIR / "events_table.md").write_text("\n".join(lines), encoding="utf-8")


def _write_panel_summary(panel: pd.DataFrame, events_df: pd.DataFrame, first_treat: dict) -> None:
    n_treated = sum(1 for v in first_treat.values() if v is not None)
    n_never = sum(1 for v in first_treat.values() if v is None)
    miss_leih = int(panel["leih"].isna().sum())
    miss_mw = int(panel["min_wage_level"].isna().sum())
    lines = [
        "# Panel Summary - Project #4 (Day 2)", "",
        f"- Rows: **{len(panel)}**  (= {panel['jurisdiction'].nunique()} jurisdictions x "
        f"{panel['quarter'].nunique()} quarters)",
        f"- Window: **{panel['quarter'].min()} -> {panel['quarter'].max()}**",
        f"- Treated states (>=1 in-window event): **{n_treated}**",
        f"- Never-treated controls: **{n_never}** (incl. 5 no-statute states)",
        f"- Total increase events: **{len(events_df)}**",
        f"- Missing log_leih cells: **{miss_leih}** | missing min_wage cells: **{miss_mw}**",
        "",
        "## Columns",
        "",
        ", ".join(f"`{c}`" for c in panel.columns),
        "",
    ]
    (RESULTS_DIR / "panel_summary.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    info = build()
    print("Panel built:")
    for k, v in info.items():
        print(f"  {k}: {v}")
    print(f"\nSaved: data/processed/panel.parquet ({info['panel_rows']} rows)")
    print("Saved: results/events_table.csv, results/events_table.md, results/panel_summary.md")
