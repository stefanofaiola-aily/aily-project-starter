"""Small editable brand configuration; source/review records live separately."""

import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import yaml

from .inputs import SHEETS, validate_inputs
from .models import Inputs, Row, calendar_date, clean, fingerprint, show_cutoff, truth

SCHEMA = "fmi-input-v2"
REVIEW_SCHEMA = "fmi-review-v1"
ENTITY_KEYS = {
    "id": "entity_id",
    "name": "name",
    "light_code": "light_code",
    "ticker": "ticker",
    "shared_symbol": "shared_symbol",
    "instagram": "handle",
    "profile_id": "profile_id",
    "financial_subject": "financial_subject",
    "scope": "scope",
    "proxy": "proxy",
    "proxy_label": "proxy_label",
    "aliases": "aliases",
    "required": "fmi_required",
    "category": "event_category",
    "invited": "event_invited",
    "parent": "parent",
    "proxy_authorized": "proxy_authorized",
    "financial_comparability_evidence": "financial_comparability_evidence",
}
ANALYSIS_KEYS = {
    "id": "analysis_id",
    **{
        k: k
        for k in (
            "route",
            "collection",
            "show_date",
            "timezone",
            "cutoff",
            "current_start",
            "current_end",
            "baseline_start",
            "baseline_end",
            "headline",
            "selected",
            "common_months_only",
            "dossier",
        )
    },
}
FORECAST_KEYS = {
    "label": "forecast_target_label",
    "start": "forecast_target_start",
    "end": "forecast_target_end",
}
ENTITY_REVIEWS = {"entity_id", "mapping_approved", "evidence", "event_names"}
ANALYSIS_REVIEWS = {
    "analysis_id",
    "reviewed",
    "financial_comparable",
    "social_coverage_reviewed",
    "forecast_alignment_reviewed",
    "evidence",
}


def sparse(row: Row) -> Row:
    """Keep deliberate false/zero values; remove only nulls and empty strings."""
    return {k: clean(v) for k, v in row.items() if v is not None and v != ""}


def check_keys(row: Row, allowed: set[str], label: str) -> None:
    if not isinstance(row, dict):
        raise ValueError(f"{label} must be an object")
    unknown = set(row) - allowed
    if unknown:
        raise ValueError(f"{label}: unknown fields {sorted(unknown)}")


def read_reference(path: Path, name: str) -> Path:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Input references must be nonempty local file paths")
    target = path.parent / name
    if not target.is_file():
        raise ValueError(f"Missing input companion: {target}")
    return target


def policy_overrides(path: Path, data: Row) -> Row:
    if not data.get("policy_file"):
        return {}
    overrides = yaml.safe_load(read_reference(path, data["policy_file"]).read_text())
    if not isinstance(overrides, dict):
        raise ValueError("The policy YAML must contain a parameter mapping")
    return overrides


