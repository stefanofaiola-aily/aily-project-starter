"""Dossier financial diagnostics, without inferring or approving source semantics."""

from collections import Counter
from dataclasses import asdict

from . import dossier_selection
from .inputs import as_dict
from .models import Inputs, Row, Snapshot, calendar_date, fingerprint, truth
from .policy import Policy
from .scoring import calculate

SEMANTIC_FIELDS = (
    "period_start",
    "period_end",
    "period_type",
    "scope",
    "currency",
    "unit_multiplier",
)


def actual_candidates(entity: Row, snapshot: Snapshot, metric: str) -> list[Row]:
    """Exact source identifiers only; no parent/alias or name-based substitution."""
    symbol = entity.get("shared_symbol") or entity.get("ticker")
    return [
        r
        for r in snapshot.financials
        if r.get("kind") == "actual"
        and r.get("metric") == metric
        and (
            bool(symbol) and r.get("symbol") == symbol
            if str(r.get("source_relation", "")).startswith(
                ("normalized.", "denormalized.")
            )
            else bool(entity.get("light_code"))
            and r.get("company_code") == entity["light_code"]
        )
    ]


def native_end_hint(row: Row, requested: Row) -> bool:
    """An inventory hint, never proof of start, grain, fiscal year, or scope."""
    end = requested.get("end")
    raw_end = row.get("period_end") or row.get("reported_date") or row.get("date")
    if not end or not raw_end:
        return False  # Native fiscal labels alone cannot establish date equivalence.
    try:
        distance = abs((calendar_date(raw_end) - calendar_date(end)).days)
    except (TypeError, ValueError):
        return False
    tolerance = (
        14 if requested.get("alignment") == "calendar_selling_window_proxy" else 0
    )
    return distance <= tolerance


def period_inventory(
    requested: Row,
    candidates: list[Row],
    selected: Row | None,
    scope: str | None,
    documents: list[Row] | None = None,
) -> Row:
    hints = [r for r in candidates if native_end_hint(r, requested)]
    document_hints = [r for r in documents or [] if native_end_hint(r, requested)]
    status = (
        "selected_by_dossier_service"
        if selected
        else "source_documents_present_measurement_adapter_required"
        if not hints and document_hints
        else "no_actual_observations_in_snapshot"
        if not candidates
        else "native_fiscal_period_requires_source_evidence"
        if not requested.get("end")
        else "no_native_end_hint_in_snapshot"
        if not hints
        else "observed_candidates_not_verified_or_conflicting"
    )
    return {
        "requested": requested,
        "status": status,
        "actual_observation_count": len(candidates),
        "native_end_hint_count": len(hints),
        "document_end_hint_count": len(document_hints),
        "document_candidates": [
            {
                k: r.get(k)
                for k in (
                    "company_code",
                    "url",
                    "period_start",
                    "period_end",
                    "document_type",
                    "source_row_id",
                )
            }
            for r in document_hints
        ],
        "missing_raw_semantics_counts": {
            k: sum(r.get(k) in (None, "") for r in hints) for k in SEMANTIC_FIELDS
        },
        "known_scope_mismatch_count": sum(
            r.get("scope") not in (None, "", scope) for r in hints
        ),
        "source_classifications": dict(
            Counter(str(r.get("source_classification") or "unknown") for r in hints)
        ),
        "candidate_source_row_ids": [r.get("source_row_id") for r in hints],
        "selected_source_row_id": selected.get("source_row_id") if selected else None,
        "selected_source_relation": selected.get("source_relation")
        if selected
        else None,
    }


