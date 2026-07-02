"""
series_map.py - FRED series ID map for Project #4 (Minimum Wage & Low-Wage Employment DiD).

Builds the exact FRED series IDs for all 51 jurisdictions (50 states + DC) across the
four per-jurisdiction roles used in the difference-in-differences design, plus the single
national federal-minimum-wage series.

Roles (see project-plan.md):
    treatment   STTMINWG<XX>   State minimum wage rate            (the policy variable)
    outcome     <XX>LEIH       All Employees: Leisure & Hospitality (low-wage sector)
    normalizer  <XX>NA         All Employees: Total Nonfarm        (denominator / size control)
    control     <XX>UR         State unemployment rate
    flag        FEDMINNFRWG    Federal Minimum Hourly Wage, Nonfarm Workers (national, no <XX>)

<XX> is the two-letter USPS postal abbreviation, e.g. CA -> STTMINWGCA, CALEIH, CANA, CAUR.

This module is import-safe and side-effect free. The validation routine (validate_series_map)
performs live FRED lookups and is only invoked when the file is run as a script.

Conventions (project rules):
    * FRED_API_KEY is read from the project .env via python-dotenv; never hardcoded or printed.
    * If a series is missing/discontinued on FRED, it is logged and dropped WITH A NOTE.
      We never impute a substitute ID.
"""
from __future__ import annotations

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
RESULTS_DIR = PROJECT_ROOT / "results"

# ---------------------------------------------------------------------------
# 51 jurisdictions: 50 states + DC, USPS abbreviation -> full name
# ---------------------------------------------------------------------------
JURISDICTIONS: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

# Per-jurisdiction series-ID templates, keyed by role.
ROLE_TEMPLATES: dict[str, str] = {
    "treatment":  "STTMINWG{XX}",   # state minimum wage
    "outcome":    "{XX}LEIH",       # Leisure & Hospitality employment
    "normalizer": "{XX}NA",         # Total Nonfarm employment
    "control":    "{XX}UR",         # state unemployment rate
}

# National (jurisdiction-independent) series.
NATIONAL_SERIES: dict[str, str] = {
    "federal_min_wage": "FEDMINNFRWG",  # Federal Minimum Hourly Wage for Nonfarm Workers, US
}


# ---------------------------------------------------------------------------
# Map construction (deterministic, no network)
# ---------------------------------------------------------------------------
def build_series_map() -> dict[str, dict[str, str]]:
    """Return {jurisdiction_abbr: {role: series_id, ...}, "_national": {...}}.

    Pure string construction; no FRED calls. Stable, sorted by postal code.
    """
    smap: dict[str, dict[str, str]] = {}
    for xx in sorted(JURISDICTIONS):
        smap[xx] = {role: tmpl.format(XX=xx) for role, tmpl in ROLE_TEMPLATES.items()}
    smap["_national"] = dict(NATIONAL_SERIES)
    return smap


def all_series_ids() -> list[str]:
    """Flat, de-duplicated, sorted list of every FRED series ID in the map."""
    ids: set[str] = set()
    smap = build_series_map()
    for xx, roles in smap.items():
        if xx == "_national":
            ids.update(roles.values())
        else:
            ids.update(roles.values())
    return sorted(ids)


def series_index() -> list[dict[str, str]]:
    """Long-format index: one record per (jurisdiction, role, series_id)."""
    rows: list[dict[str, str]] = []
    smap = build_series_map()
    for xx in sorted(JURISDICTIONS):
        for role, sid in smap[xx].items():
            rows.append({
                "jurisdiction": xx,
                "name": JURISDICTIONS[xx],
                "role": role,
                "series_id": sid,
            })
    for role, sid in smap["_national"].items():
        rows.append({
            "jurisdiction": "US",
            "name": "United States",
            "role": role,
            "series_id": sid,
        })
    return rows


# ---------------------------------------------------------------------------
# Validation against FRED (network; only run as a script)
# ---------------------------------------------------------------------------
# Throttle/retry settings. FRED's documented limit is ~120 requests/minute; with 205 series
# a small inter-request sleep plus backoff on 429s keeps us comfortably under it.
REQUEST_SLEEP_S = 0.6          # ~100 req/min steady state
MAX_RETRIES = 5
BACKOFF_BASE_S = 2.0           # 2s, 4s, 8s, ... on "Too Many Requests"


def _load_fred():
    """Construct an authenticated Fred client from .env. Never prints the key."""
    from dotenv import load_dotenv
    from fredapi import Fred
    load_dotenv(ENV_PATH)
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise RuntimeError(f"FRED_API_KEY not found in {ENV_PATH}")
    return Fred(api_key=api_key)


def _is_rate_limited(err: str) -> bool:
    return "too many requests" in err.lower() or "rate limit" in err.lower()


def _is_does_not_exist(err: str | None) -> bool:
    """True only for FRED's genuine 'series does not exist' / bad-request-on-id responses."""
    if not err:
        return False
    e = err.lower()
    return "does not exist" in e or ("bad request" in e and "rate limit" not in e)


def _get_info_with_retry(fred, sid: str):
    """Return (info_dict, None) on success or (None, error_str) on failure.

    Retries with exponential backoff specifically on rate-limit responses so that
    transient 429s are not mistaken for missing series.
    """
    import time
    err = None
    for attempt in range(MAX_RETRIES):
        try:
            return fred.get_series_info(sid), None
        except Exception as exc:  # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            if _is_rate_limited(err) and attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_BASE_S * (2 ** attempt))
                continue
            return None, err
    return None, err


