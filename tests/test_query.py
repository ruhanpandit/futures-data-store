"""Tests for the query module.

Synthetic tests (no marker) run with generated Parquet fixtures.
Tests marked @has_real_data require `python -m futures_data_store.normalize` first.
"""

import numpy as np
import pandas as pd
import pytest

from futures_data_store.query import get_bars, to_arrays

from .conftest import has_real_data

# ---------------------------------------------------------------------------
# Synthetic-data tests (always run)
# ---------------------------------------------------------------------------


def test_rth_bar_count_synthetic(synthetic_data):
    """A full synthetic day returns exactly 390 RTH bars."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth", data_dir=synthetic_data)
    assert len(df) == 390


def test_half_day_synthetic(synthetic_data):
    """A synthetic half day returns 225 bars."""
    df = get_bars("ES", "2023-11-24", "2023-11-24", session="rth", data_dir=synthetic_data)
    assert len(df) == 225


def test_bar_columns_synthetic(synthetic_data):
    """DataFrame must have the expected columns."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth", data_dir=synthetic_data)
    expected = ["ts", "open", "high", "low", "close", "volume", "instrument_id"]
    assert list(df.columns) == expected


def test_tz_determinism_synthetic(synthetic_data):
    """Timestamps must be UTC regardless of machine timezone."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth", data_dir=synthetic_data)
    assert str(df["ts"].dt.tz) == "UTC"
    # First RTH bar: 09:30 ET = 13:30 UTC
    assert df["ts"].iloc[0].hour == 13
    assert df["ts"].iloc[0].minute == 30


def test_globex_includes_rth_synthetic(synthetic_data):
    """Globex session must return at least as many bars as RTH."""
    rth = get_bars("ES", "2023-10-03", "2023-10-03", session="rth", data_dir=synthetic_data)
    globex = get_bars("ES", "2023-10-03", "2023-10-03", session="globex", data_dir=synthetic_data)
    assert len(globex) >= len(rth)


def test_rth_timestamps_in_range_synthetic(synthetic_data):
    """All RTH bars must fall within 09:30-16:00 ET."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth", data_dir=synthetic_data)
    ts_et = df["ts"].dt.tz_convert("America/New_York")
    times = ts_et.dt.time
    assert times.min() >= pd.Timestamp("09:30").time()
    assert times.max() <= pd.Timestamp("15:59").time()


def test_invalid_session_raises():
    """Passing an invalid session name must raise ValueError."""
    with pytest.raises(ValueError, match="session must be"):
        get_bars("ES", "2023-10-03", "2023-10-03", session="invalid")


def test_invalid_symbol_raises():
    """Passing an unknown symbol must raise ValueError."""
    with pytest.raises(ValueError, match="Unknown symbol"):
        get_bars("ZZ", "2023-10-03", "2023-10-03")


def test_to_arrays_dtypes_and_contiguity_synthetic(synthetic_data):
    """All arrays must have correct dtypes and be C-contiguous."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth", data_dir=synthetic_data)
    arrays = to_arrays(df)

    expected_dtypes = {
        "ts_ns": np.int64,
        "open": np.float64,
        "high": np.float64,
        "low": np.float64,
        "close": np.float64,
        "volume": np.float64,
        "instrument_id": np.int64,
        "session_date": np.int32,
    }

    assert set(arrays.keys()) == set(expected_dtypes.keys())
    for name, expected_dtype in expected_dtypes.items():
        arr = arrays[name]
        assert arr.dtype == expected_dtype, f"{name}: expected {expected_dtype}, got {arr.dtype}"
        assert arr.flags["C_CONTIGUOUS"], f"{name} not C-contiguous"
        assert arr.shape == (390,), f"{name} shape {arr.shape} != (390,)"


def test_to_arrays_session_date_synthetic(synthetic_data):
    """RTH bars should have session_date matching the calendar date."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth", data_dir=synthetic_data)
    arrays = to_arrays(df)
    assert all(arrays["session_date"] == 20231003)


def test_to_arrays_values_match_synthetic(synthetic_data):
    """Array values must match the DataFrame."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth", data_dir=synthetic_data)
    arrays = to_arrays(df)
    np.testing.assert_array_equal(arrays["close"], df["close"].to_numpy())


def test_nq_synthetic(synthetic_data):
    """NQ should return bars from synthetic data."""
    df = get_bars("NQ", "2023-10-03", "2023-10-03", session="rth", data_dir=synthetic_data)
    assert len(df) == 390


# ---------------------------------------------------------------------------
# Real-data tests (skipped when data is absent)
# ---------------------------------------------------------------------------


@has_real_data
def test_rth_bar_count():
    """A normal Tuesday (2023-10-03) must return exactly 390 RTH bars."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth")
    assert len(df) == 390


@has_real_data
def test_half_day_thanksgiving():
    """The day after Thanksgiving 2023 (2023-11-24) is a half day (225 bars)."""
    df = get_bars("ES", "2023-11-24", "2023-11-24", session="rth")
    assert len(df) == 225


@has_real_data
def test_globex_more_than_rth():
    """Globex session must return more bars than RTH for the same day."""
    rth = get_bars("ES", "2023-10-03", "2023-10-03", session="rth")
    globex = get_bars("ES", "2023-10-03", "2023-10-03", session="globex")
    assert len(globex) > len(rth)


@has_real_data
def test_to_arrays_ts_ns_known_value():
    """First RTH bar on 2023-10-03: 13:30 UTC = 1696339800000000000 ns."""
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth")
    arrays = to_arrays(df)
    assert arrays["ts_ns"][0] == 1696339800_000_000_000


@has_real_data
def test_nq_rth_bar_count():
    """NQ should also return 390 RTH bars on a normal day."""
    df = get_bars("NQ", "2023-10-03", "2023-10-03", session="rth")
    assert len(df) == 390
