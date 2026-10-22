# Changelog

## v0.2.0 (2026-10-22)

### MUST FIX (blocks Week 2)

1. **Data directory resolution**: `PROCESSED_DIR` no longer uses `Path(__file__).parents[2]` which breaks in non-editable installs. New resolution chain: explicit `data_dir` argument > `EDGE_LAB_DATA_DIR` env var > repo-relative fallback. `FileNotFoundError` names the env var.

2. **Timezone determinism**: DuckDB connections now force `SET TimeZone = 'UTC'`. `get_bars()` returns UTC timestamps regardless of machine timezone. Previously returned local-zone timestamps (hour 9 on ET machines, hour 13 on UTC machines).

3. **Contract rolls**:
   - Switched from `.c.0` (calendar roll) to `.v.0` (volume roll) symbology. Fixes 0-bar gap on every quarterly expiry Friday (23 missing trading days).
   - `normalize.py` now keeps `instrument_id` through to Parquet.
   - Quality report includes roll dates, old/new instrument IDs, and price jumps.

4. **`to_arrays()` contract for C++ engine**: Now returns `ts_ns` (int64 nanoseconds since epoch UTC), `open/high/low/close/volume` (float64), `instrument_id` (int64), `session_date` (int32 YYYYMMDD, CME convention: bars at/after 18:00 ET belong to next day). All C-contiguous.

### SHOULD FIX

5. **Out-of-order check**: Now checks physical Parquet file order instead of post-`ORDER BY` order. Added test with swapped-row fixture.

6. **Half-day dates**: `QualityReport.half_day_dates` stores the actual dates. Test asserts 2023-11-24 (Black Friday) is flagged.

7. **Synthetic test fixtures**: 21 tests run against `tmp_path` Parquet fixtures without real data. Real-data tests marked `@has_real_data` and skip when data is absent.

8. **SQL injection prevention**: Queries use DuckDB `$param` placeholders instead of f-strings. Symbol validated against allowlist (`ES`, `NQ`).

### NITS

- Queries now include a `year` predicate for real Hive partition pruning.
- README and CLAUDE.md updated to match code (UTC timestamps, `.v.0` symbology, `EDGE_LAB_DATA_DIR`, `instrument_id`).
- `.claude/settings.local.json` removed from git and added to `.gitignore`.
- README notes that Databento's `end` is exclusive (last day is 2024-12-30, not 2024-12-31).

## v0.1.0 (2026-10-17)

Initial release: Databento ingest, Parquet normalization, DuckDB query, quality checks, 14 tests passing.