def validate_series_map(write_report: bool = True) -> dict:
    """Resolve every series ID on FRED and produce a validation report.

    For each ID we record whether FRED returns metadata (resolves=True), the title,
    frequency, units, observation span, and last-updated. IDs that fail to resolve are
    logged as missing/discontinued and flagged for dropping (NOT imputed).

    Returns a report dict and (optionally) writes results/series_validation.json and .md.
    Raises on a hard network/auth failure so the caller can STOP and write BLOCKERS.md.
    """
    import time

    fred = _load_fred()
    index = series_index()
    resolved: list[dict] = []
    missing: list[dict] = []      # genuinely does-not-exist on FRED -> drop (no imputation)
    transient: list[dict] = []    # rate-limit / network -> NOT a real miss; re-run to resolve

    for rec in index:
        sid = rec["series_id"]
        info, err = _get_info_with_retry(fred, sid)
        if info is not None:
            resolved.append({
                **rec,
                "resolves": True,
                "title": str(info.get("title", "")),
                "frequency": str(info.get("frequency_short", info.get("frequency", ""))),
                "units": str(info.get("units_short", info.get("units", ""))),
                "obs_start": str(info.get("observation_start", "")),
                "obs_end": str(info.get("observation_end", "")),
                "last_updated": str(info.get("last_updated", "")),
            })
        elif _is_does_not_exist(err):
            missing.append({**rec, "resolves": False, "error": err})
        else:
            transient.append({**rec, "resolves": False, "error": err})
        time.sleep(REQUEST_SLEEP_S)  # stay under FRED's ~120 req/min rate limit

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "n_total": len(index),
        "n_resolved": len(resolved),
        "n_missing": len(missing),
        "n_transient": len(transient),
        "resolved": resolved,
        "missing": missing,
        "transient": transient,
    }

    if write_report:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (RESULTS_DIR / "series_validation.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        _write_markdown_report(report)

    return report


def _write_markdown_report(report: dict) -> None:
    n_transient = report.get("n_transient", 0)
    lines = [
        "# FRED Series Validation Report - Project #4",
        "",
        f"_Generated: {report['generated_utc']}_",
        "",
        f"- Total series checked: **{report['n_total']}**",
        f"- Resolved on FRED: **{report['n_resolved']}**",
        f"- Missing / discontinued (dropped, not imputed): **{report['n_missing']}**",
        f"- Transient errors (rate-limit/network - NOT dropped, re-run to resolve): **{n_transient}**",
        "",
    ]
    if report["missing"]:
        lines += ["## Missing / discontinued series (dropped, not imputed)", "",
                  "| Jurisdiction | Role | Series ID | Error |", "|---|---|---|---|"]
        for m in report["missing"]:
            lines.append(f"| {m['jurisdiction']} | {m['role']} | `{m['series_id']}` | {m['error']} |")
        lines.append("")
    if report.get("transient"):
        lines += ["## Transient errors (re-run `--validate` to resolve; NOT treated as missing)", "",
                  "| Jurisdiction | Role | Series ID | Error |", "|---|---|---|---|"]
        for t in report["transient"]:
            lines.append(f"| {t['jurisdiction']} | {t['role']} | `{t['series_id']}` | {t['error']} |")
        lines.append("")
    lines += ["## Resolved series", "",
              "| Jurisdiction | Role | Series ID | Freq | Units | Span |", "|---|---|---|---|---|---|"]
    for r in report["resolved"]:
        span = f"{r['obs_start']} -> {r['obs_end']}"
        lines.append(f"| {r['jurisdiction']} | {r['role']} | `{r['series_id']}` | "
                     f"{r['frequency']} | {r['units']} | {span} |")
    (RESULTS_DIR / "series_validation.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    smap = build_series_map()
    ids = all_series_ids()
    print(f"Jurisdictions: {len(JURISDICTIONS)} (50 states + DC)")
    print(f"Per-jurisdiction roles: {list(ROLE_TEMPLATES)}")
    print(f"National series: {list(NATIONAL_SERIES.values())}")
    print(f"Total unique series IDs: {len(ids)}  "
          f"(= {len(JURISDICTIONS)} x {len(ROLE_TEMPLATES)} + {len(NATIONAL_SERIES)})")
    print("Sample (CA):", smap["CA"])

    if "--validate" in sys.argv:
        print("\nValidating against FRED (throttled ~100 req/min, with retry on rate limit)...")
        try:
            rep = validate_series_map(write_report=True)
            print(f"\nValidation: {rep['n_resolved']}/{rep['n_total']} resolved, "
                  f"{rep['n_missing']} missing, {rep.get('n_transient', 0)} transient. "
                  f"Report -> results/series_validation.md")
            if rep['n_missing']:
                print("Genuinely missing (dropped, not imputed): "
                      + ", ".join(m['series_id'] for m in rep['missing']))
            if rep.get('n_transient'):
                print("Transient errors remain (re-run to resolve): "
                      + ", ".join(t['series_id'] for t in rep['transient']))
        except Exception as exc:  # noqa: BLE001
            print(f"\nVALIDATION FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            sys.exit(2)
