"""Read identity/date evidence from reports, never import their measurements."""

import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .inputs import key, validate_inputs
from .models import Inputs, Row, truth

WORD = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def compact(value: str) -> str:
    return key(value).replace("-", "")


def names(value: str) -> set[str]:
    """Punctuation/legal suffix variants, not fuzzy brand-to-parent matching."""
    basic = key(value)
    short = re.sub(r"-(inc|incorporated|llc|ltd|limited|plc|spa|co|corp)$", "", basic)
    return {compact(basic), compact(short)}


def report_date(value: str) -> str | None:
    for pattern in ("%Y-%m-%d", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value.strip(), pattern).date().isoformat()
        except ValueError:
            pass
    return None


def read_reports(root: Path) -> list[Row]:
    reports = []
    for path in sorted(root.rglob("*.docx")):
        if not any(x in str(path) for x in ("02_Brand_reports", "New prospects info")):
            continue
        with ZipFile(path) as archive:
            doc = ET.fromstring(archive.read("word/document.xml"))

            def text(node: ET.Element) -> str:
                return "".join(t.text or "" for t in node.findall(".//w:t", WORD))

            paragraphs = [text(p) for p in doc.findall(".//w:p", WORD)]
            links = []
            if "word/_rels/document.xml.rels" in archive.namelist():
                rels = ET.fromstring(archive.read("word/_rels/document.xml.rels"))
                links = [
                    r.attrib["Target"]
                    for r in rels
                    if r.attrib.get("TargetMode") == "External"
                ]
            handles = set()
            preferred_handles = set()
            for p in paragraphs:
                for match in re.finditer(r"@([A-Za-z0-9_.]+)", p):
                    handle = re.split(r"FY\d", match[1])[0].rstrip(".").lower()
                    handles.add(handle)
                    if re.search(r"^(?:Instagram account|Account:)\s*@", p):
                        preferred_handles.add(handle)
                for match in re.finditer(r"account handle \(([^)]+)\)", p):
                    handles.add(match[1].lower())
            for value in links + paragraphs:
                for match in re.finditer(r"instagram\.com/([A-Za-z0-9_.]+)", value):
                    if match[1].lower() not in {"p", "reel", "reels", "stories"}:
                        handles.add(match[1].lower())
            shows = []
            for table in doc.findall(".//w:tbl", WORD):
                rows = [
                    [text(c) for c in r.findall("w:tc", WORD)]
                    for r in table.findall("w:tr", WORD)
                ]
                if not rows:
                    continue
                headings = rows[0]
                date_col = next(
                    (
                        i
                        for i, h in enumerate(headings)
                        if h.lower() in {"show date", "event date"}
                    ),
                    None,
                )
                if date_col is not None:
                    for row in rows[1:]:
                        day = (
                            report_date(row[date_col]) if len(row) > date_col else None
                        )
                        if day:
                            shows.append(
                                {
                                    "collection": row[0],
                                    "show_date": day,
                                    "evidence": str(path),
                                }
                            )
            stem = path.stem.split("_momentum")[0].split("_show")[0].split("_fiscal")[0]
            report_name = path.parent.name if "02_Brand_reports" in str(path) else stem
            reports.append(
                {
                    "report_name": report_name,
                    "path": str(path),
                    "title": paragraphs[0] if paragraphs else None,
                    "handles": sorted(handles),
                    "preferred_handles": sorted(preferred_handles),
                    "shows": shows,
                    "date_evidence": [
                        p
                        for p in paragraphs
                        if re.search(
                            r"show.*(2024|2025|2026)|shown on|show date", p, re.I
                        )
                    ],
                    "timezones": sorted(
                        set(
                            re.findall(
                                r"(?:Europe|America)/[A-Za-z_]+", " ".join(paragraphs)
                            )
                        )
                    ),
                    "scope_evidence": [
                        p
                        for p in paragraphs
                        if re.search(
                            r"scope|standalone|consolidated|group proxy|"
                            r"not.*revenue|private|fiscal",
                            p,
                            re.I,
                        )
                    ][:12],
                    "links": links,
                }
            )
    return reports


def matched_reports(entity: Row, reports: list[Row]) -> list[Row]:
    variants = names(str(entity["name"])) | names(str(entity["entity_id"]))
    aliases = {
        "victorias-secret-co": "victorias_secret",
        "g-iii-apparel-group": "g_iii",
        "global-luxury-retail-group-dba-missoni": "missoni",
        "rag-bone": "rag_and_bone",
        "santoni-spa": "santoni",
        "rachel-zoe-creations": "rachel_zoe_creations",
        "levi-s": "levis",
    }
    if entity["entity_id"] in aliases:
        variants.add(compact(aliases[entity["entity_id"]]))
    return [r for r in reports if compact(r["report_name"]) in variants]


