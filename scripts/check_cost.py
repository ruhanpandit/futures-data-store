"""Check Databento download cost before spending credits.

Run: python scripts/check_cost.py
"""

import os

import databento as db
from dotenv import load_dotenv

load_dotenv()

client = db.Historical(os.environ["DATABENTO_API_KEY"])

# ES and NQ continuous front-month on CME Globex (GLBX.MDP3)
# stype_in="continuous" tells Databento to handle contract rolls for us
# schema="ohlcv-1m" gives 1-minute OHLCV bars (server-side aggregation)
symbols = ["ES.c.0", "NQ.c.0"]

# Check cost for a broad date range first
# Adjust these dates based on how much history you want
cost = client.metadata.get_cost(
    dataset="GLBX.MDP3",
    symbols=symbols,
    schema="ohlcv-1m",
    start="2019-01-01",
    end="2024-12-31",
    stype_in="continuous",
)

print(f"Estimated cost: ${cost:.2f}")
print()
print("If this exceeds your $125 free credits, shrink the date range.")
print("A good starting point might be 2022-01-01 to 2024-12-31 (3 years).")

# Also check a smaller range for comparison
cost_small = client.metadata.get_cost(
    dataset="GLBX.MDP3",
    symbols=symbols,
    schema="ohlcv-1m",
    start="2022-01-01",
    end="2024-12-31",
    stype_in="continuous",
)

print(f"3-year range cost: ${cost_small:.2f}")