def materialize(data: Row) -> Inputs:
    """Derive boilerplate IDs/windows; never infer approvals or measurements."""
    check_keys(
        data,
        {
            "schema_version",
            "policy_file",
            "review_file",
            "query",
            "forecast",
            "mode",
            "financial_basis",
            "headline_method",
            "brands",
            "peer_entities",
        },
        "Inputs",
    )
    mode = data.get("mode", "strict_replay")
    headline_method = data.get("headline_method", "dossier_reference")
    if headline_method not in {"dossier_reference", "weighted_components"}:
        raise ValueError(
            "Headline method must be dossier_reference or weighted_components"
        )
    if mode not in {"strict_replay", "presentation", "dossier"}:
        raise ValueError("Mode must be strict_replay, presentation or dossier")
    basis = data.get("financial_basis", "target_season")
    if basis not in {"target_season", "latest_available", "dossier"}:
        raise ValueError(
            "Financial basis must be target_season, latest_available or dossier"
        )
    if (mode == "dossier") != (basis == "dossier"):
        raise ValueError(
            "Dossier mode requires dossier financial basis, never latest_available"
        )
    if mode == "strict_replay" and basis != "target_season":
        raise ValueError("Latest available financials are only for presentation mode")
    default_forecast = data.get("forecast", {})
    check_keys(default_forecast, set(FORECAST_KEYS), "Default forecast target")
    if default_forecast and not all(default_forecast.get(k) for k in FORECAST_KEYS):
        raise ValueError("Forecast target requires label, start and end")
    result = Inputs()
    for prospect, rows in (
        (True, data.get("brands", [])),
        (False, data.get("peer_entities", [])),
    ):
        if not isinstance(rows, list):
            raise ValueError("Brands and peer_entities must be arrays")
        for item in rows:
            allowed = set(ENTITY_KEYS) | (
                {"analysis", "peers", "forecast", "financial_periods", "review"}
                if prospect
                else {"review"}
            )
            check_keys(item, allowed, "Brand" if prospect else "Peer entity")
            if not item.get("id") or not item.get("name"):
                raise ValueError("Every entity needs a stable id and name")
            entity = {ENTITY_KEYS[k]: v for k, v in item.items() if k in ENTITY_KEYS}
            if "parent" in item:
                parent = item["parent"]
                check_keys(
                    parent,
                    {
                        "name",
                        "light_code",
                        "ticker",
                        "shared_symbol",
                        "evidence",
                        "authorized",
                        "prefer",
                    },
                    "Parent fallback",
                )
                if not parent.get("name") or not parent.get("evidence"):
                    raise ValueError(
                        "Parent fallback requires a name and ownership evidence"
                    )
            entity.update(prospect=prospect, mapping_approved=False)
            result.entities.append(entity)
            if not prospect:
                continue
            settings = item.get("analysis", {})
            check_keys(settings, set(ANALYSIS_KEYS), "Analysis")
            if settings.get("route") == "show" and any(
                k in settings
                for k in (
                    "cutoff",
                    "current_start",
                    "current_end",
                    "baseline_start",
                    "baseline_end",
                )
            ):
                raise ValueError(
                    "Show cutoff/windows are derived; edit show_date/timezone"
                )
            analysis = {ANALYSIS_KEYS[k]: v for k, v in settings.items()}
            analysis.setdefault("analysis_id", item["id"] + "-headline")
            analysis.setdefault("headline", True)
            analysis.setdefault("selected", True)
            analysis.update(entity_id=item["id"], reviewed=False)
            analysis["calculation_mode"] = mode
            analysis["financial_basis"] = basis
            analysis["headline_method"] = headline_method
            if mode == "dossier":
                from .dossier_inputs import validate_method

                method = analysis.get("dossier")
                if not isinstance(method, dict):
                    raise ValueError(
                        "Dossier mode requires explicit per-brand dossier parameters"
                    )
                validate_method(
                    method,
                    {
                        e["id"]
                        for e in [
                            *data.get("brands", []),
                            *data.get("peer_entities", []),
                        ]
                    },
                )
            if (
                analysis.get("route") == "show"
                and analysis.get("show_date")
                and analysis.get("timezone")
            ):
                day = calendar_date(analysis["show_date"])
                analysis.update(
                    show_date=day.isoformat(),
                    cutoff=show_cutoff(day, analysis["timezone"]).isoformat(),
                    current_start=day.isoformat(),
                    current_end=(day + timedelta(days=7)).isoformat(),
                    baseline_start=(day - timedelta(days=30)).isoformat(),
                    baseline_end=(day + timedelta(days=37)).isoformat(),
                )
                if mode == "dossier":
                    options = analysis["dossier"].get("social", {})
                    analysis.update(
                        baseline_start=(
                            day - timedelta(days=int(options.get("baseline_days", 15)))
                        ).isoformat(),
                        baseline_end=(day - timedelta(days=1)).isoformat(),
                        current_end=(
                            day + timedelta(days=int(options.get("current_days", 7)))
                        ).isoformat(),
                    )
            override = item.get("forecast", {})
            check_keys(override, set(FORECAST_KEYS), "Forecast target")
            forecast = {**default_forecast, **override}
            if (
                forecast.get("start")
                and forecast.get("end")
                and calendar_date(forecast["start"]) > calendar_date(forecast["end"])
            ):
                raise ValueError("Forecast target start must precede end")
            analysis.update({FORECAST_KEYS[k]: v for k, v in forecast.items()})
            result.analyses.append(analysis)
            aid = analysis["analysis_id"]
            peers = item.get("peers", [])
            if not isinstance(peers, list) or any(
                not isinstance(p, str) or not p for p in peers
            ):
                raise ValueError("Peers must be an array of stable entity IDs")
            result.peers.extend(
                {
                    "analysis_id": aid,
                    "peer_entity_id": p,
                    "approved": False,
                    "comparable": False,
                }
                for p in peers
            )
            preferences = item.get("financial_periods", {})
            check_keys(
                preferences, {"oldest", "earlier", "latest"}, "Financial periods"
            )
            if any(
                not isinstance(v, str) or not v.strip() for v in preferences.values()
            ):
                raise ValueError("Financial periods are explicit labels, never amounts")
            for eid in (item["id"], *peers):
                for role in ("oldest", "earlier", "latest"):
                    row = {
                        "analysis_id": aid,
                        "entity_id": eid,
                        "role": role,
                        "metric": "revenue",
                        "approved": False,
                    }
                    if eid == item["id"] and role in preferences:
                        row["period_label"] = preferences[role]
                    result.financial_review.append(row)
            result.financial_review.extend(
                {
                    "analysis_id": aid,
                    "entity_id": item["id"],
                    "role": role,
                    "metric": "revenue",
                    "approved": False,
                }
                for role in ("baseline", "prior_actual")
            )
    validate_inputs(result)
    return result


