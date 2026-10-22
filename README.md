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
| `download.py` | Pull 1-min OHLCV bars from GLBX.MDP3 using continuous front-month symbology (`ES.c.0`, `NQ.c.0`). Streams to disk. |
| `normalize.py` | Convert raw `.dbn.zst` to Parquet partitioned by symbol and year. Timestamps stored in UTC. |
| `query.py` | `get_bars(symbol, start, end, session)` returns a DataFrame. `to_arrays()` returns contiguous float64 NumPy arrays. |
| `quality.py` | Data-quality checks: duplicates, gaps, out-of-order bars, half-day detection. |

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

# 390 one-minute RTH bars for a normal trading day
df = get_bars("ES", "2023-10-03", "2023-10-03", session="rth")

# Contiguous float64 arrays for C++ engine
arrays = to_arrays(df)
```

### 5. Quality report

```bash
python -m futures_data_store.quality
```

## Data coverage

| Symbol | Range | Rows |
|--------|-------|------|
| ES | 2019-01-01 to 2024-12-31 | 2,099,867 |
| NQ | 2019-01-01 to 2024-12-31 | 2,095,523 |

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

14 tests covering bar counts, session filtering, data types, array contiguity, and quality checks.

## Downstream usage

Later repos in the Edge Lab arc install this package:

```bash
pip install git+https://github.com/ruhanpandit/futures-data-store.git
```

```python
from futures_data_store.query import get_bars, to_arrays
```
