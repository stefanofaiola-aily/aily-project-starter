"""One-time dossier parameter alignment. Never import report measurements.

Reports own the business method; supporting records supply exact fiscal dates.
The resulting JSON is self-contained and editable, not re-derived on every run.
"""

import json
import re
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path

from .dossiers import report_content
from .handover import matched_reports, names, read_reports
from .inputs import key
from .models import Row

ROLES = ("oldest", "earlier", "latest")
DATE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)")


def dates(text: str) -> list[str]:
    result = DATE.findall(text)
    if result:
        return result
    for match in re.finditer(r"\b(\d{1,2}) (\w+) (20\d{2})\b", text):
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                result.append(datetime.strptime(match[0], fmt).date().isoformat())
                break
            except ValueError:
                continue
    return result


def period(start: str | None, end: str | None, label: str = "") -> Row:
    length = (
        (date.fromisoformat(end) - date.fromisoformat(start)).days
        if start and end
        else None
    )
    return {
        "label": label,
        "start": start,
        "end": end,
        "type": "annual" if length is not None and length > 300 else "quarter",
    }


def match_entity(name: str, entities: list[Row], preferred: list[str]) -> str | None:
    variants = names(re.sub(r"tom ford fashion", "Tom Ford", name, flags=re.I))
    aliases = {
        "Prada Group": "prada",
        "Abercrombie brand": "abercrombie-fitch",
        "Abercrombie brand net sales": "abercrombie-fitch",
        "American Eagle brand": "american-eagle",
        "LVMH consolidated group": "lvmh",
        "Macy’s Inc.": "macys",
        "Adore Beauty": "adore-beauty-group",
    }
    alias = next((v for k, v in aliases.items() if names(k) & variants), None)
    found = [e["id"] for e in entities if names(e["name"]) & variants]
    choices = [eid for eid in preferred if eid in found]
    if len(choices) == 1:
        return choices[0]
    if alias and any(e["id"] == alias for e in entities):
        return alias
    return choices[0] if len(choices) == 1 else found[0] if len(found) == 1 else None


def scope(text: str) -> str | None:
    lower = text.lower()
    if (
        "dtc" in lower and not re.search(r"not dtc|excludes? dtc", lower)
    ) or "retail revenue" in lower:
        return "retail_dtc"
    if "segment" in lower or "brand line" in lower:
        return "brand_segment"
    if "continuing-operation" in lower or "continuing operations" in lower:
        return "continuing_operations"
    if "consolidated" in lower or "group revenue" in lower or "parent-unit" in lower:
        return "consolidated"
    if "standalone" in lower or "company revenue" in lower:
        return "standalone"
    if "brand revenue" in lower or "brand net sales" in lower:
        return "brand_segment"
    return None


def table_periods(
    tables: list[list[list[str]]], brand: Row, entities: list[Row]
) -> dict[str, Row]:
    """Only semantic/date cells, never amounts, growth or component scores."""
    result: dict[str, Row] = {}
    preferred = [brand["id"], *brand.get("peers", [])]
    for table in tables:
        if not table:
            continue
        header = " ".join(table[0]).lower()
        if not re.search(
            r"financial input|fiscal year|fiscal start|base year end|peer / units",
            header,
        ):
            continue
        if "social" in header or "median" in header:
            continue
        own = []
        grouped: dict[str, list[Row]] = {}
        for row in table[1:]:
            if "entity and fiscal year" in header:
                label = re.search(r"FY\s*20\d{2}", row[0], re.I)
                eid = match_entity(
                    row[0][: label.start()] if label else row[0], entities, preferred
                )
                ds = dates(row[1]) if len(row) > 1 else []
                if eid and label and len(ds) == 2:
                    grouped.setdefault(eid, []).append(period(ds[0], ds[1], label[0]))
                continue
            if "peer / units" in header or "base year end" in header:
                name = re.split(
                    r"(?:USD|EUR|GBP|JPY|SEK|DKK|AUD)\s*(?:millions|billions)", row[0]
                )[0]
                eid = match_entity(name, entities, preferred)
                if eid:
                    entries = []
                    for cell in row[1:4]:
                        ds = dates(cell)
                        if len(ds) >= 2:
                            entries.append(period(ds[0], ds[1]))
                        elif ds:
                            entries.append(period(None, ds[0]))
                    if entries:
                        result[eid] = {
                            "periods": dict(zip(ROLES, entries, strict=False))
                        }
                continue
            ds = [day for cell in row[1:] for day in dates(cell)]
            if ds and re.search(r"FY\s*20\d{2}", row[0], re.I):
                own.append(
                    period(
                        ds[0] if len(ds) > 1 else None,
                        ds[1] if len(ds) > 1 else ds[0],
                        row[0],
                    )
                )
        if own:
            result[brand["id"]] = {"periods": dict(zip(ROLES, own[:3], strict=False))}
        for eid, entries in grouped.items():
            result[eid] = {"periods": dict(zip(ROLES, entries[-3:], strict=False))}
    return result


def supporting_entities(data: Row) -> list[Row]:
    if isinstance(data.get("entities"), list):
        return data["entities"]
    for name in (
        "financial_evidence",
        "financial",
        "financial_inputs",
        "financial_saved_research",
    ):
        block = data.get(name)
        if isinstance(block, dict) and isinstance(block.get("entities"), list):
            return block["entities"]
    return []


