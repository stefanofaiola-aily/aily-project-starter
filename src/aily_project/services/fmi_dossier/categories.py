"""Explicit three-category company-list assignments; never infer from brand type."""

from pathlib import Path

from openpyxl import load_workbook

from .model import Row
from .presentation import CATEGORIES, identity

# Reviewed spelling/name aliases already used in the dinner-list reconciliation.
# These are identities, not parent-financial substitutions or fuzzy matching.
ALIASES = {
    "hermes": "hermès",
    "ralh lauren": "ralph lauren",
    "abercromie & fitch": "abercrombie & fitch",
    "the gap": "gap inc",
}


def category_identity(name: str) -> str:
    key = identity(" ".join(name.split()))
    return ALIASES.get(key, key)


def read_categories(path: Path) -> dict[str, Row]:
    """Read company names in A and explicit app categories in B, with cell evidence."""
    workbook = load_workbook(path, read_only=True, data_only=True)
    assignments: dict[str, Row] = {}
    try:
        sheet = workbook.worksheets[0]
        if str(sheet.cell(1, 2).value).strip().casefold() != "category":
            raise ValueError(f"Expected Category header in {path} / {sheet.title}!B1")
        for index, (name, category) in enumerate(
            sheet.iter_rows(min_row=2, max_col=2, values_only=True), start=2
        ):
            if not name or not str(name).strip():
                continue
            value = (
                "_".join(str(category).strip().upper().split()) if category else None
            )
            if value is not None and value not in CATEGORIES:
                raise ValueError(
                    f"Unsupported category {category!r} for {name}: "
                    f"{path} / {sheet.title}!B{index}"
                )
            key = category_identity(str(name))
            if key in assignments:
                raise ValueError(f"Duplicate category assignment for {name} in {path}")
            assignments[key] = {
                "category": value,
                "source": f"{path} | {sheet.title}!B{index}",
            }
    finally:
        workbook.close()
    return assignments


def apply_categories(rows: list[Row], assignments: dict[str, Row]) -> list[Row]:
    """The current list replaces stale categories, never the score or forecast."""
    result = []
    for source in rows:
        row = dict(source)
        assignment = assignments.get(category_identity(row["name"]))
        category = assignment["category"] if assignment else None
        row.update(
            leaderboard_category=category,
            app_category=category,
            in_ranking_company_list=assignment is not None,
            leaderboard_category_source=assignment["source"] if assignment else None,
            leaderboard_category_assignment_status=(
                "current_company_list_assignment"
                if category
                else "missing_current_category_assignment"
                if assignment
                else "not_in_current_category_list"
            ),
        )
        result.append(row)
    return result
