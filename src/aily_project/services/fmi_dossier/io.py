"""Small typed CSV handoffs for the independent dossier notebooks."""

import csv
import json
from pathlib import Path

import pandas as pd

from .model import Row, clean


def save_table(rows: list[Row], path: Path) -> pd.DataFrame:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.with_suffix(".csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: json.dumps(
                        clean(row.get(k)), ensure_ascii=False, allow_nan=False
                    )
                    for k in keys
                }
            )
    return pd.DataFrame(rows)


def load_table(path: Path) -> list[Row]:
    with path.with_suffix(".csv").open(newline="") as stream:
        return [
            {k: json.loads(v) for k, v in row.items()} for row in csv.DictReader(stream)
        ]