def apply_support(method: Row, record: Row, brand: Row, entities: list[Row]) -> None:
    preferred = [brand["id"], *brand.get("peers", [])]
    for entity in supporting_entities(record):
        eid = match_entity(entity["name"], entities, preferred)
        if eid is None:
            continue
        observations = entity.get("inputs", [])
        method["financial"]["entities"][eid] = {
            "subject": entity["name"],
            "scope": scope(entity.get("scope", "")),
            "metric": "revenue",
            "definition": entity.get("scope"),
            "periods": dict(
                zip(
                    ROLES,
                    [period(r.get("start"), r.get("end")) for r in observations[:3]],
                    strict=False,
                )
            ),
        }
    rows = record.get("annual_inputs", [])
    if isinstance(rows, list):
        grouped: dict[str, list[Row]] = {}
        for row in rows:
            if row.get("entity") and row.get("fiscal_start") and row.get("fiscal_end"):
                grouped.setdefault(row["entity"], []).append(row)
        for name, observations in grouped.items():
            eid = match_entity(name, entities, preferred)
            if eid:
                method["financial"]["entities"][eid] = {
                    "subject": name,
                    "scope": scope(observations[0].get("metric", "")),
                    "metric": "revenue",
                    "definition": observations[0].get("metric"),
                    "periods": dict(
                        zip(
                            ROLES,
                            [
                                period(
                                    r["fiscal_start"],
                                    r["fiscal_end"],
                                    r.get("fiscal_year", ""),
                                )
                                for r in observations[:3]
                            ],
                            strict=False,
                        )
                    ),
                }


def roadmap_parameters(
    method: Row,
    analysis: Row,
    cycle: Row,
    cycles: dict[str, Row],
    brand: Row,
    entities: list[Row],
) -> None:
    """Whitelist parameters only. DOCX/supporting records take precedence."""
    social = method["social"]
    social_text = str(cycle.get("socialMetric") or "").lower()
    social.update(
        platform=str(cycle.get("socialPlatform") or "instagram").lower(),
        metric="comments" if "comment" in social_text else "likes",
    )
    for source, target in (
        ("baselineWindowStart", "baseline_start"),
        ("baselineWindowEnd", "baseline_end"),
        ("showWindowStart", "current_start"),
        ("showWindowEnd", "current_end"),
    ):
        if cycle.get(source):
            analysis.setdefault(target, cycle[source])
    if not analysis.get("show_date") and cycle.get("showDate"):
        analysis.update(
            route="show",
            show_date=cycle["showDate"],
            collection=cycle.get("collection"),
            timezone=cycle.get("socialTimezone") or analysis.get("timezone"),
        )
        social.update(baseline_days=15, current_days=7)
    elif not analysis.get("collection"):
        analysis["collection"] = cycle.get("collection")
    if cycle.get("socialTimezone"):
        analysis["timezone"] = cycle["socialTimezone"]
    if cycle.get("socialIncludedCalendarMonths"):
        social["months"] = cycle["socialIncludedCalendarMonths"]
    if cycle.get("socialMinimumValidPosts"):
        social["min_posts"] = cycle["socialMinimumValidPosts"]
    if cycle.get("socialMinimumCommonMonths"):
        social["min_common_months"] = cycle["socialMinimumCommonMonths"]
    if cycle.get("socialAggregation"):
        social["aggregation"] = cycle["socialAggregation"]
    if cycle.get("socialSelectionRule"):
        social["selection_description"] = cycle["socialSelectionRule"]
    financial = method["financial"]["entities"]
    own = financial.setdefault(brand["id"], {"periods": {}})
    definition = cycle.get("revenueScope")
    if definition:
        own.setdefault("definition", definition)
        if not own.get("scope"):
            own["scope"] = scope(definition)
    own.setdefault("subject", cycle.get("proxyFinancialEntity") or brand["name"])
    selected = cycle
    for role in reversed(ROLES):
        for peer in selected.get("peers", []):
            eid = match_entity(
                peer.get("company", ""), entities, brand.get("peers", [])
            )
            if not eid or eid not in brand.get("peers", []):
                continue
            spec = financial.setdefault(eid, {"periods": {}})
            spec.setdefault("subject", peer["company"])
            if not spec.get("scope"):
                spec["scope"] = scope(peer.get("revenueScope", ""))
            ps, pe = peer.get("financialPeriodStart"), peer.get("financialPeriodEnd")
            if ps and pe:
                spec["periods"].setdefault(
                    role, period(ps, pe, peer.get("financialPeriodLabel", ""))
                )
            rs, re_ = (
                peer.get("referenceFinancialPeriodStart"),
                peer.get("referenceFinancialPeriodEnd"),
            )
            if rs and re_ and role != "oldest":
                spec["periods"].setdefault(
                    "earlier" if role == "latest" else "oldest", period(rs, re_)
                )
        start = selected.get("financialPeriodStart")
        end = selected.get("financialPeriodEnd")
        if start and end:
            own["periods"].setdefault(
                role, period(start, end, selected.get("financialPeriodLabel", ""))
            )
        previous = cycles.get(str(selected.get("priorCycleKey") or ""), {})
        if not previous and role != "oldest":
            ps, pe = (
                selected.get("referenceFinancialPeriodStart"),
                selected.get("referenceFinancialPeriodEnd"),
            )
            if ps and pe:
                own["periods"].setdefault(
                    "earlier" if role == "latest" else "oldest", period(ps, pe)
                )
        selected = previous


