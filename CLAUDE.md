# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

futures-data-store is the data layer for Edge Lab, an 8-week quant research portfolio. It ingests CME futures data (ES, NQ) from Databento, normalizes to Parquet, and exposes a DuckDB query interface. Downstream repos (backtest-engine-cpp, fvg-signal-lab, etc.) pip-install this package.

## Commands

```bash
# Install (editable, with dev deps) -- use python -m pip on Windows
python -m pip install -e ".[dev]"

# Run tests
pytest

# Run a single test
pytest tests/test_query.py::test_rth_bar_count -v

# Lint
ruff check src/ tests/

# Cost check before downloading data
python scripts/check_cost.py
```

## Architecture

Data flows in three stages, each owned by one module:

```
Databento API  -->  download.py  -->  data/raw/*.dbn.zst
                    normalize.py -->  data/processed/{symbol}/year={YYYY}/*.parquet
                    query.py     -->  DuckDB over Parquet --> DataFrame / NumPy arrays
```

- **paths.py**: Centralized data directory resolution. Resolution order: explicit argument, EDGE_LAB_DATA_DIR env var, repo-relative fallback. Symbol validation against allowlist.
- **download.py**: Pulls 1-min OHLCV bars from GLBX.MDP3 using volume-roll symbology (`ES.v.0`, `NQ.v.0`). Streams to disk to keep memory flat.
- **normalize.py**: Converts raw Databento files to Parquet partitioned by symbol and year. Keeps instrument_id for contract roll tracking. Timestamps stored in UTC.
- **query.py**: `get_bars(symbol, start, end, session="rth"|"globex")` returns a DataFrame with UTC timestamps. `to_arrays()` returns C-contiguous arrays (ts_ns int64, OHLCV float64, instrument_id int64, session_date int32) for the C++ engine.
- **quality.py**: Data-quality checks (duplicate timestamps, physical-order verification, gaps, half-day detection, contract roll reporting). RTH gaps are anomalies; overnight gaps can be normal.

## Key conventions

- API key loaded from `.env` via python-dotenv. Never hardcode credentials.
- Raw data lives in `data/` which is gitignored. Reproducibility comes from the download script, not committed data files.
- src layout: imports require `pip install -e .` first.
- Timestamps are stored in UTC in Parquet. DuckDB connections force `SET TimeZone = 'UTC'` for deterministic output. Conversion to America/New_York happens in SQL filters only.
- RTH session: 09:30-16:00 ET. A normal trading day has exactly 390 one-minute bars.
- When pip-installed (non-editable), set `EDGE_LAB_DATA_DIR` to the data root directory.
- Queries use DuckDB `$param` placeholders, not f-string interpolation.
