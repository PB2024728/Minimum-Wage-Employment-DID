"""
Shared pytest fixtures for Project #4 (Minimum Wage & Low-Wage Employment).

Makes `src/` importable and loads the processed panel + the detected-events table once
per test session. Tests are read-only over the committed artifacts in data/processed/ and
results/; they never re-hit FRED.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"

# make the standalone src/ modules importable as top-level names
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(scope="session")
def panel() -> pd.DataFrame:
    """The analysis panel (parquet preferred, csv fallback)."""
    pq = PROCESSED / "panel.parquet"
    csv = PROCESSED / "panel.csv"
    if pq.exists():
        try:
            return pd.read_parquet(pq)
        except Exception:
            pass
    if csv.exists():
        return pd.read_csv(csv)
    pytest.skip("processed panel not found; run src/build_panel.py first")


@pytest.fixture(scope="session")
def events() -> pd.DataFrame:
    """The detected minimum-wage increase events table."""
    csv = RESULTS / "events_table.csv"
    if not csv.exists():
        pytest.skip("results/events_table.csv not found; run src/build_panel.py first")
    return pd.read_csv(csv)
