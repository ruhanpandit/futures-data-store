"""Download CME futures data from Databento to local raw files.

Each symbol gets its own .dbn.zst file in data/raw/.
Streams to disk to keep memory usage flat.
"""

import logging
import os
from pathlib import Path

import databento as db
from dotenv import load_dotenv

from futures_data_store.paths import resolve_raw_dir

load_dotenv()

logger = logging.getLogger(__name__)

SYMBOLS = ["ES.v.0", "NQ.v.0"]
DATASET = "GLBX.MDP3"
SCHEMA = "ohlcv-1m"
STYPE = "continuous"


def download_bars(
    symbols: list[str] = SYMBOLS,
    start: str = "2019-01-01",
    end: str = "2024-12-31",
    output_dir: Path | None = None,
) -> list[Path]:
    """Download 1-min OHLCV bars for the given symbols.

    Returns list of paths to the downloaded .dbn.zst files.
    """
    if output_dir is None:
        output_dir = resolve_raw_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    client = db.Historical(os.environ["DATABENTO_API_KEY"])

    downloaded: list[Path] = []
    for symbol in symbols:
        out_path = output_dir / f"{symbol.replace('.', '_')}_{start}_{end}.dbn.zst"

        if out_path.exists():
            logger.info("Skipping %s, already exists: %s", symbol, out_path)
            downloaded.append(out_path)
            continue

        logger.info("Downloading %s from %s to %s ...", symbol, start, end)

        data = client.timeseries.get_range(
            dataset=DATASET,
            symbols=[symbol],
            schema=SCHEMA,
            start=start,
            end=end,
            stype_in=STYPE,
        )

        # .to_file() streams to disk without buffering the full dataset in memory
        data.to_file(str(out_path))
        size_mb = out_path.stat().st_size / (1024 * 1024)
        logger.info("Saved %s (%.1f MB)", out_path.name, size_mb)
        downloaded.append(out_path)

    return downloaded


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    paths = download_bars()
    print(f"\nDownloaded {len(paths)} file(s):")
    for p in paths:
        print(f"  {p}")
