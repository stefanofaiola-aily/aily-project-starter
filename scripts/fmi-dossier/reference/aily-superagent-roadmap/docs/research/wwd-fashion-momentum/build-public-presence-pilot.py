"""Record a focused public social/media feasibility review, separate from indices."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AS_OF = '2026-10-27T05:57:32Z'
POSTS = [
 {'company':'J.Crew','handle':'jcrew','format':'Reel','published':'2026-09-22','url':'https://www.instagram.com/reel/DdlzuDBhXn4/','label':'Barn Jacket anniversary launch','likesDisplay':'14.6K','likesApproximate':14600,'likesRounded':True,'comments':414,'searchSnippetLikes':9208,'note':'Search snippet was stale relative to the directly inspected post; do not use the snippet as the measured value.'},
 {'company':'J.Crew','handle':'jcrew','format':'Photo/carousel post','published':'2026-09-22','url':'https://www.instagram.com/p/DdmHVwvoFH3/','label':'One iconic jacket, 160 ways','likesDisplay':'7.3K','likesApproximate':7300,'likesRounded':True,'comments':225},
 {'company':'J.Crew','handle':'jcrew','format':'Photo/carousel post','published':'2026-09-28','url':'https://www.instagram.com/p/Dd1UJHwIKQt/','label':'Barn Jacket friends follow-up','likesDisplay':'2.1K','likesApproximate':2100,'likesRounded':True,'comments':20},
 {'company':'ME+EM','handle':'meandem','format':'Reel','published':'2026-10-20','url':'https://www.instagram.com/meandem/reel/DeuUeL4EhXY/','label':'Recent public Reel','likesDisplay':'2.4K','likesApproximate':2400,'likesRounded':True,'comments':118},
 {'company':'ME+EM','handle':'meandem','format':'Photo post','published':'2026-10-19','url':'https://www.instagram.com/meandem/p/DeriH6QAc6n/','label':'The finishing touches','likesDisplay':'431','likesApproximate':431,'likesRounded':False,'comments':4},
 {'company':'ME+EM','handle':'meandem','format':'Reel','published':'2026-10-18','url':'https://www.instagram.com/meandem/reel/Deo9LUjlK1F/','label':'Recent public Reel','likesDisplay':'707','likesApproximate':707,'likesRounded':False,'comments':13},
]
for p in POSTS:
    p.update({'classification':'direct_public_observation','observedAt':AS_OF,
       'collectionWindow':'Accumulated visible counters inspected on 27 October, not counters captured seven days after posting',
       'views':None,'reach':None,'saves':None,'shares':None,'priorComparable':None,
       'eligibleForMomentumFormula':False,'selection':'Purposive feasibility sample; not a complete campaign or account census'})

MEDIA = [
 {'company':'J.Crew','event':'Barn Jacket 40th anniversary campaign','publisher':'Marie Claire','title':"J.Crew's Barn Jacket Turned 40. To Celebrate, the Brand Dropped the Cult Classic in New Colors and Prints",'published':'2026-09-22','url':'https://www.marieclaire.com/fashion/fall-fashion/jcrew-barn-jacket-40th-anniversary-collection/','access':'Full public article directly read','category':'Editorial shopping coverage with affiliate disclosure','usesCompanyMaterials':True},
 {'company':'J.Crew','event':'Barn Jacket 40th anniversary campaign','publisher':'The Fashionisto','title':'J.Crew Goes All In on the Barn Jacket','published':'2026-09-24','url':'https://www.thefashionisto.com/story/jcrew-barn-jacket-campaign-2026/','access':'Public article and publication date directly inspected','category':'Editorial campaign commentary','usesCompanyMaterials':True},
]
for m in MEDIA:
    m.update({'classification':'verified_public_article','observedAt':AS_OF,
        'estimatedAudience':None,'eligibleForMomentumFormula':False,
        'note':'Observed coverage item; no audience value or complete media-volume estimate inferred'})

ACCOUNT = {
 'company':'ME+EM','primaryProfile':'https://www.instagram.com/meandem/',
 'publicFollowersDisplay':'1.1M','followersRounded':True,
 'classification':'direct_public_observation','observedAt':AS_OF,
 'providerReport':{'url':'https://hypeauditor.com/instagram/meandem/','updatedLabel':'October 2026',
   'followersReported':1120218,'engagementRateReportedPercent':0.87,
   'averageLikesReported':610,'averageCommentsReported':9,
   'followerGrowthReportedPercent':1.82,'followerGrowthWindowVerified':False,
   'classification':'third_party_reported','eligibleForMomentumFormula':False,
   'qualityIssue':'Reported 0.87% ER does not reconcile with (610+9)/1,120,218 = about 0.0553%. Different windows or definitions may explain it; the public report does not establish equivalence. Do not blend or treat this as a validated rate.',
   'excluded':'Creator income, net worth, authenticity scores and provider rank are not brand commercial performance or momentum.'},
 'providerMethodology':{'url':'https://hypeauditor.com/collect-analyze-influencer-data/',
   'verified':'Public information plus statistical/proprietary processing; reports typically refresh weekly; provider says it does not access private DMs or account Insights.',
   'limitation':'General method page does not resolve the sampled report’s ER denominator or measurement windows.'},
 'visibleGrid':{'postsObserved':12,'dateRange':'2026-10-17 through 2026-10-26','completeAccountCensus':False,
   'note':'Profile links and displayed image descriptions inspected; this is not a verified total posting frequency.'}}

METHOD = {
 'purpose':'Add source-backed current public-presence tiles to the prospect experience while preserving existing score eligibility.',
 'instagram':[
  'Verify the official brand account through the brand site or matching profile identity; retain brand, parent and division scope.',
  'For event momentum, enumerate all relevant official posts in the same -3/+7-day event window for both editions, record format and date, and compare counters at matched ages when historic captures exist.',
  'Without historic captures, label observed current counters as a snapshot. Do not invent seven-day historical counters or compare today’s old-post counters as though they were measured at equal age.',
  'For a current account audit, use a predefined chronological sample such as the latest 20 eligible posts in a fixed date range; disclose sample completeness and split Reels from photo/carousel posts. Do not sample only viral posts.',
  'Use median likes/comments per post to reduce domination by one celebrity post; report visible video views separately when accessible. A current follower-normalized interaction proxy must name its denominator and is not reach-based engagement.',
  'Reach, impressions, saves, shares, website clicks, paid versus organic allocation and attribution are absent from this pilot. Owner Insights or a documented provider would be needed to fill these fields.',
 ],
 'media':[
  'Define one publisher panel, language and geography for all brands, and explicit current/reference event windows. A separate calendar-period presence view can use matched 28-day windows, but that changes the comparison from event momentum.',
  'Record title, URL, publication date, event relevance, publisher, brand scope and editorial/press-release/shopping category for each item.',
  'Deduplicate canonical URLs and syndicated/reprinted stories. Keep company releases and republications separate from editorial coverage; classify affiliate shopping articles visibly.',
  'Count verified distinct stories and publishers within the defined panel. Call this observed coverage in the panel, not all internet coverage. Paywalled or inaccessible sources have explicit unknown states.',
  'Compare current/reference counts only under the same retrieval and inclusion rules; search-engine estimated result totals are not article counts. Article counts do not establish sentiment, readership or sales.',
 ],
 'mediaPanelProposal':['Vogue','WWD','The Impression','FashionUnited',"Harper’s Bazaar",'Marie Claire','InStyle','The Fashionisto','Town & Country','The Hollywood Reporter'],
 'scoreRule':'Original indices unchanged. Add a new comparable category only after its pair and scope are validated. A separately defined current-presence score would need its own disclosed rubric; no such numeric score is assigned here.',
 'retailers':'Keep their shared brand board. Their own social presence can be a separate audit but cannot be represented as a retailer fashion-show index.',
}
IDEAS = [
 {'idea':'Campaign response relative to the brand’s usual posts','value':'Shows whether an event stands out for that brand rather than rewarding the biggest follower base','requirement':'Same formats and matched counter ages, complete or clearly defined samples; keep observational and non-causal'},
 {'idea':'Creator amplification','value':'Separates response on the brand’s own account from attention on creator accounts','requirement':'Verified campaign-related creator posts; label overlapping audiences and do not sum followers as unique reach'},
 {'idea':'Brand and hero-product search interest','value':'Helps distinguish broad brand attention from interest in a specific bag, jacket or dress','requirement':'Same Google Trends topic/query, geography, time range and normalization; keep separate from approved score categories'},
 {'idea':'Public product availability','value':'Makes the invitation tangible: attention around a hero product versus visible sizes/colors available','requirement':'Timestamped observations from official shops; a public out-of-stock state does not prove sales or demand'},
 {'idea':'YouTube and TikTok video response','value':'Extends beyond Instagram where official campaign/show videos are public','requirement':'Verified official videos, matched elapsed windows and separate platforms; cumulative views are not unique audience'},
]
OUTPUT = {'title':'Public social and media presence — feasibility pilot','asOf':AS_OF,
 'scope':{'brandsSampled':['J.Crew','ME+EM'],'officialInstagramPostsInspected':6,
  'verifiedEditorialArticles':2,'allProspectSocialAuditCompleted':False,'newComparableIndices':0},
 'instagramPosts':POSTS,'accountSnapshot':ACCOUNT,'verifiedMediaItems':MEDIA,
 'observedMediaSummary':{'company':'J.Crew','verifiedDistinctPublishersInThisPilot':2,
  'completeCoverage':False,'priorComparableCount':None,'eligibleForMomentumFormula':False},
 'accessNotes':['Instagram primary pages were readable without sign-in for the sampled posts and profile.',
  'J.Crew HypeAuditor report hit a security-verification page; no challenge was solved and no metrics taken from that page.',
  'Town & Country article navigation failed; retained as a search-discovered candidate, not a verified article.',
  'No owner Insights, provider exports, subscription reports or private account data accessed.'],
 'method':METHOD,'additionalIdeas':IDEAS,
 'conclusion':'Public signals can enrich the prospect teasers immediately. This pilot does not establish full social performance, comprehensive media volume or matched historical momentum.'}
assert len(POSTS)==6 and len(MEDIA)==2
assert all(p['priorComparable'] is None and not p['eligibleForMomentumFormula'] for p in POSTS)
assert len({m['publisher'] for m in MEDIA})==2
(ROOT/'public-presence-pilot.json').write_text(json.dumps(OUTPUT,indent=2,ensure_ascii=False)+'\n')

lines=['# Public Instagram and media coverage — pilot and recommendation','',
 '**Yes: these channels can provide useful additional external signals.** This focused review verified six official Instagram posts across J.Crew and ME+EM, ME+EM’s public account size, and two editorial items about J.Crew’s campaign. It is a feasibility pilot, not an all-prospect audit. No new index is assigned.','',
 'Inspected 27 October 2026; recorded at **06:57 Berlin / 05:57 UTC**. Public counters change and some are rounded.','',
 '## Overall standing','',
 '- All 25 prospects have research/copy drafts and prompts, mapped to Allen’s 26 environments.','- The 18 brands have five provisional public indices, one separate VS candidate, one growth-only result and eleven missing comparisons.','- The seven retailers share the brand board; it remains a partial provisional view.','- Company context is covered through 24 Light dossier matches and official Exemplar context. Production source validation and app delivery remain pending.','',
 '## What the online pilot found','',
 '| Brand | Official post | Date | Public likes | Public comments |','| --- | --- | --- | ---: | ---: |']
for p in POSTS:
    lines.append(f"| {p['company']} | [{p['label']}]({p['url']}) | {p['published']} | {p['likesDisplay']} | {p['comments']} |")
lines += ['','These are selected post snapshots, not full campaign totals, representative averages or comparable growth. J.Crew’s posts had around a month to accumulate engagement; ME+EM’s had roughly a week. Formats differ. Do not compare these samples as a brand ranking. No visible views/reach/saves/shares were collected.','',
 'The search snippet listed 9,208 likes for J.Crew’s launch Reel, while the directly inspected page displayed **14.6K**. Collect counts from primary pages and retain observation dates; search snippets are discovery pointers.','',
 '**ME+EM profile:** the [official Instagram page](https://www.instagram.com/meandem/) displays approximately **1.1M followers**. Its [HypeAuditor report](https://hypeauditor.com/instagram/meandem/) lists 1,120,218 followers and 0.87% engagement for October 2026. Its reported 610 average likes and 9 average comments imply about 0.0553% under a simple follower-based formula, so the public fields do not reconcile. The provider’s windows/definitions would need resolving before using that rate. No creator-earnings estimates or account-quality scores are used.','',
 'The [provider methodology](https://hypeauditor.com/collect-analyze-influencer-data/) describes public data, statistical/proprietary processing and typical weekly refreshes. It does not resolve this account report’s denominator or windows.','',
 '**Media:** two distinct publishers were directly verified for J.Crew’s Barn Jacket campaign:']
for m in MEDIA:
    lines.append(f"- [{m['publisher']} — {m['title']}]({m['url']}) ({m['published']}): {m['category']}.")
lines += ['','This is **two verified examples**, not a claim of only two articles or an exhaustive media count. Both use campaign materials; Marie Claire discloses affiliate shopping links. Company releases and syndicated copies must be separated from editorial coverage.','',
 '## Recommended prospect experience','',
 'Keep the Fashion Momentum index where the existing evidence supports it. Add a small **public-presence snapshot** to provide useful content when the historical index is missing: current public post response, observed media coverage and an internal-data invitation. Use an observation date and evidence-coverage label. Keep full audit details under the information control.','',
 'Suggested fields: **Instagram response**, **editorial coverage in the defined panel**, and optionally **search interest**. Leave unknown fields empty. Follower size supplies context; it does not establish momentum or reached audience. A broader current-presence numeric score would have a different methodology and should be named and explained separately.','',
 '## Consistent collection method','', '### Instagram',''] + [f'{i}. {v}' for i,v in enumerate(METHOD['instagram'],1)]
lines += ['', '### Media coverage',''] + [f'{i}. {v}' for i,v in enumerate(METHOD['media'],1)]
lines += ['','Proposed initial panel: '+', '.join(METHOD['mediaPanelProposal'])+'. This is a proposal; the pilot did not exhaustively search this panel.','',
 '## Further ideas worth using','']
for i in IDEAS:
    lines += [f"- **{i['idea']}:** {i['value']}. Requires: {i['requirement']}."]
lines += ['','## Practical next layer','',
 '1. Extend the public-presence snapshot to the 18 brand packages using verified official accounts and a fixed sample. Preserve the shared retailer board.','2. Build the dated article ledger within the same publisher panel for current and reference event windows. Show completeness and inaccessible sources.','3. Promote measurements into the original momentum calculation only when at least two comparable pairs exist. Preserve separate current-only context otherwise.','4. Use the gaps to make the CTA concrete: internal sales/stock data can help investigate whether visible attention aligns with product demand and availability.','',
 'This route can improve the usefulness of every teaser without waiting for a full provider export. It cannot recreate historical social capture windows or guarantee complete media coverage from ordinary web search.','',
 f'[Structured pilot data]({ROOT / "public-presence-pilot.json"}) · [All-prospect review]({ROOT / "review.md"})','']
(ROOT/'public-presence-pilot.md').write_text('\n'.join(lines).rstrip()+'\n')
print(json.dumps(OUTPUT['scope'],indent=2))
