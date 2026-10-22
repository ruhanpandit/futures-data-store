"""Tests for the quality module.

These tests require normalized Parquet data in data/processed/.
"""

from futures_data_store.quality import run_quality_check


def test_no_duplicates():
    """ES data must have zero duplicate timestamps."""
    report = run_quality_check("ES")
    assert report.duplicate_count == 0


def test_no_out_of_order():
    """ES data must have zero out-of-order bars."""
    report = run_quality_check("ES")
    assert report.out_of_order_count == 0


def test_half_days_detected():
    """Quality check must detect half days."""
    report = run_quality_check("ES")
    assert report.half_days > 0, "Should detect at least one half day"


def test_full_days_majority():
    """Most trading days should be full 390-bar days."""
    report = run_quality_check("ES")
    assert report.full_days > report.trading_days * 0.9, (
        "Full days should be > 90% of trading days"
    )