def bindings(data: Row, inputs: Inputs) -> Row:
    entities = {
        e["entity_id"]: sparse(
            {
                k: v
                for k, v in e.items()
                if k
                not in {
                    "mapping_approved",
                    "prospect",
                    "fmi_required",
                    "event_category",
                    "event_invited",
                }
            }
        )
        for e in inputs.entities
    }
    periods = {b["id"]: b.get("financial_periods", {}) for b in data.get("brands", [])}
    analyses = {}
    for a in inputs.analyses:
        peers = sorted(
            p["peer_entity_id"]
            for p in inputs.peers
            if p["analysis_id"] == a["analysis_id"]
        )
        analyses[a["analysis_id"]] = fingerprint(
            {
                "analysis": a,
                "entities": [entities[eid] for eid in (a["entity_id"], *peers)],
                "peers": peers,
                "financial_periods": periods.get(a["entity_id"], {}),
            }
        )
    return {
        "entities": {eid: fingerprint(e) for eid, e in entities.items()},
        "analyses": analyses,
    }


def inline_reviews(inputs: Inputs, data: Row) -> Inputs:
    """Optional sparse decisions beside a brand, never generated placeholder rows."""
    entities = {e["entity_id"]: e for e in inputs.entities}
    analyses = {a["entity_id"]: a for a in inputs.analyses}
    for item in [*data.get("brands", []), *data.get("peer_entities", [])]:
        review = item.get("review", {})
        check_keys(
            review, {"identity", "analysis", "peers", "financial", "posts"}, "Review"
        )
        for section in ("peers", "financial", "posts"):
            if not isinstance(review.get(section, {}), dict):
                raise ValueError(f"Review {section} must be an object")
        identity = review.get("identity", {})
        check_keys(
            identity, ENTITY_REVIEWS - {"entity_id", "event_names"}, "Identity review"
        )
        entities[item["id"]].update(identity)
        if not any(k in review for k in ("analysis", "peers", "financial", "posts")):
            continue
        if item["id"] not in analyses:
            raise ValueError("Peer-only entities can only declare identity review")
        analysis = analyses[item["id"]]
        aid = analysis["analysis_id"]
        settings = review.get("analysis", {})
        check_keys(settings, ANALYSIS_REVIEWS - {"analysis_id"}, "Analysis review")
        analysis.update(settings)
        members = {item["id"], *item.get("peers", [])}
        for eid, decision in review.get("peers", {}).items():
            edge = next(
                (
                    p
                    for p in inputs.peers
                    if p["analysis_id"] == aid and p["peer_entity_id"] == eid
                ),
                None,
            )
            if edge is None:
                raise ValueError("Reviewed peer must be assigned to this brand")
            check_keys(decision, {"approved", "comparable", "evidence"}, "Peer review")
            edge.update(decision)
        for eid, selections in review.get("financial", {}).items():
            if not isinstance(selections, dict):
                raise ValueError("Financial selections must be an object")
            if eid not in members:
                raise ValueError(
                    "Financial selection must belong to brand or its peers"
                )
            for role, selection in selections.items():
                if role not in {
                    "oldest",
                    "earlier",
                    "latest",
                    "baseline",
                    "prior_actual",
                }:
                    raise ValueError("Unknown financial selection role")
                check_keys(
                    selection,
                    set(SHEETS["Financial review"][1].split())
                    - {"analysis_id", "entity_id", "role", "metric"},
                    "Financial selection",
                )
                match = next(
                    (
                        r
                        for r in inputs.financial_review
                        if r["analysis_id"] == aid
                        and r["entity_id"] == eid
                        and r["role"] == role
                    ),
                    None,
                )
                if match is None:
                    raise ValueError(
                        "Forecast selections belong to the brand, not peers"
                    )
                requested = match.get("period_label")
                if requested and selection.get("period_label", requested) != requested:
                    raise ValueError(
                        "Financial selection conflicts with requested period"
                    )
                match.update(selection)
        for post_key, decision in review.get("posts", {}).items():
            check_keys(decision, {"reviewed", "relevant", "evidence"}, "Post review")
            inputs.post_review.append(
                {"analysis_id": aid, "post_key": post_key, **decision}
            )
    validate_inputs(inputs)
    return inputs


