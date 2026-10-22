"""Tests for the query module.

These tests require normalized Parquet data in data/processed/.
Run `python -m futures_data_store.normalize` first.
"""

import numpy as np
import pandas as pd
import pytest

from futures_data_store.query import get_bars, to_arrays


# -- Done-when tests --------------------------------------------------------

def test_rth_bar_count():
    """A normal Tuesday (2023-10-03) must return exactly 390 RTH bars."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth")
    assert len(df) == 390, f"Expected 390 RTH bars, got {len(df)}"


def test_half_day_thanksgiving():
    """The day after Thanksgiving 2023 (2023-11-24) is a half day.

    CME early close at 13:15 ET = 225 bars, not 390.
    """
    df = get_bars("ES", "2023-11-24", "2023-11-24", session="rth")
    assert len(df) == 225, f"Expected 225 half-day bars, got {len(df)}"
    assert len(df) < 390, "Half day should have fewer bars than a full day"


# -- Column and type checks -------------------------------------------------

def test_bar_columns():
    """DataFrame must have the expected columns."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth")
    expected = ["ts", "open", "high", "low", "close", "volume"]
    assert list(df.columns) == expected


def test_price_types():
    """OHLCV columns must be numeric."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth")
    for col in ("open", "high", "low", "close"):
        assert df[col].dtype == np.float64, f"{col} should be float64"


# -- Session filtering -------------------------------------------------------

def test_globex_more_than_rth():
    """Globex session must return more bars than RTH for the same day."""
    rth = get_bars("ES", "2023-10-03", "2023-10-03", session="rth")
    globex = get_bars("ES", "2023-10-03", "2023-10-03", session="globex")
    assert len(globex) > len(rth), (
        f"Globex ({len(globex)}) should have more bars than RTH ({len(rth)})"
    )


def test_rth_timestamps_in_range():
    """All RTH bars must fall within 09:30-16:00 ET."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth")
    ts_et = df["ts"].dt.tz_convert("America/New_York")
    times = ts_et.dt.time

    earliest = pd.Timestamp("09:30").time()
    latest = pd.Timestamp("15:59").time()  # last bar is at 15:59

    assert times.min() >= earliest, f"Earliest bar {times.min()} before 09:30"
    assert times.max() <= latest, f"Latest bar {times.max()} after 15:59"


def test_invalid_session_raises():
    """Passing an invalid session name must raise ValueError."""
    with pytest.raises(ValueError, match="session must be"):
        get_bars("ES", "2023-10-03", "2023-10-03", session="invalid")


# -- to_arrays ---------------------------------------------------------------

def test_to_arrays_contiguous():
    """NumPy arrays must be float64 and C-contiguous for C++ engine."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth")
    arrays = to_arrays(df)

    assert set(arrays.keys()) == {"open", "high", "low", "close", "volume"}

    for name, arr in arrays.items():
        assert arr.dtype == np.float64, f"{name} should be float64"
        assert arr.flags["C_CONTIGUOUS"], f"{name} should be C-contiguous"
        assert arr.shape == (390,), f"{name} shape should be (390,)"


def test_to_arrays_values_match():
    """Array values must match the DataFrame."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth")
    arrays = to_arrays(df)

    np.testing.assert_array_equal(arrays["close"], df["close"].to_numpy())


# -- NQ symbol ---------------------------------------------------------------

def test_nq_rth_bar_count():
    """NQ should also return 390 RTH bars on a normal day."""
    df = get_bars("NQ", "2023-10-03", "2023-10-03", session="rth")
    assert len(df) == 390, f"Expected 390 NQ RTH bars, got {len(df)}"