def prepare_candidates(
    inputs: Inputs, data: Row, reports: list[Row]
) -> tuple[Inputs, list[Row]]:
    """Populate evidence-backed proposals; never auto-approve or replace decisions."""
    result = deepcopy(inputs)
    accounts = {
        str(a["profile_username"]).lower().lstrip("@"): a for a in data["accounts"]
    }
    audit = []
    for entity in result.entities:
        refs = matched_reports(entity, reports)
        variants = names(str(entity["name"])) | names(str(entity["entity_id"]))
        registry = [
            r
            for r in data["registry"]
            if any(
                names(str(r.get(c) or "")) & variants
                for c in ("company_name", "company_label", "company_code")
            )
        ]
        if entity["entity_id"] == "levi-s" and not registry:
            # The Light registry explicitly identifies Levi's as an owned brand.
            # Keep the related issuer a labelled proposal, not standalone revenue.
            registry = [
                r
                for r in data["registry"]
                if r.get("company_label") == "Levi Strauss & Co."
            ]
            if len(registry) == 1 and not truth(entity.get("mapping_approved")):
                entity["proxy"] = True
                entity["proxy_label"] = (
                    "Levi Strauss & Co. group candidate, not standalone Levi's"
                )
        if entity.get("light_code"):
            registry = [
                r for r in data["registry"] if r["company_code"] == entity["light_code"]
            ]
        if len(registry) == 1 and not truth(entity.get("mapping_approved")):
            company = registry[0]
            for k, value in (
                ("light_code", company["company_code"]),
                ("ticker", company.get("company_ticker")),
                ("financial_subject", company.get("company_label")),
            ):
                if not entity.get(k):
                    entity[k] = value
        handles = {h for r in refs for h in r["handles"] if h in accounts}
        preferred = {
            h for r in refs for h in r.get("preferred_handles", []) if h in accounts
        }
        exact_handles = {h for h in accounts if compact(h) in variants}
        if entity["entity_id"] == "abercrombie-fitch" and "abercrombie" in accounts:
            exact_handles.add("abercrombie")
        # Explicit report accounts win only when unique. Multi-brand proxy reports
        # do not confer their subsidiaries' accounts on the group.
        proposals = (
            preferred or (handles if len(handles) == 1 else exact_handles) or handles
        )
        if entity.get("handle"):
            proposals = {str(entity["handle"]).lower().lstrip("@")}
        if len(proposals) == 1 and not truth(entity.get("mapping_approved")):
            handle = next(iter(proposals))
            if not entity.get("handle"):
                entity["handle"] = handle
            ids = {
                str(a["profile_id"])
                for a in data["accounts"]
                if str(a["profile_username"]).lower() == handle and a.get("profile_id")
            }
            if len(ids) == 1 and not entity.get("profile_id"):
                entity["profile_id"] = ids.pop()
        audit.append(
            {
                "entity_id": entity["entity_id"],
                "name": entity["name"],
                "prospect": truth(entity.get("prospect")),
                "report_count": len(refs),
                "report_paths": [r["path"] for r in refs],
                "registry_matches": [r["company_code"] for r in registry],
                "light_code": entity.get("light_code"),
                "ticker": entity.get("ticker"),
                "candidate_handles": sorted(proposals),
                "handle": entity.get("handle"),
                "shows": [s for r in refs for s in r["shows"]],
                "scope_clues": [p for r in refs for p in r["scope_evidence"]],
                "identity_status": "candidate_found"
                if len(registry) == 1
                else "no_unique_light_match",
                "social_status": "candidate_found"
                if entity.get("handle") in accounts
                else "no_own_account_in_inventory",
            }
        )
        if refs and not truth(entity.get("mapping_approved")):
            prior = str(entity.get("evidence") or "")
            additions = [r["path"] for r in refs if r["path"] not in prior]
            entity["evidence"] = "; ".join([prior, *additions]).strip("; ")
    validate_inputs(result)
    return result, audit


def candidate_symbols(entity: Row) -> set[str]:
    """Search tokens only. A hit does not establish scope or identity approval."""
    result = {
        compact(str(entity["name"])).upper(),
        compact(str(entity["entity_id"])).upper(),
    }
    result.update(
        compact(a.strip()).upper()
        for a in str(entity.get("aliases") or "").split(";")
        if a.strip()
    )
    result.update(
        str(entity[k])
        for k in ("light_code", "ticker", "shared_symbol")
        if entity.get(k)
    )
    return result