def read_compact(path: Path, data: Row) -> Inputs:
    inputs = materialize(data)
    if not data.get("review_file"):
        return inline_reviews(inputs, data)
    if any(
        "review" in item
        for item in [*data.get("brands", []), *data.get("peer_entities", [])]
    ):
        raise ValueError("Use inline decisions or the legacy review file, not both")
    reviews = json.loads(read_reference(path, data["review_file"]).read_text())
    check_keys(
        reviews,
        {
            "schema_version",
            "bindings",
            "entity_reviews",
            "analysis_reviews",
            "peer_reviews",
            "financial_selection",
            "post_review",
            "evidence",
        },
        "Reviews",
    )
    if reviews.get("schema_version") != REVIEW_SCHEMA:
        raise ValueError(f"Expected review schema {REVIEW_SCHEMA}")
    current, recorded = bindings(data, inputs), reviews.get("bindings", {})
    entities = {e["entity_id"]: e for e in inputs.entities}
    analyses = {a["analysis_id"]: a for a in inputs.analyses}
    peers = {(p["analysis_id"], p["peer_entity_id"]): p for p in inputs.peers}
    financials = {
        (r["analysis_id"], r["entity_id"], r["role"], r["metric"]): r
        for r in inputs.financial_review
    }
    for section, allowed in (
        ("entity_reviews", ENTITY_REVIEWS),
        ("analysis_reviews", ANALYSIS_REVIEWS),
        ("peer_reviews", set(SHEETS["Peers"][1].split())),
        ("financial_selection", set(SHEETS["Financial review"][1].split())),
        ("post_review", set(SHEETS["Post review"][1].split())),
    ):
        seen = set()
        for row in reviews.get(section, []):
            check_keys(row, allowed, section)
            columns = (
                ("entity_id",)
                if section == "entity_reviews"
                else ("analysis_id",)
                if section == "analysis_reviews"
                else ("analysis_id", "peer_entity_id")
                if section == "peer_reviews"
                else ("analysis_id", "entity_id", "role", "metric")
                if section == "financial_selection"
                else ("analysis_id", "post_key")
            )
            ident = tuple(row.get(k) for k in columns)
            if any(not k for k in ident) or ident in seen:
                raise ValueError(f"Missing or duplicate review key: {section} {ident}")
            seen.add(ident)
            if section == "entity_reviews":
                eid = row["entity_id"]
                if eid in entities and current["entities"].get(eid) == recorded.get(
                    "entities", {}
                ).get(eid):
                    entities[eid].update(row)
                continue
            aid = row["analysis_id"]
            if aid not in analyses or current["analyses"].get(aid) != recorded.get(
                "analyses", {}
            ).get(aid):
                continue  # Preserve stale decisions in the file; never reuse approval.
            if section == "analysis_reviews":
                analyses[aid].update(row)
            elif section == "peer_reviews":
                ident = (aid, row["peer_entity_id"])
                if ident in peers:
                    peers[ident].update(row)
            elif section == "financial_selection":
                ident = (aid, row["entity_id"], row["role"], row["metric"])
                if row["entity_id"] not in {
                    analyses[aid]["entity_id"],
                    *(
                        p["peer_entity_id"]
                        for p in inputs.peers
                        if p["analysis_id"] == aid
                    ),
                }:
                    if truth(row.get("approved")):
                        raise ValueError(
                            "Financial selection is not a member of its analysis"
                        )
                    continue
                requested = financials.get(ident, {}).get("period_label")
                if (
                    truth(row.get("approved"))
                    and requested
                    and row.get("period_label")
                    and row["period_label"] != requested
                ):
                    raise ValueError(
                        "Reviewed source label conflicts with "
                        "requested financial period"
                    )
                financials[ident] = {**financials.get(ident, {}), **row}
            else:
                inputs.post_review.append(deepcopy(row))
    inputs.financial_review = list(financials.values())
    validate_inputs(inputs)
    return inputs


