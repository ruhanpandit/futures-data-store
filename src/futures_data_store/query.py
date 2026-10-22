"""Query interface over partitioned Parquet files using DuckDB.

Main entry points:
    get_bars(symbol, start, end, session) -> pd.DataFrame
    to_arrays(df) -> dict of contiguous float64 NumPy arrays
"""

import logging
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

# RTH = Regular Trading Hours for CME equity index futures
RTH_START = "09:30:00"
RTH_END = "16:00:00"


def get_bars(
    symbol: str,
    start: str,
    end: str,
    session: str = "rth",
    data_dir: Path = PROCESSED_DIR,
) -> pd.DataFrame:
    """Query OHLCV bars for a symbol and date range.

    Parameters
    ----------
    symbol : str
        "ES" or "NQ"
    start : str
        Start date inclusive, e.g. "2023-06-01"
    end : str
        End date inclusive, e.g. "2023-06-30"
    session : str
        "rth" for Regular Trading Hours (09:30-16:00 ET) or
        "globex" for the full session (no time filter)
    data_dir : Path
        Root of the processed Parquet directory

    Returns
    -------
    pd.DataFrame
        Columns: ts (UTC), open, high, low, close, volume
    """
    if session not in ("rth", "globex"):
        raise ValueError(f"session must be 'rth' or 'globex', got '{session}'")

    parquet_glob = str(data_dir / symbol / "**" / "*.parquet")

    # DuckDB reads the Hive-partitioned directory and applies partition pruning
    # timezone() converts UTC timestamps to ET for session filtering
    query = f"""
        SELECT ts, open, high, low, close, volume
        FROM read_parquet('{parquet_glob}', hive_partitioning=true)
        WHERE ts >= '{start}'::TIMESTAMPTZ
          AND ts < '{end}'::TIMESTAMPTZ + INTERVAL 1 DAY
    """

    if session == "rth":
        query += f"""
          AND CAST(timezone('America/New_York', ts) AS TIME)
              >= '{RTH_START}'::TIME
          AND CAST(timezone('America/New_York', ts) AS TIME)
              < '{RTH_END}'::TIME
        """

    query += "\n        ORDER BY ts"

    logger.debug("Running query:\n%s", query)

    con = duckdb.connect()
    df = con.execute(query).fetchdf()
    con.close()

    logger.info(
        "get_bars(%s, %s, %s, %s): %d rows",
        symbol, start, end, session, len(df),
    )
    return df


def to_arrays(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Convert a bars DataFrame to contiguous float64 NumPy arrays.

    Returns a dict with keys: open, high, low, close, volume.
    These are ready to pass to the C++ backtest engine via pybind11.
    Contiguous layout (C order) is required for zero-copy access in C++.
    """
    arrays = {}
    for col in ("open", "high", "low", "close", "volume"):
        arrays[col] = np.ascontiguousarray(df[col].to_numpy(dtype=np.float64))
    return arrays


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # Quick smoke test: a normal Tuesday
    df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth")
    print(f"\nES RTH bars on 2023-10-03 (Tuesday): {len(df)} rows")
    print(df.head())
    print("\nExpected: 390 bars (09:30-16:00 ET, 1-min each)")

    # Test to_arrays
    arrs = to_arrays(df)
    print(f"\nto_arrays keys: {list(arrs.keys())}")
    print(f"close array: shape={arrs['close'].shape}, dtype={arrs['close'].dtype}, "
          f"contiguous={arrs['close'].flags['C_CONTIGUOUS']}")
