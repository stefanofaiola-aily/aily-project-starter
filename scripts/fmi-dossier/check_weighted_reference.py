"""One-time snapshot of the supplied workbook plus roadmap evidence, no DB reads.

Run from the project root. The cached reference is comparison-only, not an input
to scoring. Run again only when a new historical reference is supplied.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from openpyxl import load_workbook

from aily_project.services.fmi_dossier.presentation import identity

KEYS = [
    "prospect",
    "coreInsight",
    "overallScore",
    "overallSentiment",
    "momentumScore",
    "momentumSentiment",
    "socialScore",
    "socialSentiment",
    "strengthScore",
    "strengthSentiment",
    "emailDomains",
    "companyCodes",
    "momentumDescriptor",
    "momentumInsight",
    "socialDescriptor",
    "socialInsight",
    "strengthDescriptor",
    "strengthInsight",
    "normalizedFashionMomentumIndex",
    "momentumKpiValue",
    "momentumKpiLabel",
    "socialKpiValue",
    "socialKpiLabel",
    "strengthKpiValue",
    "strengthKpiLabel",
    "leaderboardCategory",
    "leaderboardRank",
    "smFeb2024",
    "q4VsBaseline2024",
    "smFeb2025",
    "q4VsBaseline2025",
    "smFeb2026",
    "q4VsBaseline2026",
    "insightsDescriptive",
    "insightsStatistics",
    "q4VsBaseline2024YoyV2",
    "q4VsBaseline2025YoyV2",
    "q4VsBaseline2026YoyV2",
]
REFERENCE_ROOT = (
    Path(__file__).resolve().parent
    / "reference/aily-superagent-roadmap/docs/research/wwd-fashion-momentum"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workbook",
        type=Path,
        default=REFERENCE_ROOT / "weighted-delivery.xlsx",
    )
    parser.add_argument(
        "--roadmap",
        type=Path,
        default=REFERENCE_ROOT / "weighted-delivery.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/fmi-dossier/.work/weighted-reference.json"),
    )
    args = parser.parse_args()
    roadmap = json.loads(args.roadmap.read_text())
    records = {identity(r["prospectName"]): r for r in roadmap["records"]}
    generated = {identity(r["prospect"]): r for r in roadmap["deliveryRows"]}
    book = load_workbook(args.workbook, read_only=True, data_only=True)
    try:
        values = list(book["Delivery"].values)
    finally:
        book.close()
    header_index = next(i for i, v in enumerate(values) if v[0] == "Prospect")
    brands, discrepancies, snapshots = {}, [], {}
    verified = 0
    for cells in values[header_index + 1 :]:
        if not cells[0]:
            continue
        name, key = cells[0], identity(cells[0])
        if key in brands:
            raise ValueError("Duplicate historical identity: " + name)
        if len(cells) != len(KEYS):
            raise ValueError("Unexpected weighted Delivery column count")
        expected = generated.get(key)
        if expected:
            for field, actual in zip(KEYS, cells, strict=True):
                target = expected.get(field)
                if isinstance(target, list):
                    target = "; ".join(target) or None
                equal = (
                    math.isclose(actual, target, rel_tol=1e-10, abs_tol=1e-9)
                    if isinstance(actual, (int, float))
                    and isinstance(target, (int, float))
                    else actual == target
                )
                if not equal:
                    discrepancies.append(
                        {
                            "brand": name,
                            "field": field,
                            "workbook": actual,
                            "roadmap": target,
                        }
                    )
                else:
                    verified += 1
        record = records.get(key, {})
        page = record.get("page1", {})
        evidence = record.get("evidence", {})
        metadata = roadmap.get("sourceDocuments", {}).get(name, {})
        strength = record.get("page2", {}).get("strength", {})
        note = "; ".join(
            str(v)
            for v in [
                metadata.get("methodStatus"),
                metadata.get("sourceRuleHandling"),
                strength.get("categoryBasis"),
                evidence.get("componentScoreBasis"),
            ]
            if v
        )
        if name in roadmap.get("scoreRevisions", {}):
            note = (
                "Explicit user score revision/accepted proxy: "
                + roadmap["scoreRevisions"][name]["reconciliationStatus"]
            )
        if name in {"Fendi", "Marc Jacobs", "New Balance", "LVMH"}:
            note += (
                "; current Word dossier and roadmap use different component/"
                "portfolio or proxy methods; do not interchange source headlines"
            )
        brands[key] = {
            "name": name,
            "raw_fmi": cells[2],
            "display_fmi": cells[18],
            "ir_score": cells[4],
            "social_score": cells[6],
            "trend_score": cells[8],
            "overall_sentiment": cells[3],
            "trend_descriptor": cells[16],
            "core_insight": cells[1],
            "company_codes": cells[11],
            "category": cells[25],
            "selected_cycle": record.get("selectedCycleKey"),
            "financial_period_start": page.get("financialPeriodStart"),
            "financial_period_end": page.get("financialPeriodEnd"),
            "collection": page.get("collectionLabel"),
            "show_date": page.get("showDate"),
            "source_document": evidence.get("sourceDocument"),
            "method_note": note,
            "source_artifact_status": "Historical workbook is numeric reference; "
            "roadmap Markdown and local Word are distinct artifacts, "
            "not byte-identical documents",
        }
        snapshot_fields = {
            "email_domains": 10,
            "source_social_2024": 27,
            "source_q4_vs_baseline_2024": 28,
            "source_social_2025": 29,
            "source_q4_vs_baseline_2025": 30,
            "source_social_2026": 31,
            "source_q4_vs_baseline_2026": 32,
            "source_insights_descriptive": 33,
            "source_insights_statistics": 34,
            "source_q4_sales_yoy_2024": 35,
            "source_q4_sales_yoy_2025": 36,
            "source_q4_sales_yoy_2026": 37,
        }
        snapshots[key] = {
            "values": {k: cells[i] for k, i in snapshot_fields.items()},
            "source_reference": f"{args.workbook} | Delivery row "
            f"{header_index + 2 + len(brands) - 1}",
        }
    payload = {
        "source": str(args.workbook),
        "workbook_sha256": hashlib.sha256(args.workbook.read_bytes()).hexdigest(),
        "roadmap_source": str(args.roadmap),
        "roadmap_sha256": hashlib.sha256(args.roadmap.read_bytes()).hexdigest(),
        "verified_cells": verified,
        "workbook_roadmap_differences": discrepancies,
        "brands": brands,
        "delivery_snapshots": snapshots,
    }
    # Do not borrow roadmap periods/copy if the purported snapshots disagree.
    if discrepancies:
        raise ValueError(
            "Historical workbook/roadmap snapshot differ: "
            + json.dumps(discrepancies, ensure_ascii=False)
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(
        f"{len(brands)} historical brands; {verified} workbook/roadmap "
        "cells match; snapshot saved"
    )


if __name__ == "__main__":
    main()