def calendar_financials(
    method: Row,
    tables: list[list[list[str]]],
    brand: Row,
    entities: list[Row],
    text: str,
) -> None:
    """Explicit calendar-year financial definitions, never arbitrary fiscal labels."""
    # Calendar reporting must be established for the entity, not inferred from
    # another company's fiscal labels. These are the report's calendar issuers.
    for table in tables:
        if not table or not re.search(
            r"entity or segment|entity|business", table[0][0], re.I
        ):
            continue
        labels = [re.search(r"FY\s*(20\d{2})", cell) for cell in table[0][1:4]]
        if len(labels) != 3 or not all(labels):
            continue
        for row in table[1:]:
            eid = match_entity(row[0], entities, [brand["id"], *brand.get("peers", [])])
            if eid is None:
                continue
            # These entities' calendar reporting is stated in the supplied reports.
            if eid not in {
                "hermes",
                "prada",
                "chanel",
                "valentino",
                "christian-dior",
                "gucci",
                "saint-laurent",
                "lvmh",
                "moncler-group",
            }:
                continue
            own = method["financial"]["entities"].setdefault(eid, {"periods": {}})
            own.setdefault("subject", row[0])
            own.setdefault(
                "scope",
                "brand_segment"
                if eid in {"gucci", "saint-laurent"}
                else "consolidated"
                if eid in {"hermes", "prada", "lvmh", "moncler-group"}
                else "standalone",
            )
            for role, label in zip(ROLES, labels, strict=True):
                assert label is not None
                year = label[1]
                own["periods"].setdefault(
                    role, period(f"{year}-01-01", f"{year}-12-31", f"FY{year}")
                )


def fiscal_labels(
    method: Row, analysis: Row, tables: list, brand: Row, entities: list[Row], text: str
) -> None:
    """Preserve issuer FY labels when a report omits exact older boundaries.

    Labels are requests, not permission to equate shared calendar-year rows with
    Light fiscal years. The selector still needs verified native period metadata.
    """
    for table in tables:
        if not table or table[0][0].lower() not in {
            "entity",
            "entity or segment",
            "fiscal year",
        }:
            continue
        if table[0][0].lower() == "fiscal year":
            labels_by_row = [
                r[0] for r in table[1:] if re.fullmatch(r"FY\s*20\d{2}", r[0])
            ]
            if len(labels_by_row) == 3:
                for name in table[0][1:]:
                    eid = match_entity(
                        name, entities, [brand["id"], *brand.get("peers", [])]
                    )
                    if eid:
                        spec = method["financial"]["entities"].setdefault(
                            eid, {"periods": {}}
                        )
                        spec.setdefault("subject", name)
                        spec.setdefault(
                            "scope",
                            "consolidated"
                            if eid == "ralph-lauren"
                            else "brand_segment",
                        )
                        for role, label in zip(ROLES, labels_by_row, strict=True):
                            spec["periods"].setdefault(
                                role,
                                {
                                    "label": label,
                                    "type": "annual",
                                    "alignment": "native_fiscal_year",
                                },
                            )
            continue
        labels = [re.search(r"FY\s*(20\d{2})", cell) for cell in table[0][1:4]]
        if len(labels) != 3 or not all(labels):
            continue
        for row in table[1:]:
            eid = match_entity(row[0], entities, [brand["id"], *brand.get("peers", [])])
            if not eid:
                continue
            spec = method["financial"]["entities"].setdefault(eid, {"periods": {}})
            spec.setdefault("subject", row[0])
            if not spec.get("scope"):
                if eid == brand["id"]:
                    spec["scope"] = scope(" ".join(text.split("1 Fashion")[0:1]))
                elif eid in {"ralph-lauren", "hermes", "prada", "gap", "gap-inc"}:
                    spec["scope"] = "consolidated"
                elif eid in {
                    "coach",
                    "michael-kors",
                    "kate-spade",
                    "gucci",
                    "american-eagle",
                }:
                    spec["scope"] = "brand_segment"
                elif brand["id"] == "gap-inc":
                    spec["scope"] = "consolidated"
            for role, match in zip(ROLES, labels, strict=True):
                assert match is not None
                spec["periods"].setdefault(
                    role,
                    {
                        "label": f"FY{match[1]}",
                        "type": "annual",
                        "alignment": "native_fiscal_year",
                    },
                )
            # Annual social periods explicitly labelled as that issuer's FY
            # also establish two financial boundaries, not another issuer's FY.
            if (
                eid == brand["id"]
                and analysis.get("route") == "annual"
                and "fiscal years" in text.lower()
            ):
                for role, prefix in (("earlier", "baseline"), ("latest", "current")):
                    if analysis.get(f"{prefix}_start") and analysis.get(
                        f"{prefix}_end"
                    ):
                        p = spec["periods"][role]
                        if not p.get("start"):
                            p.update(
                                start=analysis[f"{prefix}_start"],
                                end=analysis[f"{prefix}_end"],
                            )


