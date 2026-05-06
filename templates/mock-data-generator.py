"""Generate deterministic sandbox CSV data for a new source system.

Usage:
    python3 templates/mock-data-generator.py

Copy this file to a project-specific script or edit the schema below, then save
outputs under data/sandbox/. Never generate or commit real source data here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from faker import Faker

ROW_COUNT = 1_000
OUTPUT_PATH = Path("data/sandbox/<system>.csv")

fake = Faker()
Faker.seed(42)

rows = [
    {
        "id": i,
        "name": fake.name(),  # PII — mask before Bronze writes.
        "email": fake.email(),  # PII — mask before Bronze writes.
        "amount": float(fake.pydecimal(left_digits=4, right_digits=2, positive=True)),
        "created_at": fake.date_this_year().isoformat(),
    }
    for i in range(1, ROW_COUNT + 1)
]

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
print(f"Generated {len(rows)} rows at {OUTPUT_PATH}")
