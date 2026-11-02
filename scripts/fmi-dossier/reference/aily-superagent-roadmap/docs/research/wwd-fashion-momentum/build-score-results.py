"""Reproduce the research results without altering Allen's source workbook."""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AS_OF = "2026-10-27T04:45:35Z"
SOURCES = {
    "lefty_london_ss27": {
        "url": "https://lefty.io/fashion-weeks/lfw-ss27",
        "title": "Lefty — London Fashion Week SS27",
        "published": "2026-09-28", "provider": "Lefty",
        "eventYear": 2026, "season": "SS27",
        "window": "September 2026 London SS27 coverage; precise comparable collection window not captured in this research",
        "verification": "Public report table read directly",
    },
    "lefty_milan_ss27": {
        "url": "https://lefty.io/fashion-weeks/mfw-ss27",
        "title": "Lefty — Milan Fashion Week SS27",
        "published": "2026-10-02", "provider": "Lefty",
        "eventYear": 2026, "season": "SS27",
        "window": "2026-09-22 to 2026-09-28; data retrieved 2026-09-30 PM",
        "verification": "Public report table and methodology read directly",
    },
    "lefty_ss26": {
        "url": "https://lefty.io/fashion-weeks/ss26",
        "title": "Lefty — SS26 Fashion Week roundup",
        "published": "2025-10-13", "provider": "Lefty",
        "eventYear": 2025, "season": "SS26",
        "window": "New York chart: 2025-09-09 to 2025-09-18. London and Milan exact collection windows not captured",
        "verification": "London/Milan HTML tables and New York embedded chart read directly; New York chart visually inspected",
        "newYorkChartUrl": "https://images.prismic.io/lefty/aNLia55xUNkB1CE2_Lefty_NYFW2.png?auto=format%2Ccompress&fit=max&w=1920",
    },
    "diary_ny_ss27": {
        "url": "https://www.diarydirectory.com/newsarticle/lefty-reveals-nyfw-ss27-key-trends/75086",
        "title": "DIARY directory — Lefty reveals NYFW SS27 key trends",
        "published": "2026-09-22", "provider": "Lefty, quoted by DIARY directory",
        "eventYear": 2026, "season": "SS27",
        "window": "September 2026 NYFW SS27; precise collection/capture window not available in accessible article",
        "verification": "Secondary article read directly. Its linked Lefty primary page returned 404",
        "unavailablePrimaryUrl": "https://lefty.io/blog/newyorkfashionweek-ss27",
    },
    "lefty_paris_ss27": {
        "url": "https://lefty.io/blog/paris-fashion-week-ss27",
        "title": "Lefty — Paris Fashion Week SS27",
        "published": "2026-10-12", "provider": "Lefty",
        "eventYear": 2026, "season": "SS27",
        "window": "2026-09-28 to 2026-10-07; data captured 2026-10-08 PM",
        "verification": "Public report table and methodology read directly",
    },
    "team_vs": {
        "url": "https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793064007537279",
        "title": "Jaime's Victoria's Secret example, Slack screenshot F0CC7KC4W4V",
        "provider": "Team-supplied screenshot; underlying measurement provider not independently verified",
        "eventYear": 2026, "window": "YouTube approximately 20.5 hours after show; matched timing for other inputs unverified",
        "verification": "Team evidence only; exact public-source figures not located",
    },
}

def dec(v):
    return Decimal(str(v))

