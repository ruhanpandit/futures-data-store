# futures-data-store

Market data layer for [Edge Lab](https://github.com/ruhanpandit), an 8-week quant research portfolio. Ingests CME futures data (ES, NQ) from Databento, normalizes to Parquet, and exposes a DuckDB query interface.

## Architecture

```
Databento API  -->  download.py  -->  data/raw/*.dbn.zst
                    normalize.py -->  data/processed/{symbol}/year={YYYY}/*.parquet
                    query.py     -->  DuckDB over Parquet --> DataFrame / NumPy arrays
```

| Module | Responsibility |
|--------|---------------|
| `paths.py` | Data directory resolution (argument > `EDGE_LAB_DATA_DIR` env var > repo-relative fallback). |
| `download.py` | Pull 1-min OHLCV bars from GLBX.MDP3 using volume-roll symbology (`ES.v.0`, `NQ.v.0`). Streams to disk. |
| `normalize.py` | Convert raw `.dbn.zst` to Parquet partitioned by symbol and year. Timestamps stored in UTC. Keeps `instrument_id` for roll tracking. |
| `query.py` | `get_bars(symbol, start, end, session)` returns a UTC DataFrame. `to_arrays()` returns C-contiguous arrays for the C++ engine. |
| `quality.py` | Data-quality checks: duplicates, physical-order verification, gaps, half-day detection, contract roll reporting. |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
.venv\Scripts\Activate.ps1         # Windows PowerShell

python -m pip install -e ".[dev]"
```

## Usage

### 1. Check cost (before downloading)

```bash
python scripts/check_cost.py
```

### 2. Download raw data

Add your Databento API key to `.env`:

```
DATABENTO_API_KEY=your-key-here
```

```bash
python -m futures_data_store.download
```

### 3. Normalize to Parquet

```bash
python -m futures_data_store.normalize
```

### 4. Query

```python
from futures_data_store.query import get_bars, to_arrays

# 390 one-minute RTH bars for a normal trading day (timestamps in UTC)
df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth")

# C-contiguous arrays for the C++ backtest engine
arrays = to_arrays(df)
# keys: ts_ns (int64), open/high/low/close/volume (float64),
#        instrument_id (int64), session_date (int32 YYYYMMDD)
```

### 5. Non-editable install

When installing via pip (not editable), set the data directory:

```bash
export EDGE_LAB_DATA_DIR=/path/to/data
pip install git+https://github.com/ruhanpandit/futures-data-store.git
```

### 6. Quality report

```bash
python -m futures_data_store.quality
```

## Data coverage

| Symbol | Symbology | Range | Rows |
|--------|-----------|-------|------|
| ES | `ES.v.0` (volume roll) | 2019-01-01 to 2024-12-30 | 2,114,000 |
| NQ | `NQ.v.0` (volume roll) | 2019-01-01 to 2024-12-30 | 2,114,015 |

Note: Databento's `end` parameter is exclusive, so the last trading day included is 2024-12-30.

## Sessions

| Session | Hours (ET) | Bars/day |
|---------|-----------|----------|
| RTH | 09:30 - 16:00 | 390 |
| Half day (13:00 close) | 09:30 - 13:00 | 210 |
| Half day (13:15 close) | 09:30 - 13:15 | 225 |
| Globex | ~23 hrs/day | ~1,380 |

## Tests

```bash
pytest -v
```

30 tests: 21 synthetic (run without data via `tmp_path` fixtures) + 9 real-data (skipped when Parquet data is absent).

## Downstream usage

```bash
pip install git+https://github.com/ruhanpandit/futures-data-store.git
```

```python
from futures_data_store.query import get_bars, to_arrays
```