def financial_inventory(inputs: Inputs, snapshot: Snapshot, analysis: Row) -> list[Row]:
    entities = {e["entity_id"]: e for e in inputs.entities}
    specs = analysis["dossier"].get("financial", {}).get("entities", {})
    assigned = [
        analysis["entity_id"],
        *(
            p["peer_entity_id"]
            for p in inputs.peers
            if p["analysis_id"] == analysis["analysis_id"]
        ),
    ]
    records = []
    for eid in dict.fromkeys([*assigned, *specs]):
        spec = specs.get(eid, {})
        entity = dossier_selection.source_subject(
            entities[eid], analysis, inputs.entities
        )
        candidates = actual_candidates(entity, snapshot, spec.get("metric", "revenue"))
        identifiers = {
            entity.get(k)
            for k in ("light_code", "shared_symbol", "ticker")
            if entity.get(k)
        }
        documents = [
            d
            for d in snapshot.metadata.get("financial_source_documents", [])
            if d.get("company_code") in identifiers
        ]
        selected, reasons = dossier_selection.series(
            inputs, entities[eid], snapshot, analysis
        )
        selected_by_role = {r["role"]: r for r in selected}
        periods = []
        for role in ("oldest", "earlier", "latest"):
            requested = spec.get("periods", {}).get(role, {})
            item = period_inventory(
                requested,
                candidates,
                selected_by_role.get(role),
                spec.get("scope"),
                documents,
            )
            defined = bool(
                spec.get("scope")
                and (
                    all(requested.get(k) for k in ("start", "end", "type"))
                    or requested.get("alignment") == "native_fiscal_year"
                    and requested.get("label")
                )
            )
            if not defined:
                item["status"] = "missing_dossier_parameter_definition"
            elif not any(
                entity.get(k) for k in ("light_code", "shared_symbol", "ticker")
            ):
                item["status"] = "missing_source_identifier"
            elif (
                analysis["dossier"].get("financial", {}).get("growth_basis")
                == "published_comparable_growth"
            ):
                item["status"] = "published_growth_source_required_not_nominal_revenue"
            periods.append({"role": role, **item})
        records.append(
            {
                "entity_id": eid,
                "name": entities[eid]["name"],
                "source_entity_id": spec.get("source_entity_id") or eid,
                "subject": spec.get("subject"),
                "scope": spec.get("scope"),
                "light_code": entity.get("light_code"),
                "shared_symbol": entity.get("shared_symbol") or entity.get("ticker"),
                "series_usable": len(selected) == 3 and not reasons,
                "source_document_count": len(documents),
                "selection_reasons": reasons,
                "periods": periods,
            }
        )
    return records


