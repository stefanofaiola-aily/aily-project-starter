"""Separate, immutable dossier reference projection, never a DB input override.

The report is the authority, not its older summary CSV. Preserve its exact
headline and method exceptions; arithmetic checks use the printed components.
Q4 uplift from these scores is explicitly a new scenario, not historical replay.
"""

import csv
import json
import re
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .contract import Field
from .handover import WORD, matched_reports, names, read_reports
from .models import Inputs, Row, fingerprint, number
from .policy import Policy
from .scoring import half_up, legacy_uplift, uplift

SCORE = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*(?:/\s*100|out of 100)", re.I)


def report_content(path: Path) -> tuple[list[str], list[list[list[str]]]]:
    with ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))

    def text(node: ET.Element) -> str:
        return "".join(t.text or "" for t in node.findall(".//w:t", WORD))

    paragraphs = [text(p) for p in document.findall("w:body/w:p", WORD)]
    tables = [
        [
            [text(c) for c in row.findall("w:tc", WORD)]
            for row in table.findall("w:tr", WORD)
        ]
        for table in document.findall(".//w:tbl", WORD)
    ]
    return paragraphs, tables


def printed_number(text: str) -> float | None:
    match = re.match(r"\s*([+-]?\d+(?:\.\d+)?)", text.replace("−", "-"))
    return float(match[1]) if match else None


def components(tables: list[list[list[str]]], headline: float, normalized: bool) -> Row:
    """Read only explicitly labelled score tables; never treat growth as scores."""
    candidates = []
    for table in tables:
        if not table:
            continue
        header = [h.lower().replace(" ", "") for h in table[0]]
        social_col = next(
            (
                i
                for i, h in enumerate(header)
                if h.endswith(("social", "socialsubscore"))
            ),
            None,
        )
        ir_col = next(
            (
                i
                for i, h in enumerate(header)
                if h.endswith(("momentum", "momentumsubscore"))
            ),
            None,
        )
        trend_col = next(
            (
                i
                for i, h in enumerate(header)
                if h.endswith(("strength", "strengthsubscore"))
            ),
            None,
        )
        if all(c is not None for c in (social_col, ir_col, trend_col)):
            for row in table[1:]:
                if len(row) <= max(
                    int(c) for c in (social_col, ir_col, trend_col) if c is not None
                ):
                    continue
                values = [
                    printed_number(row[int(c)])
                    for c in (ir_col, social_col, trend_col)
                    if c is not None
                ]
                if len(values) == 3 and all(v is not None for v in values):
                    candidates.append((row[0], values))
        if header[0] == "component" and any(
            "subscore" in h
            or "percentile" in h
            or h == "scoreoutof100"
            or h.endswith("result")
            for h in header[1:]
        ):
            column = next(
                i
                for i, h in enumerate(header)
                if "subscore" in h
                or "percentile" in h
                or h == "scoreoutof100"
                or h.endswith("result")
            )
            found = {}
            for row in table[1:]:
                if len(row) <= column:
                    continue
                label = row[0].lower()
                key = (
                    "social"
                    if "social" in label or "attention" in label
                    else "trend"
                    if "strength" in label
                    else "ir"
                    if "momentum" in label
                    else None
                )
                if key:
                    found[key] = printed_number(row[column])
            if all(found.get(k) is not None for k in ("ir", "social", "trend")):
                candidates.append(
                    (
                        "percentile" if "percentile" in header[column] else "original",
                        [found[k] for k in ("ir", "social", "trend")],
                    )
                )
    if not candidates:
        return {}
    # The chosen headline may be a revised normalization, not the original score.
    preferred = [
        r
        for r in candidates
        if ("normalized" in r[0].lower() or "percentile" in r[0].lower()) == normalized
    ]
    candidates = preferred or candidates
    label, values = min(
        candidates,
        key=lambda r: abs(0.5 * r[1][0] + 0.3 * r[1][1] + 0.2 * r[1][2] - headline),
    )
    calculated = 0.5 * values[0] + 0.3 * values[1] + 0.2 * values[2]
    return {
        "dossier_ir_score": values[0],
        "dossier_social_score": values[1],
        "dossier_trend_score": values[2],
        "dossier_component_cycle": label,
        "dossier_component_sum": calculated,
        "dossier_arithmetic_status": "matches_printed_precision"
        if abs(calculated - headline) <= 0.15
        else "printed_components_do_not_match_headline",
    }


