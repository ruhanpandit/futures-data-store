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

- **download.py**: Pulls 1-min OHLCV bars from GLBX.MDP3 using continuous front-month symbology (`ES.c.0`, `NQ.c.0`). Streams to disk to keep memory flat.
- **normalize.py**: Converts raw Databento files to Parquet partitioned by symbol and year. Handles UTC-to-ET conversion (DST-aware) and contract roll metadata.
- **query.py**: `get_bars(symbol, start, end, session="rth"|"globex")` returns a DataFrame. `to_arrays()` returns contiguous float64 NumPy arrays for the C++ engine (Week 2).
- **quality.py**: Data-quality checks (duplicate timestamps, gaps, out-of-order bars, half-day detection). RTH gaps are anomalies; overnight gaps can be normal.

## Key conventions

- API key loaded from `.env` via python-dotenv. Never hardcode credentials.
- Raw data lives in `data/` which is gitignored. Reproducibility comes from the download script, not committed data files.
- src layout: imports require `pip install -e .` first.
- Timestamps are stored in UTC in Parquet, converted to America/New_York at query time.
- RTH session: 09:30-16:00 ET. A normal trading day has exactly 390 one-minute bars.
