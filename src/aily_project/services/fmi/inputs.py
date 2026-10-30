"""Excel-only review inputs; never accept manually entered measurements."""

import csv
import re
import unicodedata
from dataclasses import fields
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

from .models import Inputs, Row, Snapshot, calendar_date, instant, truth

SHEETS = {
    "Entities": (
        "entities",
        "entity_id name prospect aliases light_code ticker shared_symbol "
        "financial_subject scope proxy proxy_label handle profile_id "
        "mapping_approved evidence",
    ),
    "Peers": (
        "peers",
        "analysis_id peer_entity_id approved comparable rationale limitations evidence",
    ),
    "Analyses": (
        "analyses",
        "analysis_id entity_id route collection show_date timezone cutoff "
        "current_start current_end baseline_start baseline_end headline selected "
        "reviewed financial_comparable social_coverage_reviewed "
        "forecast_alignment_reviewed forecast_target_label forecast_target_start "
        "forecast_target_end evidence",
    ),
    "Financial review": (
        "financial_review",
        "analysis_id entity_id role metric source_row_id approved scope currency "
        "unit_multiplier period_label period_start period_end period_type "
        "aggregation_definition evidence",
    ),
    "Post review": ("post_review", "analysis_id post_key reviewed relevant evidence"),
}


def key(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def read_inputs(path: Path) -> Inputs:
    book = load_workbook(path, read_only=True, data_only=False)
    result = Inputs()
    try:
        for sheet, (attr, column_text) in SHEETS.items():
            if sheet not in book.sheetnames:
                raise ValueError(f"Missing input sheet: {sheet}")
            rows = iter(book[sheet].values)
            headers = next(rows)
            expected = column_text.split()
            if list(headers) != expected:
                raise ValueError(f"{sheet}: expected exact field keys {expected}")
            records = []
            for row in rows:
                if any(value is not None for value in row):
                    if any(isinstance(v, str) and v.startswith("=") for v in row):
                        raise ValueError(f"{sheet}: input formulas are not supported")
                    records.append(dict(zip(expected, row, strict=True)))
            setattr(result, attr, records)
    finally:
        book.close()
    validate_inputs(result)
    return result


def validate_inputs(inputs: Inputs) -> None:
    for records, columns in (
        (inputs.entities, ("entity_id",)),
        (inputs.analyses, ("analysis_id",)),
        (inputs.peers, ("analysis_id", "peer_entity_id")),
        (inputs.financial_review, ("analysis_id", "entity_id", "role", "metric")),
        (inputs.post_review, ("analysis_id", "post_key")),
    ):
        seen = set()
        for row in records:
            ident = tuple(row.get(c) for c in columns)
            if any(not v for v in ident) or ident in seen:
                raise ValueError(f"Missing or duplicate input key: {columns} {ident}")
            seen.add(ident)
    entities = {r["entity_id"] for r in inputs.entities}
    analyses = {r["analysis_id"]: r for r in inputs.analyses}
    for row in inputs.analyses:
        if row["entity_id"] not in entities:
            raise ValueError("Analysis refers to unknown entity")
    for row in inputs.peers:
        if row["analysis_id"] not in analyses or row["peer_entity_id"] not in entities:
            raise ValueError("Peer refers to unknown analysis/entity")
        if row["peer_entity_id"] == analyses[row["analysis_id"]]["entity_id"]:
            raise ValueError("A prospect cannot be its own peer")
    for row in inputs.financial_review:
        if row["analysis_id"] not in analyses or row["entity_id"] not in entities:
            raise ValueError("Financial review refers to unknown analysis/entity")
    for row in inputs.post_review:
        if row["analysis_id"] not in analyses:
            raise ValueError("Post review refers to unknown analysis")
    for entity in entities:
        selected = [
            a
            for a in inputs.analyses
            if a["entity_id"] == entity and truth(a.get("selected"))
        ]
        if len(selected) > 1:
            raise ValueError(f"More than one selected headline: {entity}")


def merge_reviews(fresh: Inputs, existing: Inputs) -> Inputs:
    """Existing decisions, including intentional blanks, win; retain extra rows."""
    keys = {
        "entities": ("entity_id",),
        "analyses": ("analysis_id",),
        "peers": ("analysis_id", "peer_entity_id"),
        "financial_review": ("analysis_id", "entity_id", "role", "metric"),
        "post_review": ("analysis_id", "post_key"),
    }
    for attr, columns in keys.items():
        index = {tuple(r[c] for c in columns): r for r in getattr(fresh, attr)}
        for row in getattr(existing, attr):
            index[tuple(row[c] for c in columns)] = row
        setattr(fresh, attr, list(index.values()))
    validate_inputs(fresh)
    return fresh


def seed_inputs(prospects: Path, legacy: Path | None = None) -> Inputs:
    book = load_workbook(prospects, read_only=True, data_only=True)
    rows = list(book.active.values)[1:]
    book.close()
    result = Inputs()
    entities: dict[str, Row] = {}
    for name, peer1, peer2 in rows:
        ident = key(str(name))
        analysis_id = ident + "-headline"
        for member in (name, peer1, peer2):
            if member:
                eid = key(str(member))
                if eid not in entities:
                    entities[eid] = {
                        "entity_id": eid,
                        "name": member,
                        "prospect": False,
                        "mapping_approved": False,
                        "evidence": str(prospects),
                    }
        entities[ident]["prospect"] = True
        result.analyses.append(
            {
                "analysis_id": analysis_id,
                "entity_id": ident,
                "headline": True,
                "selected": True,
                "reviewed": False,
            }
        )
        for peer in (peer1, peer2):
            if peer:
                result.peers.append(
                    {
                        "analysis_id": analysis_id,
                        "peer_entity_id": key(str(peer)),
                        "approved": False,
                        "comparable": False,
                        "evidence": str(prospects),
                    }
                )
    shows = {
        "chanel": ("2025-10-06", "Europe/Paris", "chanelofficial"),
        "christian-dior": ("2025-10-01", "Europe/Paris", "dior"),
        "etro": ("2025-09-24", "Europe/Rome", "etro"),
        "hermes": ("2025-10-04", "Europe/Paris", "hermes"),
        "prada": ("2025-09-25", "Europe/Rome", "prada"),
        "valentino": ("2025-10-05", "Europe/Paris", "maisonvalentino"),
        "michael-kors": ("2025-09-11", "America/New_York", "michaelkors"),
        "tory-burch": ("2025-09-15", "America/New_York", "toryburch"),
        "the-row": ("2025-10-02", "Europe/Paris", "therow"),
    }
    for a in result.analyses:
        if a["entity_id"] in shows:
            show, zone, handle = shows[a["entity_id"]]
            a.update(
                route="show",
                collection="SS2026",
                show_date=show,
                timezone=zone,
                evidence="New prospects info brand report; date requires review",
            )
            entities[a["entity_id"]]["handle"] = handle
    for eid, handle in {"kate-spade": "katespadeny", "rag-bone": "ragandbone"}.items():
        if eid in entities:
            entities[eid]["handle"] = handle
    # One-time migration preserves CSV decisions as proposals, never source amounts.
    if legacy:
        path = legacy / "entities.csv"
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    eid = key(row["entity"].replace("_", " "))
                    if eid in entities:
                        entities[eid]["light_code"] = row.get("company_code")
                        entities[eid]["evidence"] = f"Migrated candidate from {path}"
        path = legacy / "analyses.csv"
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream):
                    eid = key(row["brand"])
                    analysis = next(
                        (a for a in result.analyses if a["entity_id"] == eid), None
                    )
                    if analysis:
                        for column in ("route", "show_date", "timezone", "collection"):
                            analysis[column] = row.get(column)
                        entities[eid]["handle"] = row.get("handle")
                        analysis["evidence"] = (
                            f"Migrated from {path}; "
                            "strict cutoff replaces retrospective as_of"
                        )
    result.entities = list(entities.values())
    for a in result.analyses:
        members = [a["entity_id"]] + [
            p["peer_entity_id"]
            for p in result.peers
            if p["analysis_id"] == a["analysis_id"]
        ]
        for eid in members:
            for role in ("oldest", "earlier", "latest"):
                result.financial_review.append(
                    {
                        "analysis_id": a["analysis_id"],
                        "entity_id": eid,
                        "role": role,
                        "metric": "revenue",
                        "approved": False,
                    }
                )
        for role in ("baseline", "prior_actual"):
            result.financial_review.append(
                {
                    "analysis_id": a["analysis_id"],
                    "entity_id": a["entity_id"],
                    "role": role,
                    "metric": "revenue",
                    "approved": False,
                }
            )
    validate_inputs(result)
    return result