def project_report(path: Path) -> Row:
    paragraphs, tables = report_content(path)
    intro = " ".join(paragraphs[:4])
    matches = list(SCORE.finditer(intro))
    meaningful = [
        m
        for m in matches
        if re.search(
            r"overall|scores|score is|score:|FMI:|score of",
            intro[max(0, m.start() - 100) : m.start()],
            re.I,
        )
        and not re.search(
            r"subscore\s*(?:is|of|:)\s*$",
            intro[max(0, m.start() - 30) : m.start()],
            re.I,
        )
    ]
    matches = meaningful or matches
    partial = "subscore" in intro.lower() and not re.search(
        r"overall|combined|proxy score|scores \d", intro, re.I
    )
    # Reject a printed social-only subscore alongside an unavailable overall.
    overall_unavailable = bool(
        re.search(
            r"overall.*(?:remain unavailable|remains unavailable|score.*unavailable)",
            intro,
            re.I,
        )
    ) and not (matches and re.search(r"parent|hybrid|mixed.scope", intro, re.I))
    if overall_unavailable:
        matches = []
    headline = float(matches[0][1]) if matches and not partial else None
    normalized = "normalized" in intro.lower()
    raw = headline if not normalized else None
    display = None
    match = re.search(r"displayed as\s+(\d+(?:\.\d+)?)", intro, re.I)
    if match:
        display = float(match[1])
    # Tapestry's narrative lacks a headline, but an explicit overall table is valid.
    if headline is None and not partial and not overall_unavailable:
        for table in tables:
            if table and "overall" in " ".join(table[0]).lower():
                for row in table[1:]:
                    found = [m for cell in row for m in SCORE.finditer(cell)]
                    if found:
                        headline = float(found[-1][1])
                        raw = headline
    result: Row = {
        "dossier_headline_fmi": headline,
        "dossier_original_raw_fmi": raw,
        "dossier_historical_display_fmi": display,
        "dossier_score_basis": "component_percentile_normalized"
        if normalized
        else "original_weighted_method",
        "dossier_status": "reported_reference"
        if headline is not None
        else "partial_or_not_scoreable",
        "dossier_source": str(path),
        "dossier_source_sha256": sha256(path.read_bytes()).hexdigest(),
        "dossier_headline_evidence": intro,
        "dossier_method_limitations": "; ".join(
            p
            for p in paragraphs
            if re.search(
                r"assum|proxy|conditional|provisional|sample.*small|comment|TikTok|minimum",
                p,
                re.I,
            )
        )[:5000],
        "dossier_period_evidence": "; ".join(
            " | ".join(row) for table in tables[:2] for row in table
        )[:8000],
    }
    if headline is not None:
        result.update(components(tables, headline, normalized))
        if normalized:
            # Preserve any explicitly printed original-method calculation separately.
            for index, paragraph in enumerate(paragraphs):
                if (
                    re.search(r"50%.*30%.*20%|0\.50.*0\.30.*0\.20", paragraph)
                    and "original" in " ".join(paragraphs[index : index + 2]).lower()
                ):
                    found = list(SCORE.finditer(paragraph))
                    if found:
                        result["dossier_original_raw_fmi"] = float(found[-1][1])
                        break
            if result["dossier_original_raw_fmi"] is None:
                for table in tables:
                    for row in table:
                        if row[0].lower().startswith("original"):
                            found = [m for cell in row for m in SCORE.finditer(cell)]
                            if found:
                                result["dossier_original_raw_fmi"] = float(found[-1][1])
    result.setdefault(
        "dossier_arithmetic_status", "printed_component_inputs_unavailable"
    )
    return result