def split_document(data: Row) -> tuple[Row, Row, Row]:
    """Lossless review migration from the verbose schema, not a re-approval."""

    def entity(row: Row) -> Row:
        result = sparse({k: row.get(v) for k, v in ENTITY_KEYS.items()})
        if result.get("proxy") is False:
            result.pop("proxy")
        return result

    config: Row = {
        "schema_version": SCHEMA,
        "query": data["query"],
        "brands": [],
        "peer_entities": [entity(e) for e in data.get("peer_entities", [])],
    }
    reviews: Row = {
        "schema_version": REVIEW_SCHEMA,
        "entity_reviews": [],
        "analysis_reviews": [],
        "peer_reviews": [],
        "financial_selection": [],
        "post_review": [],
        "evidence": {
            "source_files": data.get("source_files", []),
            "report_parameters": {},
        },
    }
    for row in [
        *(b["identity"] for b in data["brands"]),
        *data.get("peer_entities", []),
    ]:
        reviews["entity_reviews"].append(
            sparse({k: row.get(k) for k in ENTITY_REVIEWS})
        )
    for brand in data["brands"]:
        if len(brand["analyses"]) != 1:
            raise ValueError(
                "Compact inputs require one analysis per brand; "
                "keep v1 for multiple analyses"
            )
        block = brand["analyses"][0]
        a = block["settings"]
        record = entity(brand["identity"])
        settings = sparse({k: a.get(v) for k, v in ANALYSIS_KEYS.items()})
        if settings.get("id") == record["id"] + "-headline":
            settings.pop("id")
        for k in ("selected", "headline"):
            if settings.get(k) is True:
                settings.pop(k)
        if settings.get("show_date"):
            settings["show_date"] = calendar_date(settings["show_date"]).isoformat()
        if settings.get("route") == "show":
            for k in (
                "cutoff",
                "current_start",
                "current_end",
                "baseline_start",
                "baseline_end",
            ):
                settings.pop(k, None)
        record.update(
            peers=[p["peer_entity_id"] for p in block["peers"]], analysis=settings
        )
        target = sparse({k: a.get(v) for k, v in FORECAST_KEYS.items()})
        if target:
            record["forecast"] = target
        preferences = sparse(
            {
                r["role"]: r.get("period_label")
                for r in block["financial_selection"]
                if r["entity_id"] == record["id"]
                and r["metric"] == "revenue"
                and r["role"] in {"oldest", "earlier", "latest"}
            }
        )
        if preferences:
            record["financial_periods"] = preferences
        config["brands"].append(record)
        reviews["analysis_reviews"].append(
            sparse({k: a.get(k) for k in ANALYSIS_REVIEWS})
        )
        reviews["peer_reviews"].extend(sparse(p) for p in block["peers"])
        reviews["financial_selection"].extend(
            sparse(r) for r in block["financial_selection"]
        )
        reviews["post_review"].extend(sparse(r) for r in block["post_review"])
        if brand.get("report_parameters"):
            reviews["evidence"]["report_parameters"][record["id"]] = brand[
                "report_parameters"
            ]
    reviews["bindings"] = bindings(config, materialize(config))
    return config, reviews, data["policy"]