def portfolio_parameters(
    method: Row, roadmap: Row, cycle_key: str, entities: list[Row]
) -> None:
    members = []
    for item in roadmap.get("portfolioSocialInputs", []):
        if item.get("cycleKey") != cycle_key or not item.get("includedInMainScore"):
            continue
        handle = str(item.get("account") or "").lower()
        if not re.fullmatch(r"[a-z0-9_.]+", handle):
            method["limitations"].append(
                f"Unresolved portfolio account: {item.get('account')}"
            )
            continue
        members.append(
            {
                "name": item["brand"],
                "handle": handle,
                "route": "annual",
                "timezone": item.get("publicationTimezone") or "UTC",
                "baseline_start": item.get("baselineWindowStart"),
                "baseline_end": item.get("baselineWindowEnd"),
                "current_start": item.get("comparisonWindowStart"),
                "current_end": item.get("comparisonWindowEnd"),
            }
        )
    campaign_handles = {
        "Gap": "gap",
        "Old Navy": "oldnavy",
        "Banana Republic": "bananarepublic",
        "Athleta": "athleta",
    }
    for item in roadmap.get("socialCampaigns", []):
        if item.get("cycleKey") != cycle_key:
            continue
        members.append(
            {
                "name": item["brand"],
                "handle": campaign_handles.get(item["brand"]),
                "route": "show",
                "show_date": item.get("anchorDate"),
                "timezone": "America/New_York",
                "caption_pattern": "|".join(
                    re.escape(t).replace(r"\ ", r"\s+")
                    for t in item.get("captionTerms", [])
                ),
                "min_posts": item.get("minimumPostsPerWindow", 3),
            }
        )
    if members:
        method["social"].update(
            aggregation="median_member_lifts",
            members=members,
            common_months_only=False,
            min_common_months=0,
            min_members=1 if cycle_key == "gap-inc-fy2025" else len(members),
        )
        for member in members:
            identity = next(
                (e for e in entities if e.get("instagram") == member["handle"]), {}
            )
            if identity.get("profile_id"):
                member["profile_id"] = identity["profile_id"]


def show_support(
    method: Row, analysis: Row, record: Row, brand: Row, entities: list[Row]
) -> bool:
    """Latest scored collection, not latest show with a pending selling outcome."""
    events = record.get("events", [])
    nested = next(
        (
            b
            for b in record.get("brands", [])
            if names(b.get("brand", "")) & names(brand["name"])
        ),
        None,
    )
    if nested:
        events = nested.get("events", [])
    if not isinstance(events, list):
        return False
    eligible = [
        e for e in events if e.get("overall", e.get("overall_score")) is not None
    ]
    if not eligible:
        return False
    event = eligible[-1]
    if brand["id"] == "burberry":
        # The shared RL record carries all three retail/DTC financial series.
        # Keep Burberry's selected event from its own business report.
        event = {
            **event,
            "collection": "Summer 2026",
            "show_date": "2025-09-22",
            "timezone": "Europe/London",
            "pattern": None,
        }
    selected_date = event.get("show_date") or event.get("date")
    if selected_date is None:
        return False
    analysis.update(
        route="show",
        collection=event["collection"],
        show_date=selected_date,
        timezone=event.get("timezone") or analysis.get("timezone"),
    )
    method["social"].update(
        baseline_days=15, current_days=7, caption_pattern=event.get("pattern")
    )
    method["trend"]["comparison"] = "same_season"
    if nested:
        selected_keys = [event.get("commercial"), event.get("earlier")]
        if selected_keys[0] and selected_keys[1]:
            prior = re.sub(r"20\d{2}", lambda m: str(int(m[0]) - 1), selected_keys[1])
            keys = [prior, selected_keys[1], selected_keys[0]]
            for eid in (brand["id"], *brand.get("peers", [])):
                identity = next(e for e in entities if e["id"] == eid)
                entries = []
                for k in keys:
                    raw = (
                        record.get("pvh_revenue_millions", {}).get(k, {})
                        if eid == brand["id"]
                        else next(
                            (
                                v
                                for name, v in record.get("peer_revenue_millions", {})
                                .get(k, {})
                                .items()
                                if names(name) & names(identity["name"])
                            ),
                            {},
                        )
                    )
                    entries.append(period(raw.get("start"), raw.get("end"), k))
                method["financial"]["entities"][eid] = {
                    "subject": identity["name"],
                    "scope": "brand_segment" if eid == brand["id"] else "consolidated",
                    "metric": "revenue",
                    "periods": dict(zip(ROLES, entries, strict=True)),
                }
        return True
    if event.get("period_start") and event.get("period_end"):
        # Coach annual selling proxy; retain the exact supplied fiscal dates.
        own = method["financial"]["entities"].setdefault(brand["id"], {"periods": {}})
        own.update(subject=brand["name"], scope="brand_segment", metric="revenue")
        own["periods"]["latest"] = period(
            event["period_start"], event["period_end"], str(event.get("period") or "")
        )
        previous = next(
            (
                e
                for e in events
                if e.get("period") != event.get("period") and e.get("period_start")
            ),
            None,
        )
        if previous:
            own["periods"]["earlier"] = period(
                previous["period_start"],
                previous["period_end"],
                previous.get("period", ""),
            )
    finance = record.get("finance", [])
    for eid in (brand["id"], *brand.get("peers", [])):
        identity = next(e for e in entities if e["id"] == eid)
        selected = [
            r
            for r in finance
            if match_entity(r.get("brand", ""), entities, [eid]) == eid
            and r.get("period") == event.get("period")
        ]
        if not selected:
            continue
        latest = selected[0]
        earlier = next(
            (
                r
                for r in finance
                if r.get("brand") == latest.get("brand")
                and r.get("start")
                and latest.get("start")
                and 350
                <= (
                    date.fromisoformat(latest["start"]) - date.fromisoformat(r["start"])
                ).days
                <= 380
            ),
            None,
        )
        ps = {
            "latest": period(
                latest.get("start"), latest.get("end"), latest.get("period", "")
            )
        }
        if earlier:
            ps["earlier"] = period(
                earlier.get("start"), earlier.get("end"), earlier.get("period", "")
            )
        method["financial"]["entities"][eid] = {
            "subject": identity["name"],
            "scope": "brand_segment" if brand["id"] == "tom-ford" else "retail_dtc",
            "metric": "revenue_growth_comparable"
            if brand["id"] == "tom-ford"
            else "revenue",
            "definition": str(latest.get("metric", "")).split(":")[0],
            "periods": ps,
        }
        if earlier and not ps.get("oldest"):
            # Dossier year-on-year comparison explicitly identifies this calendar
            # selling window, but does not give its exact older fiscal boundaries.
            # Do not manufacture fiscal dates; keep the calendar proxy explicit.
            label = earlier.get("period", "")
            year = date.fromisoformat(earlier["end"]).year - 1
            months = (4, 6) if "Apr" in label else (10, 12) if "Oct" in label else None
            if months:
                ps["oldest"] = {
                    **period(
                        f"{year}-{months[0]:02}-01",
                        f"{year}-{months[1]:02}-30"
                        if months[1] == 6
                        else f"{year}-12-31",
                        f"Prior year {label}",
                    ),
                    "alignment": "calendar_selling_window_proxy",
                }
    return True