def dossier_records(inputs: Inputs, root: Path) -> list[Row]:
    reports = read_reports(root)
    summary_path = root / "FMI_delivery/01_FMI_results/FMI_results_summary.csv"
    with (
        summary_path.open(newline="", encoding="utf-8-sig")
        if summary_path.exists()
        else _empty_summary() as handle
    ):
        summaries = list(csv.DictReader(handle))
    rows = []
    for entity in inputs.entities:
        if not entity.get("prospect"):
            continue
        refs = matched_reports(entity, reports)
        if entity["entity_id"] == "global-luxury-retail-group-dba-missoni":
            refs = []  # A distributor cannot inherit Missoni brand performance.
        result = {
            "brand_id": entity["entity_id"],
            "name": entity["name"],
            "fmi_required": entity.get("fmi_required"),
            "dossier_status": "no_unique_report",
            "dossier_headline_fmi": None,
        }
        if len(refs) == 1:
            result.update(project_report(Path(refs[0]["path"])))
        variants = names(entity["name"]) | names(entity["entity_id"])
        matches = [
            r
            for r in summaries
            if names(r.get("Brand") or r.get("brand") or "") & variants
        ]
        if len(matches) == 1:
            result["historical_summary_raw_fmi"] = number(
                matches[0].get("fmi_raw_historical")
            )
            original = number(result.get("dossier_original_raw_fmi"))
            result["historical_summary_conflict"] = (
                original is not None
                and result["historical_summary_raw_fmi"] is not None
                and abs(original - result["historical_summary_raw_fmi"]) > 0.15
            )
        rows.append(result)
    return rows


def _empty_summary():
    from io import StringIO

    return StringIO("")


def component_comparison(reference: Row, current: Row, policy: Policy) -> Row:
    """Explain headline differences using printed components, never replace them.

    Report components use their printed 50/30/20 scale, which may be percentile
    normalized. Compare to the report headline, not its separate original raw.
    Independently available current components survive an unavailable total FMI.
    """
    result: Row = {}
    impacts = []
    for component, report_weight in (("ir", 0.5), ("social", 0.3), ("trend", 0.2)):
        old = number(reference.get(f"dossier_{component}_score"))
        new = number(current.get(f"{component}_score"))
        weight = getattr(policy, f"{component}_weight")
        result[f"current_{component}_score"] = new
        result[f"comparison_{component}_difference"] = (
            new - old if new is not None and old is not None else None
        )
        impact = (
            new * weight - old * report_weight
            if new is not None and old is not None
            else None
        )
        result[f"comparison_{component}_fmi_impact"] = impact
        impacts.append(impact)
    complete = (
        all(value is not None for value in impacts)
        and number(current.get("raw_fmi")) is not None
    )
    printed_sum = number(reference.get("dossier_component_sum"))
    headline = number(reference.get("dossier_headline_fmi"))
    result.update(
        comparison_components_fmi_difference=sum(impacts) if complete else None,
        comparison_headline_rounding_difference=printed_sum - headline
        if printed_sum is not None and headline is not None
        else None,
        comparison_component_status="complete_diagnostic_not_like_for_like"
        if complete
        else "partial_components_complete_fmi_comparison_unavailable",
    )
    return result


def refresh_comparisons(
    references: list[Row],
    current: list[Row],
    policy: Policy,
    analyses: list[Row] | None = None,
) -> list[Row]:
    """Refresh only existing current_/comparison_ columns, never report values.

    This consumes the one-off reference export, not Word files. Stable IDs retain
    row order and prevent accidental row multiplication or identity replacement.
    """
    ids = [r["brand_id"] for r in current]
    if len(ids) != len(set(ids)) or len({r["brand_id"] for r in references}) != len(
        references
    ):
        raise ValueError("Dossier comparison requires unique brand IDs")
    by_id = {r["brand_id"]: r for r in current}
    by_analysis = {a["analysis_id"]: a for a in analyses or []}
    rows = []
    for reference in references:
        db = by_id.get(reference["brand_id"], {})
        values = {"current_" + k: v for k, v in db.items()}
        method = by_analysis.get(db.get("analysis_id"), {}).get("dossier", {})
        settings = method.get("social", {})
        metric = settings.get("metric", "likes")
        values.update(
            current_social_metric=settings.get("metric"),
            current_social_aggregation=settings.get("aggregation", "single_account"),
            current_caption_pattern=settings.get("caption_pattern"),
            current_social_median=db.get(f"current_median_{metric}"),
            current_baseline_social_median=db.get(f"baseline_median_{metric}"),
            current_social_usable_posts=db.get("current_usable_posts"),
            current_baseline_social_usable_posts=db.get("baseline_usable_posts"),
            current_social_lift=db.get(f"{metric}_lift"),
            current_trend_rule=method.get("trend", {}).get("rule"),
        )
        periods = (
            method.get("financial", {})
            .get("entities", {})
            .get(reference["brand_id"], {})
            .get("periods", {})
        )
        values.update(
            {
                f"current_{role}_requested_period": json.dumps(
                    periods[role], ensure_ascii=False
                )
                if periods.get(role)
                else None
                for role in ("oldest", "earlier", "latest")
            }
        )
        values.update(component_comparison(reference, db, policy))
        raw = number(db.get("raw_fmi"))
        values.update(
            comparison_raw_difference=raw - reference["dossier_original_raw_fmi"]
            if raw is not None and reference.get("dossier_original_raw_fmi") is not None
            else None,
            comparison_headline_difference=raw - reference["dossier_headline_fmi"]
            if raw is not None and reference.get("dossier_headline_fmi") is not None
            else None,
            comparison_status="dossier_parameters_current_database_measurements_not_historical_replay",
            current_missing_inputs=db.get("missing_reasons"),
            current_window=db.get("current_window"),
            current_baseline_window=db.get("baseline_window"),
            current_extracted_at=db.get("data_extracted_at"),
        )
        rows.append(
            {
                k: values.get(k) if k.startswith(("current_", "comparison_")) else v
                for k, v in reference.items()
            }
        )
    return rows


