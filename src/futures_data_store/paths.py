"""Centralized data directory resolution.

Resolution order:
    1. Explicit data_dir argument passed to functions
    2. EDGE_LAB_DATA_DIR environment variable
    3. Repo-relative fallback (works in editable installs only)

If no Parquet files are found, raises FileNotFoundError naming the
EDGE_LAB_DATA_DIR env var so the user knows how to fix it.
"""

import os
from pathlib import Path

_ENV_VAR = "EDGE_LAB_DATA_DIR"

# Repo-relative fallback (only valid for editable installs)
_REPO_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

VALID_SYMBOLS = {"ES", "NQ"}


def resolve_data_dir(subdir: str, data_dir: Path | None = None) -> Path:
    """Resolve the data directory for a given subdirectory (raw or processed).

    Parameters
    ----------
    subdir : str
        "raw" or "processed"
    data_dir : Path | None
        Explicit override. If provided, returns data_dir / subdir directly.

    Returns
    -------
    Path
        Resolved path to data/{subdir}
    """
    if data_dir is not None:
        return data_dir / subdir

    env_val = os.environ.get(_ENV_VAR)
    if env_val:
        return Path(env_val) / subdir

    return _REPO_DATA_DIR / subdir


def resolve_processed_dir(data_dir: Path | None = None) -> Path:
    """Resolve the processed Parquet directory, raising if no data found."""
    d = resolve_data_dir("processed", data_dir)
    if not d.exists() or not any(d.glob("**/*.parquet")):
        raise FileNotFoundError(
            f"No Parquet files found in {d}. "
            f"Set the {_ENV_VAR} environment variable to your data root, "
            f"or pass data_dir explicitly."
        )
    return d


def resolve_raw_dir(data_dir: Path | None = None) -> Path:
    """Resolve the raw data directory."""
    return resolve_data_dir("raw", data_dir)


def validate_symbol(symbol: str) -> None:
    """Raise ValueError if symbol is not in the allowlist."""
    if symbol not in VALID_SYMBOLS:
        raise ValueError(
            f"Unknown symbol '{symbol}'. Valid symbols: {sorted(VALID_SYMBOLS)}"
        )