def as_dict(inputs: Inputs) -> dict[str, list[Row]]:
    return {f.name: getattr(inputs, f.name) for f in fields(inputs)}


def propose_mappings(inputs: Inputs, snapshot: Snapshot) -> Inputs:
    """Fill only empty candidate cells; approvals and reviewed rows never change."""
    proposals = snapshot.metadata.get("candidate_mappings", [])
    symbols = {r.get("symbol") for r in snapshot.financials}
    for entity in inputs.entities:
        if truth(entity.get("mapping_approved")):
            continue
        matches = [r for r in proposals if r["entity_id"] == entity["entity_id"]]
        if len(matches) != 1:
            continue
        row = matches[0]
        if not entity.get("light_code"):
            entity["light_code"] = row.get("company_code")
        if not entity.get("ticker"):
            entity["ticker"] = row.get("company_ticker")
        if not entity.get("shared_symbol"):
            ticker, code = row.get("company_ticker"), row.get("company_code")
            entity["shared_symbol"] = (
                ticker if ticker in symbols else code if code in symbols else None
            )
    for entity in inputs.entities:
        if (
            truth(entity.get("mapping_approved"))
            or entity.get("profile_id")
            or not entity.get("handle")
        ):
            continue
        ids = {
            str(r["profile_id"])
            for r in snapshot.posts + snapshot.profiles
            if r.get("profile_id")
            and str(r.get("profile_username", "")).lower()
            == str(entity["handle"]).lower()
        }
        if len(ids) == 1:
            entity["profile_id"] = ids.pop()
    return inputs


