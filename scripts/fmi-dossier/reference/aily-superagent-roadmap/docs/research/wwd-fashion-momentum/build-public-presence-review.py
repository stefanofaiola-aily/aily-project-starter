"""Build a scoped public snapshot from observations; never infer momentum from it."""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOCIAL = json.loads((ROOT / 'social-presence-observations.json').read_text())
MEDIA = json.loads((ROOT / 'media-presence-observations.json').read_text())
PILOT = json.loads((ROOT / 'public-presence-pilot.json').read_text())
PROSPECTS = json.loads((ROOT / 'prospects.json').read_text())
START, END = '2026-09-20', '2026-10-19'
ASOF = '2026-10-27'

def number(display):
    if display is None:
        return None
    text = display.replace(',', '').strip()
    suffix = text[-1].upper()
    multiplier = {'K': 1000, 'M': 1000000}.get(suffix, 1)
    return round(float(text[:-1] if multiplier != 1 else text) * multiplier)

def instant(hhmm):
    return f'{ASOF}T{hhmm}Z'  # Preserve the recorded minute precision.

def period(date):
    if date is None:
        return 'publication_date_unverified'
    if START <= date <= END:
        return 'within_social_selection_window'
    if date < START:
        return 'older_context'
    return 'after_social_selection_window'

def account(row):
    h = row['handle']
    posts = []
    for path, likes, comments, published, observed, exception in row['posts']:
        match = re.match(r'^/([^/]+)/(?:p|reel)/', path)
        owner = match.group(1) if match else h
        related = owner != h
        selection = exception or 'date_eligible_visible_grid_sample'
        posts.append({
            'url': 'https://www.instagram.com' + path,
            'profileHandle': h, 'postOwnerHandle': owner,
            'ownershipBasis': 'Username in observed post URL' if match else 'Verified J.Crew post identity in retained pilot',
            'scope': 'related_account_context' if related else 'matched_account_post',
            'includedInOwnAccountSummary': not related,
            'format': 'Reel' if '/reel/' in path else 'Photo/carousel (not separated)',
            'published': published, 'observedAt': instant(observed),
            'observationTimePrecision': 'minute',
            'likesDisplay': likes, 'likesApproximate': number(likes),
            'commentsDisplay': comments, 'commentsApproximate': number(comments),
            'countsRounded': any(v and v[-1].upper() in 'KM' for v in [likes, comments]),
            'likesState': 'visible' if likes is not None else 'unavailable',
            'commentsState': 'visible' if comments is not None else 'unavailable',
            'selection': selection, 'withinSelectionDateWindow': START <= published <= END,
            'views': None, 'reach': None, 'saves': None, 'shares': None,
            'paidOrganicSplit': None, 'priorComparable': None,
            'eligibleForMomentumFormula': False,
            'collectionWindow': 'Accumulated visible counters on October 27; not measured at equal post age or at seven days',
        })
    own = [p for p in posts if p['includedInOwnAccountSummary']]
    visible = [p for p in own if p['likesApproximate'] is not None]
    if visible:
        low = min(visible, key=lambda p: p['likesApproximate'])
        high = max(visible, key=lambda p: p['likesApproximate'])
        likes_range = low['likesDisplay'] if low is high else f"{low['likesDisplay']}–{high['likesDisplay']}"
    else:
        likes_range = 'Unavailable'
    return {
        'handle': h, 'url': f'https://www.instagram.com/{h}/',
        'identityVerification': 'Official Exemplar company site links to banner account' if row['company'] == 'Exemplar Luxury Group'
            else 'Linked from official Victoria’s Secret shop footer' if h == 'victoriassecret'
            else 'Search-discovered profile matched by visible name/bio/domain; independent official-site link not verified in this pass',
        'scope': row['scope'], 'followersDisplay': row['followers'],
        'followersApproximate': number(row['followers']), 'followersAreReach': False,
        'observedAt': instant(row['observed']), 'observationTimePrecision': 'minute',
        'posts': posts, 'sampleSummary': {
            'inspectedPosts': len(posts), 'ownAccountPosts': len(own),
            'relatedAccountPosts': len(posts) - len(own),
            'ownPostsWithVisibleLikes': len(visible),
            'ownSampleLikesRangeDisplay': likes_range,
            'primaryOwnAccountPosts': sum(p['selection'] == 'date_eligible_visible_grid_sample' for p in own),
            'selectionExceptions': sorted({p['selection'] for p in posts if p['selection'] != 'date_eligible_visible_grid_sample'}),
            'fullAccountAverage': None, 'engagementRate': None, 'rank': None,
        }, 'eligibleForMomentumFormula': False,
    }

media = [dict(m) for m in MEDIA]
for m in PILOT['verifiedMediaItems']:
    media.append({**m, 'verifiedText': True, 'scope': 'J.Crew Barn Jacket; not Factory or Madewell'})
for m in media:
    m.update({'publicationWindow': period(m['published']), 'estimatedAudience': None,
              'priorComparable': None, 'eligibleForMomentumFormula': False})
    m['classification'] = 'verified_public_source_text' if m['verifiedText'] else 'unverified_source_pointer_or_gap'