def build_handoff(
    inputs: Inputs, snapshot: Snapshot, policy: Policy
) -> tuple[str, Row]:
    """Use production selections and preserve distinctions in source coverage."""
    from .data_handoff import table, text

    if any(a.get("calculation_mode") != "dossier" for a in inputs.analyses):
        raise ValueError("Dossier coverage requires dossier inputs")
    run_id = fingerprint(
        {
            "inputs": as_dict(inputs),
            "snapshot": asdict(snapshot),
            "policy": policy.model_dump(),
        }
    )
    results, cohort = calculate(inputs, snapshot, policy, run_id)
    entities = {e["entity_id"]: e for e in inputs.entities}
    analyses = {a["analysis_id"]: a for a in inputs.analyses}
    prospects = []
    for result in results:
        analysis = analyses.get(result.analysis_id or "")
        prospects.append(
            {
                "brand_id": result.brand_id,
                "name": entities[result.brand_id]["name"],
                "mandatory": truth(entities[result.brand_id].get("fmi_required")),
                "financial": financial_inventory(inputs, snapshot, analysis)
                if analysis
                else [],
                "result": result.record(),
            }
        )
    statuses = Counter(
        p["status"] for b in prospects for e in b["financial"] for p in e["periods"]
    )
    actuals = [
        r
        for r in snapshot.financials
        if r.get("kind") == "actual" and r.get("metric") == "revenue"
    ]
    sources: list[Row] = [
        {
            "relation": relation,
            "actual_revenue_rows": len(rows),
            "missing_semantics": {
                k: sum(r.get(k) in (None, "") for r in rows) for k in SEMANTIC_FIELDS
            },
        }
        for relation in sorted({r["source_relation"] for r in actuals})
        if (rows := [r for r in actuals if r["source_relation"] == relation])
    ]
    lines = [
        "# FMI dossier source-coverage audit",
        "",
        f"Authenticated snapshot: {snapshot.metadata['extracted_at']}. "
        f"Run: `{run_id}`.",
        "",
        "Read-only diagnostic; inputs and manager/app deliveries are unchanged. "
        "Dossiers define subjects/scopes and scoring periods. Q4 2026 is only the "
        "forecast target. Selection and calculations use the production services.",
        "",
        "A native-end hint is an inventory aid, NOT proof of reporting boundaries, "
        "annual/discrete-quarter grain, fiscal-year equivalence, scope, units or "
        "provenance. A missing hint/observation means absent from this bounded "
        "extract, not absent from the database. Review unknown metadata against "
        "the authenticated source before requesting duplicate amounts. Known "
        "consolidated data cannot become retail/DTC or segment data by relabelling. "
        "No source metadata, amount, or approval is inferred here.",
        "Document candidates are exact-identifier/native-end matches only. "
        "Their bodies have NOT been interpreted by this audit; document metadata "
        "can be inconsistent. A document match does not verify an amount or make "
        "a missing revenue measurement eligible.",
        "",
        f"{len(results)} prospects; "
        f"{sum(b['mandatory'] for b in prospects)} mandatory; "
        f"{sum(r.values.get('fmi_status') == 'available' for r in results)} "
        "complete FMI; "
        f"{sum(r.values.get('social_score') is not None for r in results)} "
        "social scores; "
        f"{sum(r.values.get('forecast_status') == 'available' for r in results)} "
        "adjusted forecasts.",
        "",
        *table(
            ["Period status", "Count"], [[k, v] for k, v in sorted(statuses.items())]
        ),
        "",
        *table(
            ["Source", "Actual revenue rows", "Missing raw metadata (rows)"],
            [
                [
                    s["relation"],
                    s["actual_revenue_rows"],
                    "; ".join(f"{k}: {v}" for k, v in s["missing_semantics"].items()),
                ]
                for s in sources
            ],
        ),
        "",
        *table(
            ["Source document company code", "Indexed documents (not measurements)"],
            [
                [k, v]
                for k, v in sorted(
                    Counter(
                        str(d.get("company_code"))
                        for d in snapshot.metadata.get("financial_source_documents", [])
                    ).items()
                )
            ],
        ),
        "",
    ]
    for brand in prospects:
        lines.extend([f"## {brand['name']} (`{brand['brand_id']}`)", ""])
        for entity in brand["financial"]:
            lines.extend(
                [
                    f"{entity['name']}: subject {text(entity['subject'])}, scope "
                    f"{text(entity['scope'])}; explicit source "
                    f"`{entity['source_entity_id']}`; "
                    f"usable three-period series: {entity['series_usable']}.",
                    "",
                    *table(
                        [
                            "Role",
                            "Dossier period",
                            "Status",
                            "Actual rows / end hints / document hints",
                            "Missing metadata in hints",
                        ],
                        [
                            [
                                p["role"],
                                p["requested"].get("label")
                                or (
                                    f"{p['requested'].get('start')} / "
                                    f"{p['requested'].get('end')}"
                                ),
                                p["status"],
                                f"{p['actual_observation_count']} / "
                                f"{p['native_end_hint_count']} / "
                                f"{p['document_end_hint_count']}",
                                "; ".join(
                                    f"{k}: {v}"
                                    for k, v in p[
                                        "missing_raw_semantics_counts"
                                    ].items()
                                    if v
                                )
                                or "none",
                            ]
                            for p in entity["periods"]
                        ],
                    ),
                    "",
                    "Production selection reasons: "
                    + ("; ".join(entity["selection_reasons"]) or "none"),
                    "",
                    *[
                        f"- {p['role']}: {p['known_scope_mismatch_count']} "
                        "known scope mismatches; source classifications "
                        f"{text(p['source_classifications'])}."
                        for p in entity["periods"]
                        if p["known_scope_mismatch_count"]
                        or p["source_classifications"]
                    ],
                    "",
                ]
            )
        lines.extend(
            [
                "Full FMI missing reasons: "
                + text(brand["result"].get("missing_reasons")),
                "",
            ]
        )
    return "\n".join(lines) + "\n", {
        "run_id": run_id,
        "source_extracted_at": snapshot.metadata["extracted_at"],
        "input_hash": fingerprint(as_dict(inputs)),
        "snapshot_hash": fingerprint(asdict(snapshot)),
        "cohort": cohort,
        "period_status_counts": dict(statuses),
        "source_semantics": sources,
        "prospects": prospects,
        "results": [r.record() for r in results],
    }