def half_up(v):
    return int(v.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def ratio_signal(label, current, reference, unit, current_source, reference_source, reference_year=2025, **extra):
    assert dec(reference) > 0
    ratio = dec(current) / dec(reference)
    raw = 50 * ratio
    bounded = min(Decimal(75), max(Decimal(60), raw))
    return {
        "label": label, "current": current, "reference": reference,
        "unit": unit, "referenceYear": reference_year,
        "currentSourceId": current_source, "referenceSourceId": reference_source,
        "currentClassification": "reported", "referenceClassification": "reported",
        "growth": float(ratio - 1), "rawScore": float(raw), "boundedScore": float(bounded),
        "usableForProvisionalCalculation": True,
        "matchedWindowsVerified": False, **extra,
    }

def index_of(signals):
    usable = [s for s in signals if s.get("usableForProvisionalCalculation")]
    if len(usable) < 2:
        return None, None
    # Recalculate from inputs, without rounding individual components.
    score = sum(min(Decimal(75), max(Decimal(60), 50 * dec(s["current"]) / dec(s["reference"]))) for s in usable) / len(usable)
    return half_up(score), float(score)

public_inputs = {
    "Burberry": (10842340, 16800000, 6.6, 4.8, "lefty_london_ss27", -.36, "London"),
    "Fendi": (26700000, 20900000, 4.3, 2.2, "lefty_milan_ss27", .28, "Milan"),
    "Coach": (13700000, 6000000, 4.3, 1.3, "diary_ny_ss27", 1.28, "New York"),
    "Ralph Lauren": (3500000, 10700000, 3.0, 1.3, "diary_ny_ss27", -.68, "New York"),
    "Calvin Klein": (12100000, 24900000, 4.0, 3.1, "diary_ny_ss27", -.52, "New York"),
}
common_limits = [
    "Two related influencer-post signals: estimated earned media value and average engagement rate. They are not three independent audience, social and press categories.",
    "Average engagement rate is a disclosed fallback proxy, not total engagements. EMV is an estimated media valuation, not observed reach or revenue.",
    "Same provider and same-season editions, but fully matched collection windows, post ages, platform coverage and provider definitions have not been verified.",
    "Published rounded inputs are used at their published precision; recomputed growth can differ from a report's rounded YoY growth.",
    "The 60-point floor can conceal declines, and the 75-point cap compresses strong growth. Actual growth metrics must accompany the score.",
]

prospects = json.loads((ROOT / "prospects.json").read_text())
results = []
for brand in prospects["brandContent"]:
    name = brand["company"]
    row = {
        "company": name, "status": "insufficient_comparable_data",
        "index": None, "indexUnrounded": None, "signals": [],
        "productionReady": False, "eligibleForValidatedLeaderboard": False,
        "researchAsOf": AS_OF, "limitations": [], "nextInputsNeeded": [],
        "customerContent": {
            "title": "Fashion Momentum", "brand": name,
            "displayState": "Comparable data pending",
            "cta": "Unlock November signal",
            "invitation": "Add your sales and inventory data to see where to act.",
        },
    }
    if name in public_inputs:
        emv, emv_ref, er, er_ref, source, published_growth, city = public_inputs[name]
        row["signals"] = [
            ratio_signal("Estimated earned media value", emv, emv_ref, "USD", source, "lefty_ss26",
                         metricType="earned_media_value", category="media_value_proxy", sourceReportedGrowth=published_growth,
                         precision="Burberry current value published as an integer; other EMV inputs published rounded to millions"),
            ratio_signal("Average engagement rate", er, er_ref, "%", source, "lefty_ss26",
                         metricType="average_engagement_rate", category="social_engagement_rate_proxy",
                         absoluteChangePercentagePoints=float(dec(er)-dec(er_ref)), precision="Published percentage precision"),
        ]
        row["index"], row["indexUnrounded"] = index_of(row["signals"])
        row["status"] = "provisional_public_two_signal_score"
        row["event"] = {"current": f"{city} SS27, September 2026", "reference": f"{city} SS26, September 2025"}
        row["limitations"] = common_limits.copy()
        row["nextInputsNeeded"] = ["Verify matched current/reference measurement windows and metric definitions", "Add a comparable independent audience or press-volume component if available"]
        if source == "diary_ny_ss27":
            row["limitations"].append("Current figures are from an accessible secondary source quoting Lefty; the linked primary page is unavailable.")
        row["customerContent"].update({"displayState": "Provisional · 2 signals", "score": row["index"],
            "metrics": [{"label": s["label"], "current": s["current"], "unit": s["unit"], "growth": s["growth"], "referenceLabel": "SS26 / 2025"} for s in row["signals"]]})
    results.append(row)

by_name = {b["company"]: b for b in results}
vs = by_name["Victoria's Secret & Co."]
vs["status"] = "team_input_candidate_pending_validation"
vs["signals"] = [
    ratio_signal("Peak live viewers", 3640000, 2520000, "viewers", "team_vs", "team_vs", metricType="peak_live_viewers", category="audience", matchedWindowsVerified=False),
    ratio_signal("YouTube views at approximately 20.5 hours", 20970000, 18570000, "views", "team_vs", "team_vs", metricType="youtube_views", category="audience", referenceClassification="estimated", estimateBasis="Baseline taken from Jaime's screenshot; derivation not available", matchedWindowsVerified=False),
    ratio_signal("Watch hours", 4800000, 2830000, "hours", "team_vs", "team_vs", reference_year=2024, metricType="watch_hours", category="audience", matchedWindowsVerified=False),
]
candidate, candidate_raw = index_of(vs["signals"])
vs["candidateIndex"] = candidate
vs["candidateIndexUnrounded"] = candidate_raw
vs["limitations"] = ["No independently verified public measurements for these inputs", "All three components measure overlapping viewing activity, not the standard three categories", "References mix 2025 and 2024", "Historical YouTube baseline is estimated and its basis is not available", "Matched elapsed capture windows unverified", "The screenshot's 71 differs from 69 under the later per-component 60–75 bounds"]
vs["nextInputsNeeded"] = ["Validate original audience measurements and capture timestamps", "Validate or replace the estimated YouTube reference", "Approve the mixed-year, overlapping-viewing exception before publication"]
vs["estimateSensitivity"] = []
for change in [-.1, 0, .1]:
    altered = [dict(s) for s in vs["signals"]]
    altered[1]["reference"] = float(dec(18570000) * (1 + dec(change)))
    display, exact = index_of(altered)
    vs["estimateSensitivity"].append({"illustrativeBaselineChange": change, "referenceViews": altered[1]["reference"], "candidateIndex": display, "candidateIndexUnrounded": exact})
vs["sensitivityNote"] = "Illustrative ±10% variation, not an empirically established uncertainty interval. Changing this estimate does not resolve the other evidence gaps."

tf = by_name["TOM FORD"]
tf["status"] = "single_signal_growth_only"
tf["contextMetrics"] = [
    {"label": "Estimated earned media value", "current": 13000000, "unit": "USD", "sourceId": "lefty_paris_ss27", "classification": "reported", "precision": "Published rounded value"},
    {"label": "Average engagement rate", "current": 4.3, "unit": "%", "sourceId": "lefty_paris_ss27", "classification": "reported"},
]
tf["reportedGrowth"] = {"metric": "Estimated earned media value", "growth": .35, "reference": "Reported year-over-year by source", "sourceId": "lefty_paris_ss27", "classification": "reported", "referenceValue": None}
tf["limitations"] = ["Only one reported comparable growth metric; historical absolute EMV and historical engagement rate not found. No blended index."]
tf["nextInputsNeeded"] = ["Historical comparable engagement rate or another independent current/reference signal", "Verify the source's historical EMV and comparison window"]
tf["customerContent"].update({"displayState": "1 signal · growth only", "metrics": [{"label": "Estimated media value", "current": 13000000, "unit": "USD", "reportedGrowth": .35}]})

louboutin = by_name["Christian Louboutin"]
louboutin["contextMetrics"] = [
    {"label": "Estimated earned media value", "current": 11500000, "unit": "USD", "sourceId": "lefty_paris_ss27", "classification": "reported", "precision": "Published rounded value"},
    {"label": "Average engagement rate", "current": 4.8, "unit": "%", "sourceId": "lefty_paris_ss27", "classification": "reported"},
]
louboutin["limitations"] = ["Lefty's current table uses the label Louboutin; official Loubi Show VI page provides event context only. No historical matched attention measurements found."]
louboutin["nextInputsNeeded"] = ["Previous same-season show EMV and engagement rate with matched scope and windows"]

gaps = {
    "GAP Inc": ("Campaign/news coverage found, but no matched current/reference event metrics. Gap brand measurements cannot represent the GAP Inc parent without explicit scope.", ["Choose a brand/division and a comparable event or campaign", "Two matched current/reference attention signals for that scope"], [{"url": "https://www.gapinc.com/en-us/articles/2025/02/gap-celebrates-comfort-and-confidence-in-new-feels", "purpose": "Campaign context from prior research; excluded from score"}]),
    "J.Crew": ("Campaign reviews found, but no matched quantitative attention measurements.", ["Select comparable annual or same-season campaigns", "Two matched current/reference attention signals"], [{"url": "https://theimpression.com/j-crew-fall-2026-ad-campaign-review/", "purpose": "Campaign context from prior research; excluded from score"}]),
    "ME+EM": ("Focused public search did not locate an event-specific comparable dataset. This is a research gap, not proof that no data exists.", ["Identify the comparable brand event or campaign", "Two matched current/reference attention signals"], []),
    "Moncler": ("Public FY2025 and H12026 presentations reviewed. Disclosed 2025 attention figures belong to different campaigns in the same year; no suitable 2026 pair found.", ["2026 and reference-edition metrics for the same campaign or event", "Two comparable categories, preferably reach and engagement or press volume"], [
        {"url": "https://www.monclergroup.com/v3/assets/blt61bda6b71f29a239/blt7225422691647ebd/69973d43b2ce65b7c8546796/Moncler-Group-FY-2025-Financial-Results-Presentation.pdf", "purpose": "Pages 8–9 contain different 2025 campaign scopes; excluded as a current/reference pair"},
        {"url": "https://www.monclergroup.com/v3/assets/blt61bda6b71f29a239/blt4b94a8a8df1b9ce5/6a60e6224e8afd725d30f0c0/Moncler-Group-H1-2026-Financial-Results-Presentation.pdf", "purpose": "Reviewed for matching 2026 inputs; none found"}]),
    "Marc Jacobs": ("Focused public search did not locate matched 2026/reference event measurements; current public Fashion Week tables reviewed do not provide a usable pair.", ["Identify a comparable show or campaign", "Two matched current/reference attention signals; reuse once for WHP Global and Marc Jacobs"], []),
    "DKNY": ("Official Fall 2026 Twin Muses campaign page confirms campaign context but provides no current/reference audience, engagement or media-volume metrics.", ["Comparable prior Fall campaign measurements", "Current and reference attention measurements under the same sampling rule"], [{"url": "https://www.dkny.com/pages/fall-2026-campaign", "purpose": "Official campaign page verified directly; context only"}]),
    "PacSun": ("Focused search returned business growth, store expansion and a 2025 community event, without matched event attention metrics. Sales/store counts are excluded.", ["Select a comparable brand event or campaign", "Two matched current/reference attention signals"], []),
    "Jacquemus": ("Focused searches returned marketing, follower and ecommerce context, without matched event attention measurements.", ["Select comparable same-season shows", "Two matched current/reference attention signals"], []),
    "Lafayette 148": ("Official Spring 2026 collection page confirms context and arrival in February 2026, but contains no quantitative attention comparisons. It is not a verified latest-event dataset.", ["Confirm latest comparable event and reference edition", "Two matched current/reference attention signals"], [{"url": "https://www.lafayette148ny.com/sp26-collection", "purpose": "Official collection page verified directly; context only"}]),
    "Lilly Pulitzer": ("Summer 2026 campaign release confirms context but provides no current/reference attention measurements; this does not establish the latest eligible event.", ["Confirm latest comparable event and reference edition", "Two matched current/reference attention signals"], [{"url": "https://fashionunited.com/press/fashion/lilly-pulitzer-debuts-summer-2026-campaign-at-coral-sands-inn-cottages-on-harbour-island-bahamas/2026061572976", "purpose": "Campaign release verified directly; context only"}]),
}
for name, (note, needed, context_sources) in gaps.items():
    row = by_name[name]
    row["limitations"] = [note]
    row["nextInputsNeeded"] = needed
    row["contextSources"] = context_sources

partial = sorted([b for b in results if b["index"] is not None], key=lambda b: (-b["index"], b["company"]))
retailers = [e for e in prospects["environments"] if e["type"] == "Retailer"]
output = {
    "title": "WWD Fashion Momentum — research results",
    "asOf": AS_OF, "scopeSource": prospects["source"],
    "coverage": {"uniqueProspects": 25, "environmentMappings": 26, "brands": 18, "retailers": 7,
        "publicProvisionalScores": 5, "teamInputCandidates": 1, "singleSignalGrowthOnly": 1,
        "insufficientComparableData": 11, "validatedProductionScores": 0},
    "methodology": {"growth": "current/reference - 1", "rawComponent": "50 * current/reference",
        "boundedComponent": "min(75, max(60, rawComponent))", "index": "Equal-weight average of usable bounded components",
        "rounding": "Round final display only, half-up", "minimumComponents": 2,
        "preferredCategories": ["audience/reach", "social engagement", "media coverage"],
        "publicFallback": "EMV and average engagement rate, disclosed as related influencer-post proxies",
        "missingData": "Null means unavailable, never zero; one usable comparison means growth only",
        "boundsSource": "https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793068484544519",
        "methodSource": "https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793067741340779",
        "notRevenueForecast": True},
    "sources": SOURCES, "brands": results,
    "partialDraftLeaderboard": {"label": "Five public-source provisional results only", "validated": False,
        "completeAcross18Brands": False, "crossBrandComparability": "Limited by measurement-window and proxy differences",
        "rows": [{"company": b["company"], "index": b["index"], "status": b["status"]} for b in partial],
        "exclusions": [b["company"] for b in results if b["index"] is None]},
    "retailerContent": {"contentKey": "shared-retailer-score-experience", "retailerSpecificIndex": None,
        "status": "partial_draft_only", "companies": [e["company"] for e in retailers],
        "draftLeaderboard": "partialDraftLeaderboard", "completeLeaderboardAvailable": False,
        "cta": "Unlock November signal"},
    "environments": [dict(e, contentStatus=("partial_draft_only" if e["type"] == "Retailer" else by_name[e["company"]]["status"]), qaStatus="pending") for e in prospects["environments"]],
    "publication": {"deployed": False, "showroomWinnerSelected": False, "reason": "Evidence and environment QA pending; no complete validated leaderboard"},
}
(ROOT / "score-results.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")

# Populate the working manifest with explicit draft/pending states; source mappings remain intact.
for b in prospects["brandContent"]:
    r = by_name[b["company"]]
    b.update({"index": r["index"], "signals": r["signals"], "scoreExperience": r["customerContent"],
        "researchNotes": {"status": r["status"], "limitations": r["limitations"], "nextInputsNeeded": r["nextInputsNeeded"], "resultsFile": "score-results.json"},
        "productionReady": False})
    if "candidateIndex" in r:
        b["candidateIndex"] = r["candidateIndex"]
prospects["environments"] = output["environments"]
prospects["presentation"]["status"] = "research draft generated; evidence QA and target app pending"
(ROOT / "prospects.json").write_text(json.dumps(prospects, indent=2, ensure_ascii=False) + "\n")

def pct(v):
    return f"{v:+.1%}"

lines = [
    "# Fashion Momentum — all-prospect results",
    "",
    "Research cutoff: **27 October 2026, 05:45 Berlin / 04:45 UTC**. Allen's final attendee list: **25 prospects, 18 brands + 7 retailers, 26 environment mappings**.",
    "",
    "**Five provisional public-source scores**, one separate team-input candidate, one growth-only result and eleven brands pending comparable data. No score is yet validated for production. This is the result of the public-source pass; additional matched measurements are needed to complete all brand scores.",
    "",
    "## Available public-source drafts",
    "",
    "These use two related signals: estimated earned media value (EMV) and average engagement rate (ER). Same-provider, same-season comparisons are available; matched collection windows and metric definitions still need verification. The sorted view covers these five brands only.",
    "",
    "| Brand | Provisional index | EMV current / reference | EMV change | Average ER current / reference | Relative ER change |",
    "| --- | ---: | ---: | ---: | ---: | ---: |",
]
for b in partial:
    emv, er = b["signals"]
    lines.append(f"| {b['company']} | **{b['index']}** | ${emv['current']/1e6:g}M / ${emv['reference']/1e6:g}M | {pct(emv['growth'])} | {er['current']:g}% / {er['reference']:g}% | {pct(er['growth'])} |")
lines += ["", "Reference: SS26 shows held in September **2025**. Current: SS27 shows held in September **2026**. Relative ER change is a ratio of rates; it is not the growth of engagement totals. EMV is estimated media value, not revenue.",
    "", "## Coverage of all 18 brands", "", "| Brand | Result | Missing input or qualification |", "| --- | --- | --- |"]
for b in results:
    if b["index"] is not None:
        state = f"{b['index']} — provisional public score"
        note = "2 proxy signals; matched-window validation pending"
    elif b["company"] == "Victoria's Secret & Co.":
        state, note = "69 — team-input candidate only", "Estimated YouTube baseline, mixed 2025/2024 references and overlapping viewing signals; excluded from public draft leaderboard"
    elif b["company"] == "TOM FORD":
        state, note = "EMV +35% YoY; no index", "Historical ER or another comparable category required"
    elif b["company"] == "Christian Louboutin":
        state, note = "Current EMV $11.5M / ER 4.8%; no index", "Historical same-season matched inputs required"
    else:
        state, note = "Comparable data pending", " / ".join(b["nextInputsNeeded"])
    lines.append(f"| {b['company']} | {state} | {note} |")
lines += ["", "Pending means no usable comparison was located in this public research pass, not that the brand has no data. Campaign descriptions, overall follower counts, sales growth and store counts do not substitute for matched event attention measurements.",
    "", "## Calculations and interpretation", "",
    "For each usable signal: **growth = current/reference − 1; raw score = 50 × current/reference; bounded score = min(75, max(60, raw score))**. Average bounded components equally, then round the final display half-up. Missing or zero baselines are excluded. Two components allow a disclosed index; one allows growth only.", "",
    "The 60–75 presentation bounds flatten both declines and strong growth. A 60 does not mean positive momentum. The score is not percentage growth, AI readiness or a sales forecast. Show actual growth beside the index.", "",
    "| Brand | EMV raw → bounded | ER raw → bounded | Mean → display |", "| --- | ---: | ---: | ---: |"]
for b in partial:
    a, c = b["signals"]
    lines.append(f"| {b['company']} | {a['rawScore']:.4f} → {a['boundedScore']:.4f} | {c['rawScore']:.4f} → {c['boundedScore']:.4f} | {b['indexUnrounded']:.4f} → {b['index']} |")
lines += ["", "Values shown here are formatted for readability; calculations use source inputs without intermediate rounding. Published EMV and rate inputs are already rounded. Source-reported EMV YoY: Burberry −36%, Fendi +28%, Coach +128%, Ralph Lauren −68%, Calvin Klein −52%. Recomputed growth differs slightly because the reports publish rounded inputs and their capture windows are not fully known.",
    "", "### Victoria's Secret candidate", "",
    "Jaime's team screenshot supplies peak viewers 3.64M / 2.52M (2025), YouTube views 20.97M / **estimated** 18.57M (2025, approximately 20.5 hours), and watch hours 4.80M / 2.83M (2024). Later per-component bounds produce **69**, rather than the earlier screenshot's 71. The candidate remains separate from the five public-source drafts. It does not meet the standard three-category definition.", "",
    "An illustrative ±10% change in the estimated YouTube baseline changes the display from 69 to 70 at the low-baseline end. This is a sensitivity example, not a validated confidence interval. The estimate basis, underlying provider and matched capture windows remain unverified.",
    "", "## Public evidence and remaining gaps", ""]
for sid, s in SOURCES.items():
    lines += [f"- [{s['title']}]({s['url']}) — {s['window']}. {s['verification']}."]
for b in results:
    if b["status"] == "insufficient_comparable_data":
        lines += ["", f"**{b['company']}:** {b['limitations'][0]}"]
        for s in b.get("contextSources", []):
            lines.append(f"- [Context source]({s['url']}) — {s['purpose']}.")
lines += ["", "## Prospect delivery mapping", "",
    "All seven retailers reuse the same brand leaderboard: **Exemplar Luxury Group, Amazon Fashion, NORDSTROM, Bloomingdales, Kohl's, Macys and Belmont Park Village**. Their own fashion-show index stays empty. The currently available shared view is a five-brand draft; it is not the requested full 18-brand leaderboard.", "",
    "Marc Jacobs content is generated once and reused in **WHP Global** and **Marc Jacobs**. Other parent/environment mappings remain exactly as supplied by Allen, including Fendi → LVMH, Coach → Tapestry, DKNY → G-III Apparel and Calvin Klein → PVH. Full 26-row mappings are in score-results.json and prospects.json.", "",
    "Customer content follows Bianca's compact score-and-metrics direction. CTA: **Unlock November signal**. The JSON includes draft display states and metrics. Evidence details should remain accessible. Deployment, analytics, environment QA and the showroom winner remain pending.", "",
    "## To complete the scores", "",
    "For each pending brand, obtain at least two current/reference measurements for the same event scope, provider and elapsed window. The next required fields are listed per brand above and in the JSON. Victoria's Secret needs validation of its team inputs and explicit exception handling. The five public drafts need matched-window/definition QA. No missing brand is assigned a fabricated baseline, score or rank.", "",
    "The public report summaries are sufficient for the five draft calculations. Provider exports or reproducible matched measurements would be needed to close the remaining gaps; Peter confirmed that no additional report exports are currently available.",
]
(ROOT / "score-results.md").write_text("\n".join(lines) + "\n")

# Meaningful arithmetic, missing-data and scope checks.
assert {b["company"]: b["index"] for b in partial} == {"Coach": 75, "Fendi": 69, "Ralph Lauren": 68, "Burberry": 64, "Calvin Klein": 62}
assert candidate == 69
assert index_of([ratio_signal("single", 2, 1, "count", "test", "test")]) == (None, None)
assert ratio_signal("floor", 1, 2, "count", "test", "test")["boundedScore"] == 60
assert ratio_signal("cap", 4, 1, "count", "test", "test")["boundedScore"] == 75
assert len(results) == 18 and len(retailers) == 7 and len(output["environments"]) == 26
assert len([b for b in results if b["status"] == "insufficient_comparable_data"]) == 11
assert len([e for e in output["environments"] if e["contentKey"] == "Marc Jacobs"]) == 2
assert all(b["index"] is None for b in results if b["status"] != "provisional_public_two_signal_score")
print(json.dumps({"coverage": output["coverage"], "publicDrafts": output["partialDraftLeaderboard"]["rows"], "teamCandidate": candidate, "checks": "passed"}, indent=2))

# Preserve the separately screened dossier context when rebuilding the score package.
if (ROOT / "dossier-evidence-manifest.json").exists():
    import runpy
    runpy.run_path(str(ROOT / "build-dossier-review.py"), run_name="__main__")

# Reapply all-prospect context, source review and tailored prompts after a rebuild.
if (ROOT / "build-prospect-packages.py").exists():
    import runpy
    runpy.run_path(str(ROOT / "build-prospect-packages.py"), run_name="__main__")
