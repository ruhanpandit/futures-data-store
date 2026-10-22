"""Convert raw Databento .dbn.zst files to partitioned Parquet.

Output layout:
    data/processed/{symbol}/year={YYYY}/bars.parquet

Timestamps are stored in UTC. Conversion to America/New_York
happens at query time (query.py), keeping the stored data unambiguous
across DST transitions.
"""

import logging
import re
from pathlib import Path

import databento as db
import pyarrow as pa
import pyarrow.parquet as pq

from futures_data_store.paths import resolve_data_dir, resolve_raw_dir

logger = logging.getLogger(__name__)

# Map raw filenames back to clean symbol names
# ES_v_0_2019-01-01_2024-12-31.dbn.zst --> ES
# ES_c_0_2019-01-01_2024-12-31.dbn.zst --> ES (legacy)
FILENAME_PATTERN = re.compile(r"^([A-Z]+)_[cv]_0_")


def _extract_symbol(filename: str) -> str:
    """Extract symbol name (ES, NQ) from raw filename."""
    match = FILENAME_PATTERN.match(filename)
    if not match:
        raise ValueError(f"Cannot extract symbol from filename: {filename}")
    return match.group(1)


def normalize_file(raw_path: Path, output_dir: Path | None = None) -> list[Path]:
    """Convert a single .dbn.zst file to partitioned Parquet files.

    Returns list of written Parquet file paths.
    """
    if output_dir is None:
        output_dir = resolve_data_dir("processed")
    symbol = _extract_symbol(raw_path.name)
    logger.info("Normalizing %s from %s ...", symbol, raw_path.name)

    # Read raw Databento file into a DataFrame
    store = db.DBNStore.from_file(str(raw_path))
    df = store.to_df()

    logger.info("  Raw rows: %d", len(df))

    # The index is the timestamp (ts_event). Move it to a column.
    df = df.reset_index()
    df = df.rename(columns={"ts_event": "ts"})

    # Keep OHLCV bars + instrument_id (needed for contract roll detection)
    keep_cols = ["ts", "open", "high", "low", "close", "volume", "instrument_id"]
    df = df[keep_cols]

    # Ensure timestamps are UTC
    if df["ts"].dt.tz is None:
        df["ts"] = df["ts"].dt.tz_localize("UTC")

    # Partition by year
    df["year"] = df["ts"].dt.year

    written: list[Path] = []
    for year, group in df.groupby("year"):
        year_dir = output_dir / symbol / f"year={year}"
        year_dir.mkdir(parents=True, exist_ok=True)
        out_path = year_dir / "bars.parquet"

        # Drop the year column before writing (it's encoded in the path)
        table = pa.Table.from_pandas(group.drop(columns=["year"]), preserve_index=False)
        pq.write_table(table, out_path)

        logger.info("  Wrote %s (%d rows)", out_path, len(group))
        written.append(out_path)

    return written


def normalize_all(
    raw_dir: Path | None = None,
    output_dir: Path | None = None,
) -> list[Path]:
    """Normalize all .dbn.zst files in the raw directory."""
    if raw_dir is None:
        raw_dir = resolve_raw_dir()
    raw_files = sorted(raw_dir.glob("*.dbn.zst"))
    if not raw_files:
        raise FileNotFoundError(f"No .dbn.zst files found in {raw_dir}")

    all_written: list[Path] = []
    for raw_path in raw_files:
        all_written.extend(normalize_file(raw_path, output_dir))

    logger.info("Normalization complete: %d Parquet files written", len(all_written))
    return all_written


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    paths = normalize_all()
    print(f"\nWrote {len(paths)} Parquet file(s):")
    for p in paths:
        print(f"  {p}")