def scenario_rows(
    references: list[Row], current: list[Row], policy: Policy
) -> list[Row]:
    """Attach Q4 uplift only to explicitly aligned financial subjects."""
    by_id = {r["brand_id"]: r for r in current}
    available = [r for r in references if r.get("dossier_headline_fmi") is not None]
    values = [
        r["dossier_original_raw_fmi"]
        for r in available
        if r.get("dossier_original_raw_fmi") is not None
    ]
    lo, hi = (min(values), max(values)) if values else (None, None)
    cohort_id = fingerprint(
        {
            "members": sorted(
                r["brand_id"]
                for r in available
                if r.get("dossier_original_raw_fmi") is not None
            ),
            "scores": values,
            "policy": policy.model_dump(),
        }
    )
    rows = []
    # Exact archived financial subject, not inferred ownership or fuzzy names.
    subjects = {
        "burberry": "BRBY.L",
        "ralph-lauren": "RL",
        "gap-inc": "GAP",
        "j-crew": "JCREW",
        "hermes": "HERMES",
        "me-em": "MEEM",
        "victoria-s-secret-co": "VSCO",
        "g-iii-apparel-group": "GIII",
        "pacsun": "PACSUN",
        "jacquemus": "JACQUEMUS",
        "lafayette-148": "LAFAYET148",
        "lilly-pulitzer": "LILLYPUL",
        "nordstrom": "JWN",
        "bloomingdales": "M",
        "kohl-s": "KSS",
        "estee-lauder": "EL",
        "new-balance": "NEWBALANCE",
        "ulta-beauty": "ULTA",
        "david-yurman": "DYURMAN",
        "vf-corporation": "VFC",
        "lvmh": "LVMHF",
        "louis-vuitton": "LVMHF",
        "missoni": "MISSONI",
        "valentino": "VALENTINO",
        "prada": "PRDSY",
        "chanel": "CHANEL",
    }
    for reference in available:
        row = dict(reference)
        db = by_id.get(row["brand_id"], {})
        score = row.get("dossier_original_raw_fmi")
        display = (
            half_up(
                policy.display_equal
                if lo == hi
                else policy.display_lower
                + (policy.display_upper - policy.display_lower)
                * (score - lo)
                / (hi - lo)
            )
            if score is not None and lo is not None and hi is not None
            else None
        )
        row.update(
            run_id=db.get("run_id"),
            dossier_scenario_cohort_id=cohort_id,
            dossier_scenario_policy_id=policy.version,
            comparison_headline_difference=db["raw_fmi"] - row["dossier_headline_fmi"]
            if db.get("raw_fmi") is not None
            else None,
            current_raw_fmi=db.get("raw_fmi"),
            current_display_fmi=db.get("display_fmi"),
            dossier_scenario_display_fmi=display,
            dossier_scenario_cohort_min=lo,
            dossier_scenario_cohort_max=hi,
            dossier_scenario_uplift_fraction=uplift(display, policy)
            if display is not None
            else None,
            dossier_scenario_legacy_uplift_fraction=legacy_uplift(
                row["dossier_original_raw_fmi"], policy
            )
            if row.get("dossier_original_raw_fmi") is not None
            else None,
            comparison_raw_difference=db["raw_fmi"] - row["dossier_original_raw_fmi"]
            if db.get("raw_fmi") is not None
            and row.get("dossier_original_raw_fmi") is not None
            else None,
            comparison_status="different_period_scope_windows_and_possible_normalization_not_like_for_like",
            dossier_forecast_status="scope_alignment_not_verified_no_dossier_q4_baseline",
            dossier_scenario_notice="Archived dossier headline unchanged. New "
            "rescaling/uplift scenario, NOT original forecast or strict replay.",
        )
        row.update(component_comparison(reference, db, policy))
        if score is None:
            row["dossier_forecast_status"] = (
                "percentile_headline_preserved_original_raw_missing"
            )
        baseline = number(db.get("baseline_revenue"))
        if (
            baseline is not None
            and baseline > 0
            and subjects.get(row["brand_id"]) == db.get("light_code")
            and row["dossier_scenario_uplift_fraction"] is not None
        ):
            row.update(
                dossier_forecast_status="current_q4_scope_matched_scenario_not_original_forecast",
                baseline_revenue=baseline,
                financial_subject=db.get("financial_subject"),
                baseline_period_label=db.get("baseline_period_label"),
                baseline_period_end=db.get("baseline_period_end"),
                baseline_currency=db.get("baseline_currency"),
                baseline_unit_multiplier=db.get("baseline_unit_multiplier"),
                baseline_source_row_id=db.get("baseline_source_row_id"),
                baseline_source_relation=db.get("baseline_source_relation"),
                dossier_scenario_adjustment=baseline
                * row["dossier_scenario_uplift_fraction"],
                dossier_scenario_adjusted_forecast=baseline
                * (1 + row["dossier_scenario_uplift_fraction"]),
            )
            old = row["dossier_scenario_legacy_uplift_fraction"]
            row.update(
                dossier_scenario_legacy_adjustment=baseline * old
                if old is not None
                else None,
                dossier_scenario_legacy_adjusted_forecast=baseline * (1 + old)
                if old is not None
                else None,
            )
        rows.append(row)
    return rows