def validate_method(method: Row, entity_ids: set[str]) -> None:
    """Reject measurements/typos in editable business parameters."""
    allowed = {
        "source",
        "source_sha256",
        "supporting_sources",
        "status",
        "missing_parameters",
        "financial",
        "social",
        "trend",
        "score_basis",
        "limitations",
    }
    if set(method) - allowed:
        raise ValueError(f"Unknown dossier parameters: {sorted(set(method) - allowed)}")
    financial = method.get("financial", {})
    if set(financial) - {"entities", "aggregation", "growth_basis"}:
        raise ValueError("Financial dossier parameters cannot contain amounts")
    if financial.get("aggregation") not in {
        "single_reported_observation",
        "sum_verified_discrete_quarters",
    }:
        raise ValueError("Unknown dossier revenue aggregation")
    if financial.get("growth_basis", "nominal_revenue_ratio") not in {
        "nominal_revenue_ratio",
        "published_comparable_growth",
    }:
        raise ValueError("Unknown dossier growth basis")
    for eid, spec in financial.get("entities", {}).items():
        if eid not in entity_ids:
            raise ValueError(f"Unknown dossier financial entity: {eid}")
        if set(spec) - {
            "subject",
            "scope",
            "metric",
            "definition",
            "periods",
            "source_entity_id",
        }:
            raise ValueError(
                "Financial definitions contain an unknown field or measurement"
            )
        if spec.get("source_entity_id") and spec["source_entity_id"] not in entity_ids:
            raise ValueError("Unknown dossier source entity")
        if set(spec.get("periods", {})) - set(ROLES):
            raise ValueError("Dossier periods must use oldest/earlier/latest")
        for p in spec.get("periods", {}).values():
            if set(p) - {"label", "start", "end", "type", "alignment"}:
                raise ValueError(
                    "Dossier periods contain an unknown field or measurement"
                )
            for field in ("start", "end"):
                if p.get(field):
                    date.fromisoformat(p[field])
            if p.get("start") and p.get("end") and p["start"] > p["end"]:
                raise ValueError("Dossier period start must precede end")
            if p.get("type") not in {"annual", "quarter", "half_year"}:
                raise ValueError("Unknown dossier period type")
            if p.get("alignment", "exact_dossier_boundaries") not in {
                "exact_dossier_boundaries",
                "calendar_selling_window_proxy",
                "native_fiscal_year",
            }:
                raise ValueError("Unknown dossier period alignment")
    if method.get("score_basis") not in {"original", "percentile", "partial"}:
        raise ValueError("Dossier score_basis must be original, percentile or partial")
    social = method.get("social", {})
    if set(social) - {
        "platform",
        "metric",
        "baseline_days",
        "current_days",
        "caption_pattern",
        "baseline_pattern",
        "exclude_pattern",
        "min_posts",
        "min_common_months",
        "common_months_only",
        "months",
        "aggregation",
        "members",
        "selection_description",
        "capture_cutoff",
        "min_members",
    }:
        raise ValueError("Unknown social dossier field or measurement override")
    if social.get("platform") not in {"instagram", "tiktok", "twitter"} or social.get(
        "metric"
    ) not in {"likes", "comments"}:
        raise ValueError("Unknown dossier platform/metric")
    if social.get("capture_cutoff"):
        from .models import instant

        if instant(social["capture_cutoff"]) is None:
            raise ValueError("Invalid dossier capture cutoff")
    if social.get("aggregation") not in {
        None,
        "median_member_lifts",
        "median-eligible-campaign-lifts",
        "median-selected-brand-fiscal-lifts",
        "median-selected-brand-matched-comment-lifts",
    }:
        raise ValueError("Unknown dossier social aggregation")
    for member in social.get("members", []):
        allowed_member = {
            "name",
            "handle",
            "profile_id",
            "route",
            "timezone",
            "show_date",
            "baseline_start",
            "baseline_end",
            "current_start",
            "current_end",
            "caption_pattern",
            "min_posts",
        }
        if (
            not isinstance(member, dict)
            or set(member) - allowed_member
            or not member.get("name")
            or not member.get("handle")
            or member.get("route") not in {"annual", "show"}
        ):
            raise ValueError(
                "Invalid portfolio member parameters; no measurement overrides"
            )
        for field in (
            "show_date",
            "baseline_start",
            "baseline_end",
            "current_start",
            "current_end",
        ):
            if member.get(field):
                date.fromisoformat(member[field])
        if member.get("caption_pattern"):
            re.compile(member["caption_pattern"])
        if "min_posts" in member and (
            not isinstance(member["min_posts"], int)
            or isinstance(member["min_posts"], bool)
            or member["min_posts"] <= 0
        ):
            raise ValueError("Invalid portfolio sample minimum")
    for field in (
        "baseline_days",
        "current_days",
        "min_posts",
        "min_common_months",
        "min_members",
    ):
        if field in social and (
            not isinstance(social[field], int)
            or isinstance(social[field], bool)
            or social[field] < 0
            or (
                field in {"baseline_days", "min_posts", "min_members"}
                and social[field] == 0
            )
        ):
            raise ValueError(f"Invalid dossier social {field}")
    for field in ("caption_pattern", "baseline_pattern", "exclude_pattern"):
        if social.get(field):
            re.compile(social[field])
    if any(
        not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= 12
        for m in social.get("months", [])
    ):
        raise ValueError("Dossier social months must be calendar month numbers")
    trend = method.get("trend", {})
    if (
        set(trend) - {"basis", "rule", "comparison", "assumed_score"}
        or trend.get("basis") not in {"peer_gap", "company_growth", "assumed"}
        or trend.get("rule") not in {"legacy", "improvement_sign"}
    ):
        raise ValueError("Unknown dossier Trend method")
    if trend.get("basis") == "assumed" and (
        not isinstance(trend.get("assumed_score"), (float, int))
        or not 0 <= trend["assumed_score"] <= 100
    ):
        raise ValueError("An assumed dossier Trend requires an explicit 0–100 score")


