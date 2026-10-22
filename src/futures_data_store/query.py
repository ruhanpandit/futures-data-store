"""Query interface over partitioned Parquet files using DuckDB.

Main entry points:
    get_bars(symbol, start, end, session) -> pd.DataFrame
    to_arrays(df) -> dict of contiguous NumPy arrays
"""

import logging
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from futures_data_store.paths import resolve_processed_dir, validate_symbol

logger = logging.getLogger(__name__)

# RTH = Regular Trading Hours for CME equity index futures
RTH_START = "09:30:00"
RTH_END = "16:00:00"


def _get_connection() -> duckdb.DuckDBPyConnection:
    """Create a DuckDB connection with TimeZone forced to UTC.

    Why: DuckDB's fetchdf() converts TIMESTAMPTZ to the connection's
    TimeZone setting, which defaults to the machine's local zone.
    Without this, the same query returns hour 9 on an ET machine
    and hour 13 on a UTC machine. Forcing UTC makes output
    deterministic regardless of where the code runs.
    """
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    return con


def get_bars(
    symbol: str,
    start: str,
    end: str,
    session: str = "rth",
    data_dir: Path | None = None,
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
    data_dir : Path | None
        Root data directory override. Resolved via EDGE_LAB_DATA_DIR
        env var if not provided.

    Returns
    -------
    pd.DataFrame
        Columns: ts (UTC), open, high, low, close, volume, instrument_id
    """
    validate_symbol(symbol)
    if session not in ("rth", "globex"):
        raise ValueError(f"session must be 'rth' or 'globex', got '{session}'")

    processed = resolve_processed_dir(data_dir)
    parquet_glob = str(processed / symbol / "**" / "*.parquet")

    # DuckDB reads Hive-partitioned directory.
    # year predicate enables partition pruning (skips files for other years).
    # timezone() converts UTC to ET for RTH session filtering.
    query = """
        SELECT ts, open, high, low, close, volume, instrument_id
        FROM read_parquet($parquet_glob, hive_partitioning=true)
        WHERE year >= YEAR($start::DATE)
          AND year <= YEAR($end::DATE)
          AND ts >= $start::TIMESTAMPTZ
          AND ts < $end::TIMESTAMPTZ + INTERVAL 1 DAY
    """

    if session == "rth":
        query += """
          AND CAST(timezone('America/New_York', ts) AS TIME)
              >= $rth_start::TIME
          AND CAST(timezone('America/New_York', ts) AS TIME)
              < $rth_end::TIME
        """

    query += "\n        ORDER BY ts"

    logger.debug("Running query:\n%s", query)

    params = {
        "parquet_glob": parquet_glob,
        "start": start,
        "end": end,
    }
    if session == "rth":
        params["rth_start"] = RTH_START
        params["rth_end"] = RTH_END

    con = _get_connection()
    df = con.execute(query, params).fetchdf()
    con.close()

    logger.info(
        "get_bars(%s, %s, %s, %s): %d rows",
        symbol, start, end, session, len(df),
    )
    return df


def to_arrays(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Convert a bars DataFrame to contiguous NumPy arrays.

    Returns a dict with keys and dtypes matching the C++ engine contract:
        ts_ns:          int64   (nanoseconds since epoch, UTC)
        open:           float64
        high:           float64
        low:            float64
        close:          float64
        volume:         float64
        instrument_id:  int64
        session_date:   int32   (YYYYMMDD, CME convention: bars at or after
                                 18:00 ET belong to the next calendar day)

    All arrays are C-contiguous for zero-copy access via pybind11.
    """
    arrays: dict[str, np.ndarray] = {}

    # Timestamps as int64 nanoseconds since epoch (UTC)
    # pandas stores as datetime64[us], so raw int64 is microseconds; multiply by 1000
    ts = df["ts"]
    if ts.dt.tz is not None:
        ts = ts.dt.tz_convert("UTC")
    us_values = ts.astype("int64").to_numpy()
    arrays["ts_ns"] = np.ascontiguousarray(us_values * 1000)

    # Price + volume as float64
    for col in ("open", "high", "low", "close", "volume"):
        arrays[col] = np.ascontiguousarray(df[col].to_numpy(dtype=np.float64))

    # Instrument ID as int64
    arrays["instrument_id"] = np.ascontiguousarray(
        df["instrument_id"].to_numpy(dtype=np.int64)
    )

    # Session date: CME convention, bars at or after 18:00 ET belong to next day
    ts_et = df["ts"].dt.tz_convert("America/New_York")
    session_dates = ts_et.apply(
        lambda t: (t + pd.Timedelta(hours=6)).date()
    )
    arrays["session_date"] = np.ascontiguousarray(
        session_dates.apply(lambda d: d.year * 10000 + d.month * 100 + d.day)
        .to_numpy(dtype=np.int32)
    )

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
    print(f"ts_ns[0] = {arrs['ts_ns'][0]}")
    print(f"session_date[0] = {arrs['session_date'][0]}")
