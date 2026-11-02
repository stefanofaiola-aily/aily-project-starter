"""Generate the designer delivery reference from the saved evidence packages."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
packages = json.loads((ROOT / 'prospect-packages.json').read_text())['packages']
scores = json.loads((ROOT / 'score-results.json').read_text())
brand_lookup = {b['company']: b for b in scores['brands']}
ASOF = '2026-10-27'

def money(value):
    return '$' + f'{value / 1000000:.6f}'.rstrip('0').rstrip('.') + 'M'

def cell(text):
    return str(text).replace('|', '\\|').replace('\n', '<br>')

def state_and_data(package, brand):
    name = package['company']
    if package['type'] == 'Retailer':
        return ('Shared brand board', 'No retailer-specific fashion-show index. Shared five-brand provisional board; public snapshot below.',
                'Validate underlying brand evidence and shared-board scope; resolve this live environment ID. Separate Retail Momentum scoring has no agreed method or collected comparison dataset.')
    if brand['index'] is not None:
        emv, er = brand['signals']
        return ('Provisional score',
                f"Index **{brand['index']}** · 2 proxy signals\nEMV {money(emv['current'])} / {money(emv['reference'])} ({emv['growth']:+.1%})\nAverage ER {er['current']:g}% / {er['reference']:g}% ({er['growth']:+.1%} relative)",
                'Validate current/reference event windows, provider/platform/geographic scope and definitions; review average ER as a disclosed proxy. Preserve two-signal/provisional wording. An independent audience or press-volume pair would improve coverage but is not mandatory for the permitted two-signal draft.')
    if name == 'TOM FORD':
        return ('Growth only',
                'Reported EMV **+35% YoY**; current EMV **$13M**, current average ER **4.3%**. Historical absolute values unavailable; no index.',
                'Verify the reported YoY event/reference scope and window; obtain historical comparable ER or another matched attention pair for a two-signal index. Do not reconstruct an undocumented historical EMV input.')
    if name == 'Christian Louboutin':
        return ('Current values', 'Current EMV **$11.5M**, current average ER **4.8%**. No growth or index.',
                'Obtain previous same-season EMV and ER with matched provider scope/windows; confirm the report’s Louboutin label and event identity. Then validate both comparisons.')
    if name == "Victoria's Secret & Co.":
        return ('Context only; score candidate in internal review',
                'Internal candidate **69**. Peak viewers 3.64M / 2.52M (2025); YouTube views 20.97M / estimated 18.57M (2025, approximately 20.5 hours); watch hours 4.80M / 2.83M (2024). Candidate stays out of customer score and board.',
                'Validate underlying audience sources/capture timestamps; validate or replace the estimated YouTube baseline; review sensitivity and disclose mixed years/overlapping viewing measures. These are not three independent categories.')
    gap = '; '.join(package['nextInputsNeeded'])
    if name == 'DKNY':
        gap += '. Resolve Harriet’s suggested G-III → Marc Jacobs mapping against Allen’s final DKNY → G-III mapping before loading this environment'
    if name == 'Marc Jacobs':
        gap += '. Keep both mappings; confirm WHP’s intended proxy brand if the “biggest brand” proposal is adopted'
    return ('Context only', 'No matched attention comparisons or index. Current public snapshot and source examples below.', gap + '.')

rows = []
for package in packages:
    brand = brand_lookup.get(package['company'])
    state, current, gap = state_and_data(package, brand)
    presence = package['publicPresenceReview']
    rows.append({
        'company': package['company'], 'audienceType': package['type'],
        'environments': package['environments'], 'screenStateNow': state,
        'currentScoreDataDisplay': current, 'dataNeededForFinalScoreOrBoard': gap,
        'scoreIndex': brand['index'] if brand else None,
        'internalCandidateIndex': brand.get('candidateIndex') if brand else None,
        'scoreInputs': brand.get('signals', []) if brand else [],
        'currentOnlyProviderMetrics': brand.get('contextMetrics', []) if brand else [],
        'reportedGrowth': brand.get('reportedGrowth') if brand else None,
        'eventMetadata': brand.get('event') if brand else None,
        'publicAccounts': presence['accounts'], 'mediaSources': presence['mediaItems'],
        'publicPresenceGaps': presence['gaps'],
        'publicPresenceEligibleForIndex': False,
        'invitation': package['customerContent']['invitation'],
        'internalDataFields': package['commercialContext']['internalDataFields'],
        'cta': package['customerContent']['cta'],
        'promptFile': package['promptFile'],
        'scoreProductionValidated': False, 'applicationImplemented': False,
    })

assert len(rows) == 25 and sum(len(r['environments']) for r in rows) == 26
assert Counter(r['audienceType'] for r in rows) == {'Brand': 18, 'Retailer': 7}
assert sum(r['screenStateNow'] == 'Provisional score' for r in rows) == 5
assert all(r['scoreIndex'] is None for r in rows if r['audienceType'] == 'Retailer')
assert next(r for r in rows if r['company'] == 'Marc Jacobs')['environments'] == ['WHP Global', 'Marc Jacobs']
assert next(r for r in rows if r['company'] == 'DKNY')['environments'] == ['G-III Apparel']
assert all(r['cta'] == 'Unlock November signal' for r in rows)
assert all(not r['scoreProductionValidated'] and not r['publicPresenceEligibleForIndex'] for r in rows)
out = {'title': 'Designer delivery reference — Fashion Momentum', 'dataAsOf': ASOF,
       'scope': {'prospects': 25, 'environmentMappings': 26, 'brands': 18, 'retailers': 7},
       'purpose': 'Design actual available content and missing-data states; final score validation, app implementation and deployment remain pending.',
       'sourceFiles': ['prospect-inputs.json', 'prospect-packages.json', 'score-results.json', 'public-presence-review.json'],
       'deliveryOrderProposal': 'Fashion brands first; retailer-specific scoring second. Existing shared retailer board remains in scope.',
       'harrietSource': 'https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793082417194649',
       'retailMomentumMethod': 'Proposed separate Q3-vs-prior-year or YTD approach; period, measures and reference scope not agreed or collected.',
       'prospects': rows}
(ROOT / 'delivery-table.json').write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')

lines = ['# Designer delivery table — Fashion Momentum', '',
    '**Earlier attention-method snapshot.** Peter’s later request uses IR 50% / Social 30% / Trend 20% and four pages. Use the [weighted delivery reference](weighted-delivery.md) for that structure. The indices below belong to the earlier method and must not populate weighted score fields.', '',
    '**Reference for design, content, app and data review.** Saved data as of **27 October 2026**. Covers Allen’s final **25 prospects / 26 environments**. Use the current data below for designs, with the stated display labels and empty states. Application implementation and all production score validations remain pending.', '',
    'Follow the [step-by-step designer workflow](designer-workflow.md) to turn this content into reusable layouts, a clickable review flow and an app handoff.', '',
    'The original methodology permits an explicit two-signal draft, growth only with one usable comparison, and current social context without a historical comparison. Our five calculated drafts use related EMV/average-ER proxies; their matched windows and the ER proxy still need review. EMV is estimated media value. Relative ER growth is not growth of engagement totals. The 60–75 bounds can conceal declines; show actual growth beside any index.', '',
    '## Screen states designers need', '',
    '| Screen state | Main area | Supporting content | Final-release requirement |',
    '| --- | --- | --- | --- |',
    '| Provisional score — 5 brands | Eligible draft numeral with “Provisional · 2 signals” | Current/reference EMV and average ER, actual growth, event/reference label and accessible evidence | Validate the pairs and explicitly review proxy use; remain partial/provisional until that is resolved |',
    '| Growth only — TOM FORD | Reported EMV +35% YoY; no blended index | Current provider values labelled current-only, source and reference scope | Verify reported growth; a second matched pair is needed to create an index |',
    '| Current values — Louboutin | Current EMV and average ER; no growth or index | Dated public snapshot and source context | Obtain and validate historical comparable values |',
    '| Context only — 10 other brands and VS | Public snapshot and compact “Comparable data pending” state | Source examples, scope/date labels and personalized invitation | Obtain matched comparisons; VS candidate stays in internal review until validated |',
    '| Shared brand board — 7 retailers | Same partial provisional brand view; no retailer-specific fashion-show score | Retailer’s own public snapshot and invitation | Validate the underlying brand board. A future Retail Momentum ranking needs separate agreed methodology/data |', '',
    'All states use a sleek black Agent Playground surface, dominant available metrics, short labels, accessible details and **Unlock November signal**. Empty values do not become zero, fabricated scores, invented ranks or decorative sample numbers. Keep the Fashion Momentum label distinct from the AI-readiness quiz. The state table specifies layouts; it does not certify any current score for production.', '',
    '## Per-prospect delivery table', '',
    'Score inputs below are **current / reference**, with the reference year shown where available. For the five public drafts: SS27 shows in September 2026 versus SS26 shows in September 2025. Exact individual show dates and matched provider windows need completion/validation before final content. Rows are in Allen’s list order, not a ranking.', '',
    '| Prospect | Environment(s) | Screen state now | Current methodology data | Data needed for final score/board |',
    '| --- | --- | --- | --- | --- |']
for row in rows:
    lines.append('| ' + ' | '.join(cell(x) for x in [row['company'], ' / '.join(row['environments']), row['screenStateNow'], row['currentScoreDataDisplay'], row['dataNeededForFinalScoreOrBoard']]) + ' |')
lines += ['', '## Current public snapshot values', '',
    'These values are **context outside the momentum calculation**. Followers and selected-post responses were observed on October 27, 06:21–06:26 UTC. Counters accumulated until observation; they were not captured at equal post ages. The primary public-grid sample was up to three visible posts dated September 20–October 19. “Recent supplement” and “campaign pilot” exceptions are shown. No full-account average, reach, sentiment, media-volume total or cross-prospect rank is inferred.', '',
    'The post column shows **selected own-account posts / posts with visible main like counts**. Related-account posts are separate context and excluded from those responses. Unavailable counts stay empty in the UI. Exemplar’s banner audiences are never summed. Media examples may be older, owned, affiliate or company-issued; show category and date rather than presenting every source as recent editorial coverage.', '',
    '| Prospect | Matched profile / followers | Own posts / visible like totals | Selected own-post likes | Sampling and scope notes | Verified source examples / date / type |',
    '| --- | --- | --- | --- | --- | --- |']
for row in rows:
    profiles, counts, likes, notes = [], [], [], []
    for a in row['publicAccounts']:
        summary = a['sampleSummary']
        profiles.append(f"[@{a['handle']}]({a['url']}) **{a['followersDisplay']}**")
        counts.append(f"@{a['handle']}: {summary['ownAccountPosts']} / {summary['ownPostsWithVisibleLikes']}")
        likes.append(f"@{a['handle']}: {summary['ownSampleLikesRangeDisplay']}")
        exceptions = [ {'supplement': 'recent supplement', 'campaign_pilot': 'retained campaign pilot'}.get(x, x) for x in summary['selectionExceptions']]
        own_primary = summary['primaryOwnAccountPosts']
        notes.append(f"@{a['handle']}: {a['scope']}; {own_primary} primary own-account sample posts" + (f"; {', '.join(exceptions)}" if exceptions else '') + (f"; {summary['relatedAccountPosts']} related-account posts excluded" if summary['relatedAccountPosts'] else ''))
    sources = [f"[{m['publisher']}]({m['url']}) · {m['published'] or 'publication date unverified'} · {m['category']}" for m in row['mediaSources'] if m['verifiedText']]
    lines.append('| ' + ' | '.join(cell(x) for x in [row['company'], '\n'.join(profiles), '\n'.join(counts), '\n'.join(likes), '\n'.join(notes), '\n'.join(sources) or 'No article verified in this discovery pass']) + ' |')
lines += ['', 'Post-level like/comment values, URLs, publication dates and access gaps are in [public-presence-review.md](public-presence-review.md). Do not use unverified publication dates to classify a source as current coverage. Launchmetrics share observations with unverified year/cutoff remain supporting research details.', '',
    '## Personalized action copy', '',
    'CTA label for every row: **Unlock November signal**. These invitations propose internal-data analysis; they do not establish an active upload flow or predict November revenue. Use the field lists in the structured package if implementing a real data request.', '',
    '| Prospect | Short invitation | Prompt / detailed inputs |', '| --- | --- | --- |']
for row in rows:
    lines.append(f"| {cell(row['company'])} | {cell(row['invitation'])} | [Prompt]({row['promptFile']}) |")
lines += ['', '## What is needed for the final outcome', '',
    '| Workstream | Prepared now | Needed next | Acceptance evidence |',
    '| --- | --- | --- | --- |',
    '| Design | Real prospect data, five screen states and invitations | Apply existing Agent Playground components; design score/context/empty/shared-board states; keep source detail/date labels accessible | Reviewed designs use the actual values and clear evidence labels, correct board states and exact CTA |',
    '| Data — score inputs | Five calculated drafts, one reported growth-only result, Louboutin current values and VS internal candidate | Complete the per-row gaps; event/date/cutoff/reference metadata; matched definitions/provider/platform/geography/post-age windows; report precision; disclosed estimates/proxies | At least two validated current/reference pairs for each displayed index; one comparison shown as growth only; no fabricated baseline |',
    '| Data — public context | Profiles, selected posts and classified source examples for every prospect | Retain dates, unavailable counters, sample exceptions and ownership boundaries; verify missing media dates before calling them current | Source-backed snapshot with no invented reach, full-account ER, article-volume total or historical growth |',
    '| App and routing | Allen’s exact 26 display-name mappings and structured packages | Resolve target app/content schema and live IDs; place card above WWD quiz; reuse Marc Jacobs and the shared retailer board | Correct brand/state/content in all 26 environments, with no parent-group substitution |',
    '| CTA and analytics | Exact label and proposed invitation copy | Final destination/confirmation; existing authenticated click-event conventions | Click event observed in analytics and confirmation accurately reflects the next step |',
    '| Board and showroom | Partial five-brand provisional view; no winner selected | Validate comparable board coverage; label any interim board partial; choose eligible showroom content only after comparison/QA | Consistent units and scope, actual growth visible, appropriate ties, missing brands unranked and justified showroom selection |',
    '| QA | Acceptance checklist and testers named in original handoff | Jimena and Franziska to review all environments and showroom as originally requested | Correct mapping, metrics, state, bar/highlight, details, CTA and analytics documented |', '',
    'An independent third attention category improves coverage but is not required by the original methodology’s explicit two-signal allowance. Across-brand comparison still needs a consistent set of definitions and windows. No displayed score is a percentage growth, AI-readiness measure or revenue forecast.', '',
    '## Open mapping and retailer-method decisions', '',
    'Harriet’s [later update](https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793082417194649) proposes brands-first delivery and separate retailer scoring. Q3-versus-prior-year versus YTD remains an open choice; measures/provider/scope are not agreed or collected. Designers may plan a separate Retail Momentum view as a future variant, without populating scores or merging those rankings with the fashion board.', '',
    'Keep Allen’s mappings unless explicitly revised: **Fendi → LVMH**, **Coach → Tapestry**, **Calvin Klein → PVH**, **Marc Jacobs → WHP Global and Marc Jacobs**, **DKNY → G-III Apparel**. Harriet’s G-III → Marc Jacobs suggestion conflicts with the final list; resolve it before loading G-III. WHP’s “biggest brand” suggestion does not verify Marc Jacobs as its biggest brand. Additional company examples in that message do not expand the 25-prospect scope.', '',
    '## Maintaining this reference', '',
    'Generated from the saved prospect packages and score evidence by `build-delivery-table.py`, invoked through `build.py`. Update captured inputs/builders when new evidence or an accepted mapping decision arrives; regenerate the table so design and data stay aligned. This is a dated snapshot, not a live research feed.', '',
    '[Structured delivery data](delivery-table.json) · [Implementation handoff](implementation-handoff.md) · [Score evidence](score-results.md) · [All-prospect review](review.md)', '']
(ROOT / 'delivery-table.md').write_text('\n'.join(lines).rstrip() + '\n')
print('Designer delivery reference generated: 25 prospects, 26 mappings; no score or mapping changes.')
