"""Small notebook I/O helpers. Queries and calculations stay in the notebooks."""

import csv
import json
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

import pandas as pd

from aily_project.services.fmi.extraction import SPECS, Reader, verify_read_only
from aily_project.services.fmi.models import Row, Snapshot, clean, fingerprint


def begin_extract(data: Path) -> Path:
    """Stage one notebook run without changing the last complete CSV handoff."""
    work = data / ".work"
    work.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="extract-", dir=work))


def publish_extract(staged: Path, destination: Path) -> None:
    """Publish a complete handoff; preserve the previous one in the work folder."""
    if (
        destination.name != "extract"
        or staged.parent != destination.parent / ".work"
        or not staged.name.startswith("extract-")
    ):
        raise ValueError("Use the notebook extraction staging directory")
    required = ("financials", "posts", "profiles", "registry", "overrides", "metadata")
    if any(not (staged / f"{name}.csv").exists() for name in required):
        raise ValueError("Cannot publish an incomplete extraction")
    if load_table(staged / "metadata")[0].get("authenticated") is not True:
        raise ValueError("Cannot publish an unauthenticated extraction")
    previous = staged.with_name("previous-" + staged.name)
    if destination.exists():
        destination.rename(previous)
    try:
        staged.rename(destination)
    except OSError:
        if previous.exists():
            previous.rename(destination)
        raise


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def save_json(value: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(clean(value), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )


def save_table(rows: list[Row], path: Path) -> pd.DataFrame:
    """Save one CSV and return its table for display()."""
    rows = clean(rows)
    path = path.with_suffix(".csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(dict.fromkeys(k for row in rows for k in row))

    def csv_value(value: Any) -> Any:
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            value = str(value).lower()
        # CSV may be opened in Excel. Do not execute a source caption as a formula.
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, quoting=csv.QUOTE_NONNUMERIC
        )
        writer.writeheader()
        writer.writerows({k: csv_value(row.get(k)) for k in columns} for row in rows)
    return pd.DataFrame(rows)


def load_table(path: Path) -> list[Row]:
    """Read CSVs, preserving string identifiers and missing values."""
    csv.field_size_limit(16 * 1024 * 1024)
    with path.with_suffix(".csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, quoting=csv.QUOTE_NONNUMERIC))
    for row in rows:
        for key, value in row.items():
            if value == "":
                row[key] = None
            elif isinstance(value, float) and value.is_integer():
                row[key] = int(value)
            elif isinstance(value, str):
                if value.startswith("'") and value[1:].startswith(("=", "+", "-", "@")):
                    row[key] = value[1:]
                elif value.startswith(("[", "{")):
                    with suppress(json.JSONDecodeError):
                        row[key] = json.loads(value)
                elif value in {"true", "false"} and (
                    key.startswith("is_")
                    or key.endswith(
                        ("_verified", "_approved", "_reviewed", "_eligible")
                    )
                    or key
                    in {
                        "authenticated",
                        "headline_selection",
                        "event_invited",
                        "fmi_required",
                        "proxy",
                        "prospect",
                        "selected",
                        "headline",
                        "approved",
                        "reviewed",
                        "relevant",
                        "comparable",
                        "include",
                        "has_dossier_data",
                    }
                ):
                    row[key] = value == "true"
    return rows


def read_snapshot(folder: Path) -> Snapshot:
    """Assemble the five saved source tables for the existing selection helpers."""
    metadata = load_table(folder / "metadata")[0]
    for key, filename in (
        ("candidate_mappings", "identity-candidates"),
        ("financial_source_documents", "source-documents"),
        ("competitor_candidates", "competitor-candidates"),
    ):
        path = folder / f"{filename}.csv"
        metadata[key] = load_table(path) if path.exists() else []
    return Snapshot(
        **{
            name: load_table(folder / name)
            for name in ("financials", "posts", "profiles", "registry", "overrides")
        },
        metadata=metadata,
    )


def read_source(
    client: Reader,
    schema: dict[str, set[str]],
    relation: str,
    where: str,
    params: tuple,
    required: set[str],
    folder: Path,
    metadata: Row,
    limit: int,
    *,
    include_content: bool = False,
) -> list[Row]:
    """Run one notebook-defined, bounded SELECT and immediately save its rows."""
    if relation not in SPECS or not 1 <= limit <= 500000:
        raise ValueError("Use a known relation and bounded row limit")
    if not where or ";" in where or "--" in where or "/*" in where:
        raise ValueError("Use one reviewed WHERE clause with bound values")
    verify_read_only(client)
    present = schema.get(relation, set())
    missing = required - present
    if missing:
        metadata["limitations"].append(f"{relation}: missing columns {sorted(missing)}")
        return []
    columns = [c for c in SPECS[relation] if c in present]
    if include_content:
        if (
            relation != "denormalized.finance_specific_investor_relations"
            or "content" not in present
        ):
            raise ValueError("Issuer body reads require the discovered content column")
        columns.append("content")
    query = f"SELECT {', '.join(columns)} FROM {relation} WHERE {where} LIMIT %s"
    print(query)  # Identifiers/placeholder SQL only; never credentials.
    frame = client.fetch_data_as_df(query, bind_params=(*params, limit + 1))
    if len(frame) > limit:
        raise ValueError(f"{relation}: row limit exceeded; narrow query scope")
    raw = clean(frame.to_dict("records"))
    rows = [
        {
            **row,
            "source_relation": relation,
            "source_row_id": fingerprint({"relation": relation, "row": row}),
            "extracted_at": metadata["extracted_at"],
        }
        for row in raw
    ]
    metadata["queries"].append(
        {
            "source_relation": relation,
            "columns": columns,
            "query": query,
            "scope": clean(params),
            "row_count": len(rows),
            "extracted_at": metadata["extracted_at"],
        }
    )
    save_table(rows, folder / relation.replace(".", "__"))
    save_table(metadata["queries"], folder.parent / "queries")
    print(f"Saved {len(rows):,} rows from {relation}")
    return rows