def propose_post_reviews(inputs: Inputs, snapshot: Snapshot) -> Inputs:
    """Eligible window posts become review tasks, not approved measurements."""
    from datetime import timedelta

    from .scoring import cutoff_for
    from .social import observations, post_key

    entities = {e["entity_id"]: e for e in inputs.entities}
    existing = {(r["analysis_id"], r["post_key"]) for r in inputs.post_review}
    for analysis in inputs.analyses:
        cutoff = cutoff_for(analysis)
        entity = entities[analysis["entity_id"]]
        if not cutoff or not entity.get("handle"):
            continue
        source = [
            r
            for r in snapshot.posts
            if str(r.get("profile_username", "")).lower()
            == str(entity["handle"]).lower()
        ]
        posts, _ = observations(source, cutoff)
        zone = ZoneInfo(analysis["timezone"])
        if analysis.get("route") == "show":
            show = calendar_date(analysis["show_date"])
            start, end = show - timedelta(days=30), show + timedelta(days=37)
        elif analysis.get("route") == "annual" and all(
            analysis.get(k) for k in ("baseline_start", "current_end")
        ):
            start, end = (
                calendar_date(analysis["baseline_start"]),
                calendar_date(analysis["current_end"]),
            )
        else:
            continue
        for post in posts:
            stamp = instant(post.get("date_posted"))
            ident = post_key(post)
            if (
                stamp is None
                or ident is None
                or not start <= stamp.astimezone(zone).date() <= end
            ):
                continue
            record_key = (analysis["analysis_id"], ident)
            if record_key not in existing:
                inputs.post_review.append(
                    {
                        "analysis_id": analysis["analysis_id"],
                        "post_key": ident,
                        "reviewed": False,
                        "relevant": False,
                        "evidence": post.get("post_url"),
                    }
                )
                existing.add(record_key)
    return inputs
