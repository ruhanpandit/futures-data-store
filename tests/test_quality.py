"""Tests for the quality module.

Synthetic tests run with generated fixtures.
Tests marked @has_real_data require normalized Parquet data.
"""


from futures_data_store.quality import run_quality_check

from .conftest import has_real_data

# ---------------------------------------------------------------------------
# Synthetic-data tests
# ---------------------------------------------------------------------------


def test_no_duplicates_synthetic(synthetic_data):
    """Synthetic data has zero duplicate timestamps."""
    report = run_quality_check("ES", data_dir=synthetic_data)
    assert report.duplicate_count == 0


def test_no_out_of_order_synthetic(synthetic_data):
    """Synthetic data (written in order) has zero out-of-order bars."""
    report = run_quality_check("ES", data_dir=synthetic_data)
    assert report.out_of_order_count == 0


def test_out_of_order_detected(out_of_order_data):
    """Out-of-order check must detect swapped rows in physical file order."""
    report = run_quality_check("ES", data_dir=out_of_order_data)
    assert report.out_of_order_count > 0, "Should detect at least one out-of-order bar"


def test_half_days_detected_synthetic(synthetic_data):
    """Quality check must detect the synthetic half day."""
    report = run_quality_check("ES", data_dir=synthetic_data)
    assert report.half_days == 1


def test_half_day_date_flagged_synthetic(synthetic_data):
    """2023-11-24 must appear in half_day_dates."""
    report = run_quality_check("ES", data_dir=synthetic_data)
    assert "2023-11-24" in report.half_day_dates


def test_roll_detected_synthetic(synthetic_data):
    """Synthetic data has a roll between 2023-10-03 (id=100) and 2023-10-04 (id=200)."""
    report = run_quality_check("ES", data_dir=synthetic_data)
    assert len(report.rolls) >= 1
    roll = report.rolls[0]
    assert roll["old_id"] == 100
    assert roll["new_id"] == 200


def test_full_days_synthetic(synthetic_data):
    """Synthetic data has exactly 2 full days."""
    report = run_quality_check("ES", data_dir=synthetic_data)
    assert report.full_days == 2


# ---------------------------------------------------------------------------
# Real-data tests
# ---------------------------------------------------------------------------


@has_real_data
def test_no_duplicates():
    """ES data must have zero duplicate timestamps."""
    report = run_quality_check("ES")
    assert report.duplicate_count == 0


@has_real_data
def test_no_out_of_order():
    """ES data must have zero out-of-order bars."""
    report = run_quality_check("ES")
    assert report.out_of_order_count == 0


@has_real_data
def test_half_days_detected():
    """Quality check must detect half days."""
    report = run_quality_check("ES")
    assert report.half_days > 0


@has_real_data
def test_half_day_thanksgiving_flagged():
    """2023-11-24 (Black Friday) must be in half_day_dates."""
    report = run_quality_check("ES")
    assert "2023-11-24" in report.half_day_dates


@has_real_data
def test_full_days_majority():
    """Most trading days should be full 390-bar days."""
    report = run_quality_check("ES")
    assert report.full_days > report.trading_days * 0.9


@has_real_data
def test_rolls_detected():
    """ES data must have quarterly contract rolls."""
    report = run_quality_check("ES")
    assert len(report.rolls) == 24, f"Expected 24 rolls (6 years * 4/year), got {len(report.rolls)}"