def payload(rows: list[Row]) -> Row:
    keys = list(
        dict.fromkeys(
            [
                "name",
                "brand_id",
                "fmi_required",
                "dossier_headline_fmi",
                "dossier_original_raw_fmi",
                "current_raw_fmi",
                "comparison_raw_difference",
                *[
                    key
                    for component in ("ir", "social", "trend")
                    for key in (
                        f"dossier_{component}_score",
                        f"current_{component}_score",
                        f"comparison_{component}_difference",
                        f"comparison_{component}_fmi_impact",
                    )
                ],
                "comparison_components_fmi_difference",
                "comparison_headline_rounding_difference",
                "comparison_component_status",
                *[k for r in rows for k in r],
            ]
        )
    )
    fields = []
    descriptions = {
        "dossier_headline_fmi": "Exact headline; may be a percentile proxy.",
        "dossier_original_raw_fmi": "Printed original raw; not a percentile.",
        "dossier_historical_display_fmi": "Archived printed 70–98 display.",
        "comparison_raw_difference": "Current minus original raw; NOT like-for-like.",
        "comparison_headline_difference": "Current minus headline; scales may differ.",
        "dossier_component_sum": "50% IR + 30% Social + 20% Trend from printed scores.",
        "dossier_arithmetic_status": "Printed sum vs headline; tolerance 0.15.",
        "dossier_scenario_display_fmi": "NEW raw-only rescaling; no percentiles.",
        "dossier_scenario_uplift_fraction": "NEW rate, not original forecast.",
        "dossier_forecast_status": "Current Q4 scope-matched scenario only.",
        "dossier_period_evidence": "Verbatim first tables; NOT current measurements.",
        "dossier_source_sha256": "SHA256 of the unchanged authoritative source report.",
        "historical_summary_conflict": "Old CSV disagrees with report; report wins.",
        "comparison_components_fmi_difference": "Sum of the three weighted component "
        "impacts. Explains current raw minus the report's printed component sum, "
        "not necessarily its separately recorded original raw score.",
        "comparison_headline_rounding_difference": "Printed component sum minus "
        "report headline. Add to component impacts to reconcile the headline "
        "difference. May expose a report mismatch, not only rounding.",
        "comparison_component_status": "Complete or partial component diagnostic. "
        "Different periods, subjects and percentile normalization remain explicit.",
    }
    labels = {
        "current_fmi_status": "Current FMI status",
        "current_scope": "Current revenue scope",
        "current_earlier_growth": "Earlier brand YoY growth",
        "current_latest_growth": "Latest brand YoY growth",
        "current_earlier_peer_median_growth": "Earlier peer-median YoY growth",
        "current_latest_peer_median_growth": "Latest peer-median YoY growth",
        "current_earlier_gap_pp": "Earlier brand-minus-peer gap (pp)",
        "current_latest_gap_pp": "Latest brand-minus-peer gap (pp)",
        "current_used_peer_count": "Usable peer count",
        "current_used_peer_names": "Usable peers",
        "current_social_metric": "Social metric",
        "current_social_aggregation": "Social aggregation",
        "current_caption_pattern": "Collection caption rule",
        "current_window": "Current social window",
        "current_baseline_window": "Baseline social window",
        "current_social_median": "Current median engagement",
        "current_baseline_social_median": "Baseline median engagement",
        "current_social_usable_posts": "Usable current posts",
        "current_baseline_social_usable_posts": "Usable baseline posts",
        "current_social_lift": "Social median/member lift",
        "current_trend_basis": "Current Trend basis",
        "current_trend_rule": "Current Trend rule",
        "current_trend_change_pp": "Trend change (pp)",
        "current_extracted_at": "Current data extracted at",
        **{
            f"current_{r}_requested_period": f"Requested {r} revenue period"
            for r in ("oldest", "earlier", "latest")
        },
        **{
            f"current_{c}_{k}": f"Current {'IR' if c == 'ir' else c.capitalize()} {k}"
            for c in ("ir", "social", "trend")
            for k in ("weight", "contribution")
        },
    }
    for component, weight in (("ir", 0.5), ("social", 0.3), ("trend", 0.2)):
        name = "IR" if component == "ir" else component.capitalize()
        labels.update(
            {
                f"dossier_{component}_score": f"Dossier {name} score",
                f"current_{component}_score": f"Database {name} score",
                f"comparison_{component}_difference": f"{name} score difference",
                f"comparison_{component}_fmi_impact": (
                    f"{name} impact on FMI difference"
                ),
            }
        )
        descriptions.update(
            {
                f"dossier_{component}_score": "Exact printed report component. "
                "May use percentiles or different historical methods/windows.",
                f"current_{component}_score": "Current database service component; "
                "retained independently even if complete FMI is unavailable.",
                f"comparison_{component}_difference": "Database minus printed dossier "
                "component, in score points. Diagnostic, not a like-for-like change.",
                f"comparison_{component}_fmi_impact": "Current score × resolved policy "
                f"weight minus printed report score × {weight:g}, in FMI points.",
            }
        )
    for key in keys:
        numeric = (
            key.endswith(("_fmi", "_score", "_fraction", "_difference", "_fmi_impact"))
            or key
            in {
                "dossier_component_sum",
                "dossier_scenario_cohort_min",
                "dossier_scenario_cohort_max",
                "baseline_revenue",
                "baseline_unit_multiplier",
            }
            or key.endswith(("_adjustment", "_adjusted_forecast"))
        )
        boolean = key in {"fmi_required", "historical_summary_conflict"}
        unit = (
            "boolean"
            if boolean
            else "fraction"
            if "fraction" in key
            else "currency_times_unit_multiplier"
            if key
            in {
                "baseline_revenue",
                "dossier_scenario_adjustment",
                "dossier_scenario_adjusted_forecast",
                "dossier_scenario_legacy_adjustment",
                "dossier_scenario_legacy_adjusted_forecast",
            }
            else "currency_unit_multiplier"
            if key == "baseline_unit_multiplier"
            else "score_points"
            if "difference" in key or key.endswith("_fmi_impact")
            else "score_0_100"
            if numeric
            else "text"
        )
        fields.append(
            Field(
                key,
                labels.get(key, key.replace("_", " ").capitalize()),
                "Dossier reference",
                "date"
                if key.endswith("_period_end")
                else "boolean"
                if boolean
                else "number"
                if numeric
                else "string",
                unit,
                descriptions.get(
                    key,
                    key.replace("_", " ").capitalize()
                    + ": archived reference/new scenario; never a source override.",
                ),
                "Report text/tables; source path and SHA256 retained.",
            ).record()
        )
    return {
        "kind": "flat-delivery",
        "sheets": [
            {
                "name": "Dossier reference",
                "keys": keys,
                "labels": [f["excel_label"] for f in fields],
                "fields": fields,
                "rows": [{k: r.get(k) for k in keys} for r in rows],
            }
        ],
    }
