"""Data-quality checks for normalized Parquet bars.

Checks:
    1. Duplicate timestamps
    2. Out-of-order bars
    3. RTH gap detection (missing minutes during market hours)
    4. Half-day detection (days with fewer than 390 RTH bars)

Usage:
    python -m futures_data_store.quality
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

# Known CME early-close days (13:00 ET close instead of 16:00).
# Format: (month, day). When these fall on a weekend, the early close
# shifts to the prior Friday, but we detect by bar count, not date matching.
KNOWN_HALF_DAYS_DESCRIPTION = {
    "black_friday": "Day after Thanksgiving",
    "christmas_eve": "Dec 24 (or prior Friday)",
    "independence_day_eve": "Jul 3 (or prior Friday)",
}

# CME has two types of early close for equity index futures:
#   13:00 ET = 210 bars (federal holidays: MLK, Presidents Day, etc.)
#   13:15 ET = 225 bars (day before: Jul 4, Thanksgiving, Christmas)
FULL_DAY_BARS = 390
HALF_DAY_BARS = {210, 225}


@dataclass
class QualityReport:
    """Results of running quality checks on a symbol's data."""

    symbol: str
    total_rows: int = 0
    duplicate_count: int = 0
    out_of_order_count: int = 0
    trading_days: int = 0
    full_days: int = 0
    half_days: int = 0
    anomalous_days: list[dict] = field(default_factory=list)
    rth_gaps: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"=== Quality Report: {self.symbol} ===",
            f"Total rows: {self.total_rows:,}",
            f"Duplicates: {self.duplicate_count}",
            f"Out-of-order: {self.out_of_order_count}",
            f"Trading days: {self.trading_days}",
            f"  Full days (390 bars): {self.full_days}",
            f"  Half days (210/225 bars): {self.half_days}",
            f"  Anomalous days: {len(self.anomalous_days)}",
        ]
        if self.anomalous_days:
            lines.append("  Anomalous day details:")
            for d in self.anomalous_days[:20]:
                lines.append(f"    {d['date']} - {d['bar_count']} bars")
        if self.rth_gaps:
            lines.append(f"RTH gaps (missing minutes): {len(self.rth_gaps)}")
            for g in self.rth_gaps[:20]:
                lines.append(f"    {g['date']} {g['after']} - gap of {g['gap_minutes']} min")
        return "\n".join(lines)


def _query_bars(symbol: str, data_dir: Path) -> pd.DataFrame:
    """Load all bars for a symbol with ET timestamp."""
    parquet_glob = str(data_dir / symbol / "**" / "*.parquet")
    query = f"""
        SELECT
            ts,
            timezone('America/New_York', ts) AS ts_et,
            open, high, low, close, volume
        FROM read_parquet('{parquet_glob}', hive_partitioning=true)
        ORDER BY ts
    """
    con = duckdb.connect()
    df = con.execute(query).fetchdf()
    con.close()
    return df


def check_duplicates(df: pd.DataFrame) -> int:
    """Count rows with duplicate timestamps."""
    return int(df["ts"].duplicated().sum())


def check_out_of_order(df: pd.DataFrame) -> int:
    """Count rows where timestamp is earlier than the previous row."""
    return int((df["ts"].diff().dt.total_seconds().dropna() < 0).sum())


def check_rth_days(df: pd.DataFrame) -> tuple[int, int, int, list[dict]]:
    """Analyze RTH trading days by bar count.

    Returns (trading_days, full_days, half_days, anomalous_days).
    """
    # Filter to RTH hours
    rth = df[
        (df["ts_et"].dt.time >= pd.Timestamp("09:30").time())
        & (df["ts_et"].dt.time < pd.Timestamp("16:00").time())
    ].copy()

    rth["date"] = rth["ts_et"].dt.date
    daily_counts = rth.groupby("date").size()

    trading_days = len(daily_counts)
    full_days = int((daily_counts == FULL_DAY_BARS).sum())
    half_days = int(daily_counts.isin(HALF_DAY_BARS).sum())

    # Anomalous = not full day and not a recognized half-day count
    anomalous_mask = (daily_counts != FULL_DAY_BARS) & (~daily_counts.isin(HALF_DAY_BARS))
    anomalous_days = [
        {"date": str(date), "bar_count": int(count)}
        for date, count in daily_counts[anomalous_mask].items()
    ]

    return trading_days, full_days, half_days, anomalous_days


def check_rth_gaps(df: pd.DataFrame) -> list[dict]:
    """Find gaps > 1 minute within RTH sessions.

    Only flags gaps within a single trading day's RTH session,
    not overnight gaps (which are expected).
    """
    rth = df[
        (df["ts_et"].dt.time >= pd.Timestamp("09:30").time())
        & (df["ts_et"].dt.time < pd.Timestamp("16:00").time())
    ].copy()

    rth["date"] = rth["ts_et"].dt.date
    gaps = []

    for date, group in rth.groupby("date"):
        ts_sorted = group["ts"].sort_values()
        diffs = ts_sorted.diff().dt.total_seconds().dropna()
        big_gaps = diffs[diffs > 60]

        for idx in big_gaps.index:
            gap_seconds = big_gaps[idx]
            after_ts = group.loc[idx, "ts_et"]
            gaps.append({
                "date": str(date),
                "after": str(after_ts.time()),
                "gap_minutes": int(gap_seconds // 60),
            })

    return gaps


def run_quality_check(
    symbol: str,
    data_dir: Path = PROCESSED_DIR,
) -> QualityReport:
    """Run all quality checks for a symbol."""
    logger.info("Running quality checks for %s ...", symbol)

    df = _query_bars(symbol, data_dir)
    report = QualityReport(symbol=symbol, total_rows=len(df))

    report.duplicate_count = check_duplicates(df)
    report.out_of_order_count = check_out_of_order(df)

    (
        report.trading_days,
        report.full_days,
        report.half_days,
        report.anomalous_days,
    ) = check_rth_days(df)

    report.rth_gaps = check_rth_gaps(df)

    return report


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    for symbol in ("ES", "NQ"):
        report = run_quality_check(symbol)
        print()
        print(report.summary())
        print()