def align_dossiers(
    data: Row, root: Path, roadmap: Path | None = None
) -> tuple[Row, list[Row]]:
    """Preserve identities/reviews and existing editable dossier parameters."""
    result = deepcopy(data)
    result.update(mode="dossier", financial_basis="dossier")
    reports = read_reports(root)
    entities = [*result["brands"], *result.get("peer_entities", [])]
    records_root = root / "FMI_delivery/04_Supporting_data"
    annual_path = records_root / "annual_13_calculations.json"
    annual = (
        json.loads(annual_path.read_text()).get("companies", [])
        if annual_path.exists()
        else []
    )
    record_paths = sorted((records_root / "report_records").rglob("*.json"))
    records = [(p, json.loads(p.read_text())) for p in record_paths]
    roadmap_data = json.loads(roadmap.read_text()) if roadmap else {}
    cycles = {c["cycleKey"]: c for c in roadmap_data.get("cycles", [])}
    audit = []
    for brand in result["brands"]:
        if brand.get("analysis", {}).get("dossier"):
            audit.append(
                {
                    "brand_id": brand["id"],
                    "status": "existing_dossier_parameters_preserved",
                }
            )
            continue
        identity = {"entity_id": brand["id"], "name": brand["name"]}
        refs = matched_reports(identity, reports)
        if brand["id"] == "global-luxury-retail-group-dba-missoni":
            refs = []  # The distributor is not the Missoni brand.
        analysis = {
            k: v
            for k, v in brand.get("analysis", {}).items()
            if k in {"id", "headline", "selected"}
        }
        method: Row = {
            "source": None,
            "status": "no_dossier",
            "missing_parameters": [],
            "financial": {"aggregation": "single_reported_observation", "entities": {}},
            "social": {"platform": "instagram", "metric": "likes"},
            "trend": {
                "basis": "peer_gap",
                "rule": "legacy",
                "comparison": "dossier_defined",
            },
            "score_basis": "original",
            "limitations": [],
        }
        if len(refs) != 1:
            method["missing_parameters"].append(
                "No unique business dossier for this prospect"
            )
        else:
            path = Path(refs[0]["path"])
            paragraphs, tables = report_content(path)
            text = " ".join(paragraphs)
            method.update(
                source=str(path.relative_to(root.parent)),
                source_sha256=sha256(path.read_bytes()).hexdigest(),
                status="incomplete_parameters",
                supporting_sources=[],
            )
            old_analysis = brand.get("analysis", {})
            analysis.update(
                route="annual", timezone=old_analysis.get("timezone", "UTC")
            )
            method["financial"]["entities"] = table_periods(tables, brand, entities)
            if (
                "latest company growth" in text.lower()
                or "company-only category" in text.lower()
            ):
                method["trend"]["basis"] = "company_growth"
            if re.search(
                r"normalized.*(?:score|overall)|(?:score|overall).*normalized",
                " ".join(paragraphs[:3]),
                re.I,
            ):
                method["score_basis"] = "percentile"
            if refs[0].get("annual_windows"):
                analysis.update(refs[0]["annual_windows"][0])
                method["social"]["common_months_only"] = False
            selected_annual = next(
                (c for c in annual if names(c["name"]) & names(brand["name"])), None
            )
            if selected_annual:
                selected = selected_annual["selected"]
                method["financial"]["aggregation"] = "sum_verified_discrete_quarters"
                method["trend"]["basis"] = "company_growth"
                if not brand.get("review", {}).get("peers"):
                    brand["peers"] = [
                        eid
                        for p in selected["peers"]
                        if (
                            eid := match_entity(
                                p["name"], entities, brand.get("peers", [])
                            )
                        )
                    ]
                method["social"].update(
                    min_posts=20, min_common_months=3, common_months_only=True
                )
                year, suffix = selected["year"], selected["social"]["cutoff"]
                analysis.update(
                    route="annual",
                    timezone="UTC",
                    baseline_start=f"{year - 1}-01-01",
                    baseline_end=f"{year - 1}-{suffix}",
                    current_start=f"{year}-01-01",
                    current_end=f"{year}-{suffix}",
                    collection=(
                        f"{year} social / FY{selected['financial_year']} revenue"
                    ),
                )
                for name, observations in [
                    (brand["name"], selected["own"]),
                    *[(p["name"], p["annual"]) for p in selected["peers"]],
                ]:
                    eid = match_entity(
                        name, entities, [brand["id"], *brand.get("peers", [])]
                    )
                    if eid:
                        method["financial"]["entities"][eid] = {
                            "subject": name,
                            "scope": "dossier_labelled_company",
                            "metric": "revenue",
                            "definition": selected_annual["scope"]
                            if eid == brand["id"]
                            else "Dossier peer annual revenue",
                            "periods": dict(
                                zip(
                                    ROLES,
                                    [
                                        period(r["start"], r["end"], f"FY{r['year']}")
                                        for r in observations[-3:]
                                    ],
                                    strict=False,
                                )
                            ),
                        }
                method["supporting_sources"].append(
                    str(annual_path.relative_to(root.parent))
                )
            for support_path, record in records:
                stem = path.parent.name
                matched = key(stem) in key(support_path.parent.name)
                if (
                    brand["id"] in {"calvin-klein", "tommy-hilfiger"}
                    and support_path.parent.name == "pvh-show-analysis-2026-10-27"
                ):
                    matched = True
                if (
                    brand["id"] == "vf-corporation"
                    and support_path.parent.name == "vf-corp-fy-analysis-2026-10-27"
                ):
                    matched = True
                if (
                    brand["id"] == "burberry"
                    and support_path.parent.name
                    == "ralph-lauren-show-analysis-2026-10-27"
                ):
                    matched = True
                if not matched:
                    continue
                apply_support(method, record, brand, entities)
                show_support(method, analysis, record, brand, entities)
                method["supporting_sources"].append(
                    str(support_path.relative_to(root.parent))
                )
            calendar_financials(method, tables, brand, entities, text)
            selected_key = next(
                (
                    v
                    for name, v in roadmap_data.get("selectedCycles", {}).items()
                    if names(name) & names(brand["name"])
                ),
                None,
            )
            if selected_key and not selected_annual:
                roadmap_parameters(
                    method, analysis, cycles[selected_key], cycles, brand, entities
                )
                portfolio_parameters(method, roadmap_data, selected_key, entities)
                method["supporting_sources"].append(
                    "aily-superagent-roadmap/docs/research/wwd-fashion-momentum/"
                    "weighted-delivery-inputs.json (parameters only)"
                )
            if "comment" in " ".join(paragraphs[:5]).lower():
                method["social"]["metric"] = "comments"
            if re.search(
                r"median.*three brand lifts|median of the three brand lifts|"
                r"group social proxy = median",
                text,
                re.I,
            ):
                method["social"]["aggregation"] = "median_member_lifts"
            fiscal_labels(method, analysis, tables, brand, entities, text)
            if re.search(r"captures up to 28 October 2026", text, re.I):
                method["social"]["capture_cutoff"] = "2026-10-28T23:59:59.999999Z"
            if re.search(
                r"strength is assigned.*50|neutral 50/100 assumption", text, re.I
            ):
                method["trend"].update(basis="assumed", assumed_score=50)
                method["limitations"].append(
                    "Dossier assumes Trend=50; this is not measured Trend"
                )
            # Do not lose report-specific filters behind a generic annual default.
            if brand["id"] == "me-em":
                analysis.update(
                    route="annual",
                    timezone="Europe/London",
                    baseline_start="2023-10-01",
                    baseline_end="2023-12-31",
                    current_start="2024-10-01",
                    current_end="2024-12-31",
                )
                method["social"].update(
                    min_posts=2, min_common_months=0, common_months_only=False
                )
                method["limitations"].append(
                    "Dossier uses a two-post social baseline; low reliability"
                )
            if brand["id"] in {"fendi", "christian-dior"}:
                own = method["financial"]["entities"].setdefault(
                    brand["id"], {"periods": {}}
                )
                own.update(
                    subject="LVMH Fashion and Leather Goods",
                    scope="parent_segment",
                    definition=(
                        "LVMH Fashion and Leather Goods segment, "
                        "NOT standalone brand revenue"
                    ),
                )
                own["periods"] = {
                    r: period(f"{y}-01-01", f"{y}-12-31", f"FY{y}")
                    for r, y in zip(ROLES, (2023, 2024, 2025), strict=True)
                }
            if brand["id"] == "fendi":
                analysis.update(
                    route="annual",
                    timezone="Europe/Rome",
                    baseline_start="2024-01-01",
                    baseline_end="2024-12-31",
                    current_start="2025-01-01",
                    current_end="2025-12-31",
                )
            if brand["id"] == "tom-ford":
                method["social"]["exclude_pattern"] = r"beauty|fragrance|makeup"
                method["social"]["baseline_pattern"] = ".*"
                method["financial"]["growth_basis"] = "published_comparable_growth"
                method["limitations"].append(
                    "Dossier uses published organic/comparable growth, not nominal "
                    "revenue ratios; that metric needs a verified DB source"
                )
            # The Burberry report establishes human collection relevance, not
            # a reproducible caption regex. Do not silently select all show posts.
            if brand["id"] == "burberry":
                method["social"]["selection_description"] = (
                    "Reviewed Summer 2026 collection posts only; baseline all "
                    "account posts in preceding 15 days"
                )
            # Financial subject is a source mapping, not just a display label.
            own = method["financial"]["entities"].get(brand["id"], {})
            parent_id = {"fendi": "lvmh", "christian-dior": "lvmh"}.get(brand["id"])
            if not parent_id and own.get("subject"):
                parent_id = match_entity(own["subject"], entities, [])
            if parent_id and parent_id != brand["id"]:
                own["source_entity_id"] = parent_id
                if parent_id == "lvmh" and own.get("scope") == "consolidated":
                    for p in own.get("periods", {}).values():
                        if p.get("end") and not p.get("start"):
                            p.update(start=p["end"][:4] + "-01-01", type="annual")
            if analysis.get("route") == "show":
                # Show windows are derived from the dossier's editable offsets.
                for field in (
                    "baseline_start",
                    "baseline_end",
                    "current_start",
                    "current_end",
                ):
                    analysis.pop(field, None)
            if method["social"].get("aggregation") and not method["social"].get(
                "members"
            ):
                method["missing_parameters"].append(
                    "Portfolio social accounts/windows/relevance rules "
                    "require explicit member definitions"
                )
            # Exact parameters not established by these records stay missing.
            if not method["financial"]["entities"]:
                method["missing_parameters"].append(
                    "Revenue scope and comparable period boundaries "
                    "not established in structured dossier parameters"
                )
            for eid in brand.get("peers", []):
                if eid not in method["financial"]["entities"]:
                    method["missing_parameters"].append(
                        f"{eid}: dossier peer financial period definition missing"
                    )
            if (
                not analysis.get("show_date")
                and not analysis.get("current_start")
                and not method["social"].get("members")
            ):
                method["missing_parameters"].append(
                    "Selected social publication windows not established"
                )
            if analysis.get("route") == "show" and not method["social"].get(
                "caption_pattern"
            ):
                method["missing_parameters"].append(
                    "Collection post relevance rule not established"
                )
            for eid, spec in method["financial"]["entities"].items():
                spec.setdefault(
                    "subject", next(e["name"] for e in entities if e["id"] == eid)
                )
                spec.setdefault("scope", None)
                spec.setdefault("metric", "revenue")
                for role in (
                    ("earlier", "latest")
                    if method["financial"].get("growth_basis")
                    == "published_comparable_growth"
                    else ROLES
                ):
                    p = spec.get("periods", {}).get(role, {})
                    if (not p.get("start") or not p.get("end")) and not (
                        p.get("alignment") == "native_fiscal_year" and p.get("label")
                    ):
                        method["missing_parameters"].append(
                            f"{eid}: {role} exact financial dates missing"
                        )
                if not spec.get("scope"):
                    method["missing_parameters"].append(
                        f"{eid}: financial scope definition missing"
                    )
            if not method["missing_parameters"]:
                method["status"] = "dossier_parameters_set"
        analysis["dossier"] = method
        brand["analysis"] = analysis
        audit.append(
            {
                "brand_id": brand["id"],
                "source": method["source"],
                "status": method["status"],
                "missing_parameters": method["missing_parameters"],
            }
        )
    return result, audit