companies = list(dict.fromkeys(e['company'] for e in PROSPECTS['environments']))
reviews = []
for company in companies:
    accounts = [account(a) for a in SOCIAL if a['company'] == company]
    items = [m for m in media if m['company'] == company]
    independent = [m for m in items if m['verifiedText'] and ('Editorial' in m['category'] or 'editorial' in m['category'])]
    gaps = []
    if not independent:
        gaps.append('No independent editorial article verified in this discovery pass; this is not a claim of absent coverage.')
    if any(a['sampleSummary']['ownPostsWithVisibleLikes'] < a['sampleSummary']['ownAccountPosts'] for a in accounts):
        gaps.append('Some or all sampled main post counters are unavailable; missing fields remain null.')
    if any(a['sampleSummary']['relatedAccountPosts'] for a in accounts):
        gaps.append('Related/collaborator posts are separate context and excluded from own-account response summaries.')
    if any(a['sampleSummary']['primaryOwnAccountPosts'] < 3 for a in accounts):
        gaps.append('Fewer than three eligible own-account posts visible; campaign-pilot or recent supplements, where used, remain explicitly labelled.')
    gaps.append('No matched historical social captures or comparable current/reference media census; snapshot excluded from momentum formula.')
    compact = {
        'label': 'Public presence · snapshot', 'asOf': ASOF,
        'accounts': [{'handle': a['handle'], 'scope': a['scope'], 'followersDisplay': a['followersDisplay'],
                      'samplePosts': a['sampleSummary']['ownAccountPosts'],
                      'visibleLikePosts': a['sampleSummary']['ownPostsWithVisibleLikes'],
                      'sampleLikesRange': a['sampleSummary']['ownSampleLikesRangeDisplay'],
                      'primarySamplePosts': a['sampleSummary']['primaryOwnAccountPosts'],
                      'selectionExceptions': a['sampleSummary']['selectionExceptions']} for a in accounts],
        'mediaExample': next(({'publisher': m['publisher'], 'title': m['title'], 'published': m['published'],
                              'category': m['category'], 'url': m['url'], 'publicationWindow': m['publicationWindow']}
                             for m in items if m['verifiedText']), None),
        'mediaStatus': 'Verified source example(s)' if any(m['verifiedText'] for m in items) else 'No article verified in this pass',
        'detailsFile': str(ROOT / 'public-presence-review.md'),
        'footer': 'Selected public posts; accumulated counters, not reach or a full-account average',
        'eligibleForMomentumFormula': False,
    }
    reviews.append({'company': company, 'type': next(e['type'] for e in PROSPECTS['environments'] if e['company'] == company),
                    'accounts': accounts, 'mediaItems': items, 'gaps': gaps, 'customerSnapshot': compact,
                    'completeAccountOrMediaAudit': False, 'eligibleForMomentumFormula': False})

all_posts = [p for r in reviews for a in r['accounts'] for p in a['posts']]
counts = {'prospectsReviewed': len(reviews), 'matchedProfiles': len(SOCIAL), 'postsInspected': len(all_posts),
          'postObservationsWithVisibleLikes': sum(p['likesApproximate'] is not None for p in all_posts),
          'primaryDateEligibleGridPosts': sum(p['selection'] == 'date_eligible_visible_grid_sample' for p in all_posts),
          'supplementaryRecentPosts': sum(p['selection'] == 'supplement' for p in all_posts),
          'retainedCampaignPilotPosts': sum(p['selection'] == 'campaign_pilot' for p in all_posts),
          'relatedAccountPosts': sum(not p['includedInOwnAccountSummary'] for p in all_posts),
          'verifiedSourceTexts': sum(m['verifiedText'] for m in media),
          'prospectsWithVerifiedSourceText': sum(any(m['verifiedText'] for m in r['mediaItems']) for r in reviews),
          'mediaSourcePointersOrGaps': sum(not m['verifiedText'] for m in media),
          'newComparableIndices': 0}

out = {'title': 'Public social and media presence — all 25 prospects', 'asOf': ASOF, 'counts': counts,
       'method': {'socialSelectionDates': {'start': START, 'end': END},
           'selection': 'Up to three latest eligible posts exposed in each public profile grid; truncated/pinned grids are not an exhaustive chronological feed. J.Crew retains the earlier purposive campaign pilot; recent supplements used where no mature entries exposed.',
           'observationWindow': 'October 27, 2026, 06:21–06:26 UTC; minute precision',
           'mediaMethod': 'Focused source discovery plus direct page checks; prior verified J.Crew and Lilly articles reused. No fixed-panel census, search-total count, readership, sentiment, or historical growth measurement.',
           'ownership': 'Other-account post URLs stay related context. Exemplar banners remain separate; never sum followers or call them group reach.',
           'comparison': 'No cross-prospect ranking or follower-normalized interaction rate; different scopes, post ages, formats and missing counters.',
           'access': 'Public pages only; no owner Insights, subscription signup, login-gate bypass or CAPTCHA solving.',
           'futureComparableCollection': 'For event comparisons: same event-relative window, platform definitions and post ages for both editions. For media: fixed publisher/language/geography panel and windows, verified canonical stories, releases/affiliate content/syndication separated.'},
       'prospects': reviews, 'productionReady': False}