def write_bundle(data: Row, output: Path) -> None:
    """Write fresh config/review/policy companions; never overwrite decisions."""
    from .policy import Policy

    config, reviews, policy = split_document(data)
    Policy.model_validate(policy)
    prefix = "FMI" if output.stem == "FMI_inputs" else output.stem
    review_path = output.with_name(prefix + "_reviews.json")
    policy_path = output.with_name(prefix + "_policy.yaml")
    for target in (output, review_path, policy_path):
        if target.exists():
            raise ValueError(
                f"Input already exists: {target}; choose a new bundle path"
            )
    config.update(review_file=review_path.name, policy_file=policy_path.name)
    output.parent.mkdir(parents=True, exist_ok=True)
    for target, content in ((output, config), (review_path, reviews)):
        target.write_text(
            json.dumps(clean(content), indent=2, ensure_ascii=False, allow_nan=False)
            + "\n"
        )
    policy_path.write_text(yaml.safe_dump(policy, sort_keys=False))


def refresh_reviews(path: Path, data: Row, output: Path) -> list[str]:
    """Keep selections, reset stale approvals and bind a NEW review proposal."""
    if output.exists():
        raise ValueError(
            "Review output exists; choose a new path to preserve decisions"
        )
    reviews = json.loads(read_reference(path, data["review_file"]).read_text())
    read_compact(path, data)
    current = bindings(data, materialize(data))
    previous = reviews.get("bindings", {})
    stale = {
        k
        for k, v in current["analyses"].items()
        if previous.get("analyses", {}).get(k) != v
    }
    for row in reviews.get("entity_reviews", []):
        eid = row["entity_id"]
        if current["entities"].get(eid) != previous.get("entities", {}).get(eid):
            row["mapping_approved"] = False
    for section, flags in (
        (
            "analysis_reviews",
            (
                "reviewed",
                "financial_comparable",
                "social_coverage_reviewed",
                "forecast_alignment_reviewed",
            ),
        ),
        ("peer_reviews", ("approved", "comparable")),
        ("financial_selection", ("approved",)),
        ("post_review", ("reviewed",)),
    ):
        for row in reviews.get(section, []):
            if row["analysis_id"] in stale:
                row.update(dict.fromkeys(flags, False))
    reviews["bindings"] = current
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(reviews, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )
    return sorted(stale)
