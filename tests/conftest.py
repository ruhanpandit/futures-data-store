"""Shared test fixtures.

Provides synthetic Parquet data in tmp_path so unit tests can run
without real Databento data on disk.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

# Skip marker for tests that need real downloaded data
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
has_real_data = pytest.mark.skipif(
    not DATA_DIR.exists() or not any(DATA_DIR.glob("**/*.parquet")),
    reason="Real Parquet data not available (run normalize first)",
)


def _make_rth_bars(
    date: str,
    instrument_id: int = 100,
    n_bars: int = 390,
    base_price: float = 4500.0,
) -> pd.DataFrame:
    """Generate synthetic 1-min RTH bars for a single day.

    Bars start at 09:30 ET (converted to UTC) and run for n_bars minutes.
    Prices are a simple random walk from base_price.
    """
    # Build timestamps in ET, then convert to UTC for storage
    start_et = pd.Timestamp(f"{date} 09:30:00", tz="America/New_York")
    ts_et = pd.date_range(start_et, periods=n_bars, freq="min")
    ts_utc = ts_et.tz_convert("UTC")

    rng = np.random.default_rng(seed=42)
    changes = rng.normal(0, 1.0, size=n_bars)
    close = base_price + np.cumsum(changes)
    open_ = np.roll(close, 1)
    open_[0] = base_price
    high = np.maximum(open_, close) + rng.uniform(0, 2, size=n_bars)
    low = np.minimum(open_, close) - rng.uniform(0, 2, size=n_bars)
    volume = rng.integers(100, 10000, size=n_bars).astype(np.uint64)

    return pd.DataFrame({
        "ts": ts_utc,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "instrument_id": np.full(n_bars, instrument_id, dtype=np.uint32),
    })


def write_synthetic_parquet(
    data_dir: Path,
    symbol: str,
    year: int,
    df: pd.DataFrame,
) -> Path:
    """Write a DataFrame to the expected Hive-partitioned layout."""
    out_dir = data_dir / symbol / f"year={year}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "bars.parquet"
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, out_path)
    return out_path


@pytest.fixture
def synthetic_data(tmp_path: Path) -> Path:
    """Create a minimal synthetic dataset in tmp_path.

    Layout:
        tmp_path/processed/ES/year=2023/bars.parquet  (3 days)
        tmp_path/processed/NQ/year=2023/bars.parquet  (1 day)

    Days:
        2023-10-03 (Tuesday, full day, 390 bars)
        2023-10-04 (Wednesday, full day, 390 bars, different instrument_id)
        2023-11-24 (Black Friday, half day, 225 bars)
    """
    processed = tmp_path / "processed"

    # ES: two full days + one half day
    full_day_1 = _make_rth_bars("2023-10-03", instrument_id=100, n_bars=390)
    full_day_2 = _make_rth_bars("2023-10-04", instrument_id=200, n_bars=390)
    half_day = _make_rth_bars("2023-11-24", instrument_id=200, n_bars=225)

    es_df = pd.concat([full_day_1, full_day_2, half_day], ignore_index=True)
    write_synthetic_parquet(processed, "ES", 2023, es_df)

    # NQ: one full day
    nq_df = _make_rth_bars("2023-10-03", instrument_id=300, n_bars=390, base_price=15000.0)
    write_synthetic_parquet(processed, "NQ", 2023, nq_df)

    return tmp_path


@pytest.fixture
def out_of_order_data(tmp_path: Path) -> Path:
    """Create synthetic data with two rows swapped to test out-of-order detection."""
    processed = tmp_path / "processed"

    df = _make_rth_bars("2023-10-03", instrument_id=100, n_bars=390)
    # Swap rows 5 and 6 to create an out-of-order pair
    df.iloc[5], df.iloc[6] = df.iloc[6].copy(), df.iloc[5].copy()

    write_synthetic_parquet(processed, "ES", 2023, df)
    return tmp_path