# Verify scope and known extraction pitfalls without inventing missing measurements.
assert len(reviews) == 25 and len(SOCIAL) == 27
assert Counter(r['type'] for r in reviews) == {'Brand': 18, 'Retailer': 7}
assert all(r['accounts'] and r['mediaItems'] for r in reviews)
assert all(p['likesApproximate'] is None for r in reviews if r['company'] == 'Amazon Fashion' for a in r['accounts'] for p in a['posts'])
assert all(not p['includedInOwnAccountSummary'] for p in all_posts if p['postOwnerHandle'] in ['poloralphlauren', 'nynarain', 'verawanggang', 'macysinc', 'rachelmirandablog'])
assert not any(a['handle'] == 'exemplarluxurygroup' for r in reviews for a in r['accounts'])
assert all(not p['eligibleForMomentumFormula'] for p in all_posts)
(ROOT / 'public-presence-review.json').write_text(json.dumps(out, indent=2, ensure_ascii=False) + '\n')

lines = ['# Public social and media review — all 25 prospects', '',
    f"**{counts['prospectsReviewed']} prospects · {counts['matchedProfiles']} matched public profiles · {counts['postsInspected']} inspected posts · {counts['verifiedSourceTexts']} verified source texts.** Instagram counters observed October 27, 2026, 06:21–06:26 UTC. Media source examples include older context and official releases; they are not total press coverage.", '',
    '**Index unchanged:** five provisional public indices, one separate team candidate, TOM FORD growth only and eleven brand gaps. No added social or press-volume score.', '',
    '## Snapshot by account', '',
    'Primary social selection: up to three visible grid posts dated September 20–October 19. Counts accumulated until October 27. Recent supplements and the retained J.Crew campaign pilot are separate exceptions. Followers are audience-size context, not reach. Likes ranges describe selected own-account posts only; no cross-brand ranking or full-account average.', '',
    '| Prospect / account | Followers displayed | Own posts / visible likes | Selected-post likes range | Selection exception |',
    '| --- | ---: | ---: | --- | --- |']
for r in reviews:
    for a in r['accounts']:
        s = a['sampleSummary']
        lines.append(f"| {r['company']} / [@{a['handle']}]({a['url']}) | {a['followersDisplay']} | {s['ownAccountPosts']} / {s['ownPostsWithVisibleLikes']} | {s['ownSampleLikesRangeDisplay']} | {', '.join(s['selectionExceptions']) or 'None'} |")
lines += ['', 'Related-account posts are excluded from the table’s response summaries: Polo Ralph Lauren, Nordstrom creator nynarain, Vera Wang, Macy’s Inc. and creator rachelmirandablog. Exemplar’s Neiman Marcus, Saks and Bergdorf accounts are kept separately. Gap Inc is corporate; VS is the brand; Calvin Klein spans lines beyond Collection.', '', '## Sources and gaps for each prospect', '']
for r in reviews:
    lines += [f"### {r['company']}", '']
    for a in r['accounts']:
        lines += [f"**[@{a['handle']}]({a['url']})** · {a['followersDisplay']} followers · observed {a['observedAt']} · {a['scope']}. Identity: {a['identityVerification']}.", '',
                  '| Post / owner | Published | Likes | Comments | Selection / scope |', '| --- | --- | ---: | ---: | --- |']
        for p in a['posts']:
            lines.append(f"| [{p['format']}]({p['url']}) / @{p['postOwnerHandle']} | {p['published']} | {p['likesDisplay'] or 'Unavailable'} | {p['commentsDisplay'] or 'Unavailable'} | {p['selection']} / {p['scope']} |")
        lines += ['']
    for m in r['mediaItems']:
        title = f"[{m['title']}]({m['url']})" if m['url'] else 'Source gap'
        lines += [f"- {title} · {m['publisher'] or 'No publisher verified'} · {m['published'] or 'Date unverified'} · **{m['category']}** · {m['publicationWindow']}. {m['access']}. {m['note']}"]
    lines += ['', '**Limits:** ' + ' '.join(r['gaps']), '']
lines += ['## Next evidence that would support a comparable score', '',
    'Owner or provider exports can add reach, views, saves, shares, clicks, follower history and paid/organic splits. Comparable momentum needs genuine historical captures at matched ages. A press-volume component needs identical publisher panels and event windows, canonical-story deduplication and separate release, shopping and syndication categories. Website/search interest and creator activity are further research layers; they have not been measured here.', '',
    f"[Machine-readable snapshot]({ROOT / 'public-presence-review.json'}) · [All packages and prompts]({ROOT / 'review.md'})", '']
(ROOT / 'public-presence-review.md').write_text('\n'.join(lines))
print(json.dumps(counts, indent=2))
