"""Build the compact 50/30/20 delivery and supporting page/evidence records."""
import json
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
inputs = json.loads((ROOT / 'weighted-delivery-inputs.json').read_text())
allen = json.loads((ROOT / 'prospect-inputs.json').read_text())
packages = json.loads((ROOT / 'prospect-packages.json').read_text())['packages']
enablement_input = json.loads((ROOT / 'arceo-enablement-inputs.json').read_text())
enablement_by_name = {r['company'].casefold(): r for r in enablement_input['records']}
environment_aliases = {k.casefold(): v.casefold() for k, v in enablement_input['matchRules']['environmentAliases'].items()}
prospect_enablement = {}
matched_source_companies = set()
for package in packages:
    company = package['company']
    matches = {}
    candidates = [(company, 'prospect-name', None)] + [
        (e['lightEnvironment'], 'allen-light-environment', e['lightEnvironment'])
        for e in allen['environments'] if e['company'] == company
    ]
    for candidate, basis, environment in candidates:
        key = environment_aliases.get(candidate.casefold(), candidate.casefold())
        source = enablement_by_name.get(key)
        if source is None:
            continue
        match = matches.setdefault(key, {
            'company': source['company'], 'companyCode': source['companyCode'],
            'emailDomains': source['emailDomains'], 'csvSourceRow': source['sourceRow'],
            'matchBasis': [], 'lightEnvironments': [],
        })
        if basis not in match['matchBasis']:
            match['matchBasis'].append(basis)
        if environment and environment not in match['lightEnvironments']:
            match['lightEnvironments'].append(environment)
        matched_source_companies.add(key)
    prospect_enablement[company] = list(matches.values())

csv_additions = [r for r in enablement_input['records'] if r['company'].casefold() not in matched_source_companies]
for source in csv_additions:
    packages.append({
        'company': source['company'], 'packageKey': 'arceo-' + source['companyCode'], 'type': None,
        'customerContent': {'invitation': None}, 'commercialContext': {'internalDataFields': []},
    })
    prospect_enablement[source['company']] = [{
        'company': source['company'], 'companyCode': source['companyCode'],
        'emailDomains': source['emailDomains'], 'csvSourceRow': source['sourceRow'],
        'matchBasis': ['csv-addition'], 'lightEnvironments': [],
    }]
assert len(matched_source_companies) == 27 and len(csv_additions) == 43

# User-requested report brands have no inferred Allen or enablement identity.
report_prospects = {r['company']: r for r in inputs.get('reportProspects', [])}
for company, source in report_prospects.items():
    assert company not in prospect_enablement, 'Report addition must not duplicate an existing identity'
    packages.append({
        'company': company, 'packageKey': source['packageKey'], 'type': source['type'],
        'customerContent': {'invitation': None}, 'commercialContext': {'internalDataFields': []},
    })
    prospect_enablement[company] = []

def dec(value):
    return Decimal(str(value))

def optional_dec(value):
    return None if value is None else dec(value)

def growth_value(current, reference, reported):
    if current is not None and reference is not None:
        return dec(current) / dec(reference) - 1 if dec(reference) > 0 else None
    return optional_dec(reported)

def period_start(source):
    return source.get('financialPeriodStart', source.get('sellingQuarterStart'))

def period_end(source):
    return source.get('financialPeriodEnd', source.get('sellingQuarterEnd'))

def cap(value):
    return min(Decimal(100), max(Decimal(0), value))

def num(value):
    return None if value is None else float(value)

def rounded(value, places=1):
    return value.quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP)

def sentiment(score):
    if score is None:
        return None
    return 'Good' if score >= 70 else 'Neutral' if score >= 40 else 'Needs improvement'

def momentum_sentiment(score):
    if score is None:
        return None
    return 'High' if score >= 75 else 'Medium' if score > 60 else 'Neutral' if score >= 40 else 'Low'

def social_sentiment(score):
    if score is None:
        return None
    return 'Positive' if score > 60 else 'Negative' if score < 40 else 'Neutral'

def strength_sentiment(change, latest_gap):
    if change is None or latest_gap is None:
        return None
    if change > 2:
        return 'Strong' if latest_gap >= 0 else 'Up and coming'
    return 'Fallback' if change < -2 else 'Neutral'

campaigns = []
for source in inputs.get('socialCampaigns', []):
    assert source['minimumPostsPerWindow'] >= 3
    baseline, event = source.get('baselineMedianLikes'), source.get('eventMedianLikes')
    eligible = (baseline is not None and event is not None and dec(baseline) > 0
                and source['baselinePostCount'] >= source['minimumPostsPerWindow']
                and source['eventPostCount'] >= source['minimumPostsPerWindow'])
    lift = (dec(event) / dec(baseline) - 1) * 100 if eligible else None
    campaigns.append({**source, 'eligible': eligible, 'derivedLiftPercent': num(lift),
                      'normalizedSocialScore': num(cap(50 + lift)) if lift is not None else None,
                      'signal': social_sentiment(cap(50 + lift)) if lift is not None else None,
                      'exclusionReason': None if eligible else 'Unavailable baseline or fewer than minimum posts per window'})

portfolio_social = []
for source in inputs.get('portfolioSocialInputs', []):
    baseline = source.get('baselineMedianMetricValue', source.get('baselineMedianLikes'))
    current = source.get('comparisonMedianMetricValue', source.get('comparisonMedianLikes'))
    valid = (source['includedInMainScore'] and baseline is not None and current is not None
             and dec(baseline) > 0 and source['baselineNumericPostCount'] > 0 and source['comparisonNumericPostCount'] > 0)
    lift = (dec(current) / dec(baseline) - 1) * 100 if valid else None
    portfolio_social.append({**source, 'derivedLiftPercent': num(lift),
                             'attentionSignal': social_sentiment(cap(50 + lift)) if lift is not None else None})

revenue_proxies = []
for source in inputs.get('revenueProxyInputs', []):
    combined, legacy = source.get('combinedProFormaRevenue'), source.get('legacyDicksRevenue')
    residual = dec(combined) - dec(legacy) if combined is not None and legacy is not None else None
    reported = source.get('reportedFootLockerRevenue')
    revenue_proxies.append({**source, 'derivedRevenue': num(residual),
                            'differenceFromReported': num(residual - dec(reported)) if residual is not None and reported is not None else None})
revenue_proxy_lookup = {r['proxyKey']: r for r in revenue_proxies}

cycles = []
cycle_lookup = {}
peers = []
for source in inputs['cycles']:
    cycle = dict(source)
    source_document = dict(inputs['sourceDocuments'][source['company']])
    source_document['fileName'] = source.get('sourceDocumentFileName', source_document['fileName'])
    peer_growth = [growth_value(p.get('revenueCurrent'), p.get('revenueReference'), p.get('reportedGrowth')) for p in source['peers']]
    proxy_key = source.get('brandRevenueCurrentProxyKey')
    own_current = revenue_proxy_lookup[proxy_key]['derivedRevenue'] if proxy_key else source.get('brandRevenueCurrent')
    own_growth = growth_value(own_current, source.get('brandRevenueReference'), None if proxy_key else source.get('reportedBrandGrowth'))
    benchmark_incomplete = source.get('financialBenchmarkStatus') == 'Incomplete'
    peer_median = median(peer_growth) if len(peer_growth) >= source.get('minimumPeerCount', 1) and all(g is not None for g in peer_growth) and not benchmark_incomplete else None
    gap = (own_growth - peer_median) * 100 if own_growth is not None and peer_median is not None else None
    baseline = source.get('baselineMedianMetricValue', source.get('baselineMedianLikes'))
    comparison = source.get('comparisonMedianMetricValue', source.get('showMedianLikes'))
    lift = (dec(comparison) / dec(baseline) - 1) * 100 if baseline is not None and comparison is not None and dec(baseline) > 0 else None
    annual_social_eligible = (source.get('socialMinimumValidPosts') is None or (
        min(source.get('baselinePostCount') or 0, source.get('showPostCount') or 0) >= source['socialMinimumValidPosts']
        and len(source.get('socialIncludedCalendarMonths', [])) >= source.get('socialMinimumCommonMonths', 0)))
    descriptive_lift = lift
    if not annual_social_eligible:
        lift = None
    campaign_children = [c for c in campaigns if c['cycleKey'] == source['cycleKey']]
    if source.get('socialAggregation') == 'median-eligible-campaign-lifts':
        assert all(c['company'] == source['company'] for c in campaign_children)
        eligible_lifts = [dec(c['derivedLiftPercent']) for c in campaign_children if c['eligible']]
        lift = median(eligible_lifts) if eligible_lifts else None
        cycle.update({'campaignKeys': [c['campaignKey'] for c in campaign_children],
                      'eligibleCampaignCount': len(eligible_lifts), 'excludedCampaignCount': len(campaign_children) - len(eligible_lifts)})
    if source.get('socialAggregation') in ['median-selected-brand-fiscal-lifts', 'median-selected-brand-matched-comment-lifts', 'median-selected-banner-retail-year-lifts']:
        social_children = [r for r in portfolio_social if r['cycleKey'] == source['cycleKey']]
        assert all(r['company'] == source['company'] for r in social_children)
        included = [r for r in social_children if r['includedInMainScore']]
        valid_lifts = [dec(r['derivedLiftPercent']) for r in included if r['derivedLiftPercent'] is not None]
        lift = median(valid_lifts) if included and len(valid_lifts) == len(included) else None
        cycle.update({'portfolioSocialKeys': [r['socialKey'] for r in social_children], 'includedPortfolioBrandCount': len(included)})
    ir_derived = cap(Decimal(50) + 5 * gap) if gap is not None else None
    social_derived = cap(Decimal(50) + lift) if lift is not None else None
    # The document reports components as well as rounded underlying growth inputs.
    # Keep its supplied component precision for this example, never backsolve growth.
    ir_used = None if benchmark_incomplete else optional_dec(source.get('reportedIrSubscore')) if source.get('reportedIrSubscore') is not None else ir_derived
    if proxy_key and (own_growth is None or peer_median is None):
        ir_used = None
    social_used = optional_dec(source.get('reportedSocialSubscore')) if source.get('reportedSocialSubscore') is not None else social_derived
    if not annual_social_eligible:
        social_used = None
    reported_trend = optional_dec(source.get('reportedStrengthSubscore'))
    previous = cycle_lookup.get(source['priorCycleKey'])
    assert previous is None or previous['company'] == source['company'], 'Strength must compare the same prospect'
    latest_gap = None if benchmark_incomplete else optional_dec(source['reportedRelativeMomentumPp']) if source['reportedRelativeMomentumPp'] is not None else gap
    if proxy_key and (own_growth is None or peer_median is None):
        latest_gap = None
    prior_gap = None if previous is None else optional_dec(previous['reportedRelativeMomentumPp']) if previous['reportedRelativeMomentumPp'] is not None else optional_dec(previous['derivedRelativeMomentumPp'])
    trend_change = latest_gap - prior_gap if latest_gap is not None and prior_gap is not None else None
    previous_derived = None if previous is None else optional_dec(previous['derivedRelativeMomentumPp'])
    derived_trend_change = gap - previous_derived if gap is not None and previous_derived is not None else None
    strength_label = strength_sentiment(trend_change, latest_gap)
    trend_used = None if strength_label is None else dec(inputs['trendScoreMapping'][strength_label])
    total = None if any(v is None for v in [ir_used, social_used, trend_used]) else sum(
        value * dec(inputs['weights'][key])
        for key, value in [('ir', ir_used), ('social', social_used), ('trend', trend_used)]
    )
    display = None if total is None else rounded(total, inputs['displayScoreDecimals'])
    cycle.update({
        **({'annualSocialEligible': annual_social_eligible, 'descriptiveSocialLiftPercent': num(descriptive_lift)} if source.get('socialMinimumValidPosts') is not None else {}),
        'derivedPeerMedianGrowth': num(peer_median), 'derivedRelativeMomentumPp': num(gap),
        'brandGrowthUsed': num(own_growth),
        'financialPeriodStart': period_start(source), 'financialPeriodEnd': period_end(source),
        'financialPeriodType': source.get('financialPeriodType', 'Quarter'),
        'financialPeriodLabel': source.get('financialPeriodLabel', 'Selling-quarter proxy'),
        'socialLiftPp': num(lift), 'derivedIrSubscore': num(ir_derived),
        'derivedSocialSubscore': num(social_derived), 'irSubscoreUsed': num(ir_used),
        'socialSubscoreUsed': num(social_used), 'trendSubscoreUsed': num(trend_used),
        'componentScoreBasis': source.get('componentScoreBasis', 'Reported Momentum/Social precision; Strength derived from agreed change-and-position rule. Original reported values retained separately.'),
        'trendChangePp': num(trend_change), 'derivedTrendChangePp': num(derived_trend_change), 'overallUnrounded': num(total),
        'overallDisplay': num(display), 'overallSentiment': sentiment(display),
        'momentumSentiment': momentum_sentiment(ir_used), 'socialSentiment': social_sentiment(social_used),
        'strengthSentiment': strength_label, 'derivedStrengthSubscore': num(trend_used),
        'strengthRuleScoreConsistent': None if reported_trend is None or trend_used is None else reported_trend == trend_used,
        'irPeerRank': 1 + sum(g > own_growth for g in peer_growth) if own_growth is not None and peer_median is not None else None,
        'irPeerCountIncludingBrand': 1 + len(peer_growth) if peer_median is not None else None,
        'baselineWindow': source.get('baselineWindow', '15 days before show'),
        'showWindow': source.get('showWindow', 'Show day through 7 days after'),
        'socialComparisonType': source.get('socialComparisonType', 'Show window versus 15-day baseline'),
        'metric': source.get('socialMetric', 'Median likes on selected collection-related posts'),
        'socialCaptureDate': source.get('socialCaptureDate'),
        'baselinePostCount': source.get('baselinePostCount'), 'showPostCount': source.get('showPostCount'),
        'postEvidenceUrls': source.get('postEvidenceUrls', []),
        'irEvidenceUrls': source.get('irEvidenceUrls', []), 'brandRevenueCurrent': own_current,
        'brandRevenueReference': source.get('brandRevenueReference'), 'currency': source.get('currency'),
        'revenueScope': source.get('revenueScope', f"Retail/DTC YoY growth reported in document; {source['company']}-wide quarter proxy"),
        'sourceDocument': source_document['fileName'],
        'evidenceStatus': 'User-supplied example; primary sources, populations and precision unverified',
        'productionReady': False,
    })
    cycles.append(cycle)
    cycle_lookup[cycle['cycleKey']] = cycle
    for p in source['peers']:
        peers.append({
            'cycleKey': source['cycleKey'], 'prospect': source['company'], 'peer': p['company'],
            'sellingQuarterStart': source['sellingQuarterStart'], 'sellingQuarterEnd': source['sellingQuarterEnd'],
            'financialPeriodStart': p.get('financialPeriodStart', period_start(source)),
            'financialPeriodEnd': p.get('financialPeriodEnd', period_end(source)),
            'financialPeriodType': p.get('financialPeriodType', cycle['financialPeriodType']),
            'financialPeriodLabel': p.get('financialPeriodLabel', cycle['financialPeriodLabel']),
            'reportedGrowth': p['reportedGrowth'],
            'growthUsed': num(growth_value(p.get('revenueCurrent'), p.get('revenueReference'), p.get('reportedGrowth'))),
            'revenueCurrent': p.get('revenueCurrent'), 'revenueReference': p.get('revenueReference'),
            'currency': p.get('currency'), 'revenueUnit': p.get('revenueUnit'),
            'revenueScope': p.get('revenueScope', 'Retail/DTC growth reported in supplied document'),
            'benchmarkRelationship': p.get('benchmarkRelationship'),
            'sourceDocument': source_document['fileName'],
            'sourceUrl': (p.get('sourceUrls') or [None])[0], 'sourceUrls': p.get('sourceUrls', []),
            'sourceReferences': p.get('sourceReferences', []),
            'evidenceStatus': 'Primary IR source, period and scope verification pending',
        })

selected_cycles = {company: cycle_lookup[key] for company, key in inputs['selectedCycles'].items()}
assert all(cycle['company'] == company for company, cycle in selected_cycles.items())

def insight_kpi(component, example):
    """Resolve the highlighted observation without changing scoring inputs."""
    spec = component.get('kpi')
    if not spec or not example:
        return None
    source = cycle_lookup[spec.get('sourceCycleKey', example['cycleKey'])]
    basis = spec['basis']
    if basis == 'relative-momentum':
        value = source['reportedRelativeMomentumPp']
        if value is None:
            value = source['derivedRelativeMomentumPp']
    elif basis == 'social-lift':
        value = num(dec(source['socialLiftPp']) / 100) if source['socialLiftPp'] is not None else None
    elif basis == 'own-growth':
        value = source['reportedBrandGrowth']
        if value is None:
            value = source['brandGrowthUsed']
    elif basis == 'own-growth-rate-change':
        value = num((dec(spec['currentGrowth']) - dec(spec['referenceGrowth'])) * 100)
    else:
        assert basis in ['reported-comparable-sales', 'reported-operating-change-bound', 'historical-decline-bound', 'coverage-likes', 'coverage-post-count']
        value = spec['reportedValue']
    if value is None:
        return None
    return {
        **spec, 'value': value, 'sourceCycleKey': source['cycleKey'],
        'sourceDocument': source['sourceDocument'],
        'period': spec.get('period', source['showWindow'] if basis in ['social-lift', 'coverage-likes', 'coverage-post-count'] else source['financialPeriodLabel']),
        'comparison': spec.get('comparison', source['baselineWindow'] if basis == 'social-lift' else 'No matched baseline' if basis.startswith('coverage-') else 'Named peer-growth benchmark' if basis == 'relative-momentum' else 'Prior-year equivalent period'),
    }

latest = selected_cycles['Burberry']
records = []
for package in packages:
    example = selected_cycles.get(package['company'])
    content = inputs['prospectContent'].get(package['company'], {})
    component_insights = content.get('componentInsights', {})
    presentation = content.get('presentation')
    section_labels = {key: section['title'] for section in presentation['sections']
                      for key in section['componentKeys']} if presentation else {}
    retailer = package['type'] == 'Retailer'
    retailer_annual = example and example.get('scoreProfile') in ['retailer-annual', 'retailer-parent-hybrid']
    parent_hybrid = example and example.get('scoreProfile') in ['parent-segment-hybrid', 'retailer-parent-hybrid', 'parent-group-hybrid']
    hybrid_scope = {key: example.get(key) for key in ['proxyFinancialEntity',
                    'standaloneBrandFinancialSeriesAvailable', 'standaloneBrandOverallScore']} if parent_hybrid else {}
    historical_financial = cycle_lookup.get(example.get('historicalFinancialContextCycleKey')) if example else None
    historical_context = {'cycleKey': historical_financial['cycleKey'],
        'financialPeriodStart': historical_financial['financialPeriodStart'], 'financialPeriodEnd': historical_financial['financialPeriodEnd'],
        'score': historical_financial['irSubscoreUsed'], 'displayScore': num(rounded(dec(historical_financial['irSubscoreUsed']))),
        'sentiment': historical_financial['momentumSentiment'], 'peerRank': historical_financial['irPeerRank'],
        'peerCountIncludingBrand': historical_financial['irPeerCountIncludingBrand'],
        'usedForCurrentOverall': False, 'scope': 'Earlier verified financial year; separate from current social-only result'} if historical_financial else None
    rows = [e for e in allen['environments'] if e['company'] == package['company']]
    new_company = not rows
    report_addition = report_prospects.get(package['company'])
    enablement = prospect_enablement[package['company']]
    core_insight = content.get('coreInsight') if example else None
    records.append({
        'prospectId': package['packageKey'], 'prospectName': package['company'],
        'lightEnvironments': [e['lightEnvironment'] for e in rows],
        'audienceType': package['type'], 'domain': inputs['allenWorkbookReview']['domains'].get(package['company']),
        'emailDomains': list(dict.fromkeys(d for m in enablement for d in m['emailDomains'])),
        'companyCodes': [m['companyCode'] for m in enablement], 'enablementCompanies': enablement,
        'identitySource': report_addition['identitySource'] if report_addition else enablement_input['source']['fileName'] if new_company else allen['source']['fileName'],
        'deliveryScope': 'Report addition · environment/domain/CTA pending' if report_addition else 'CSV addition · scope/environment pending' if new_company else 'Allen final prospect',
        **({'parentCompany': report_addition['parentCompany'], 'classificationBasis': report_addition['classificationBasis']}
           if report_addition else {}),
        'allenSourceRows': [e['sourceRow'] for e in rows],
        'methodVersion': inputs['methodVersion'],
        **({'presentation': presentation} if presentation else {}),
        'selectedCycleKey': example['cycleKey'] if example else None,
        'page1': {
            'title': presentation['overallTitle'] if presentation else 'Fashion momentum index',
            'collectionLabel': example['collection'] if example else None,
            'showDate': example['showDate'] if example else None,
            'sellingQuarterStart': example['sellingQuarterStart'] if example else None,
            'sellingQuarterEnd': example['sellingQuarterEnd'] if example else None,
            'financialPeriodStart': example['financialPeriodStart'] if example else None,
            'financialPeriodEnd': example['financialPeriodEnd'] if example else None,
            'financialPeriodType': example['financialPeriodType'] if example else None,
            'financialPeriodLabel': example['financialPeriodLabel'] if example else None,
            'measurementSubject': example.get('measurementSubject', example['company']) if example else None,
            'scopeLabel': example.get('scopeLabel') if example else None,
            **({'overallScoreScope': 'Parent-context hybrid', **hybrid_scope} if parent_hybrid else {}),
            **({'overallScoreScope': 'WWD-labelled annual proxy; source scope and disclosure unverified'} if example and example.get('scoreProfile') == 'brand-annual-wwd-proxy' else {}),
            'overallScore': example['overallDisplay'] if example else None,
            'overallUnrounded': example['overallUnrounded'] if example else None,
            'sentiment': example['overallSentiment'] if example else None,
            'status': content.get('deliveryStatus', 'Group example · provisional; identity/environment pending' if new_company else 'Document example · provisional') if example else 'Scope/environment and scoring inputs pending' if new_company else 'Shared brand board · no retailer score' if retailer else 'Missing weighted-method inputs',
            'coreInsight': core_insight,
            **({key: content[key] for key in ['coreInsightSourceCycleKey', 'coreInsightStatus']} if content.get('coreInsightSourceCycleKey') else {}),
            'weightsLabel': ' · '.join(f"{label} {(dec(inputs['weights'][key]) * 100).normalize():f}%"
                                      for key, label in [('ir', 'Momentum'), ('social', 'Social'), ('trend', 'Strength')]),
            **({'reportedFinancialOnlyScore': example['reportedFinancialOnlyScore'],
                'reportedFinancialOnlySentiment': example.get('reportedFinancialOnlySentiment'),
                'financialOnlyBasis': example.get('financialOnlyBasis')}
               if example and example.get('reportedFinancialOnlyScore') is not None else {}),
        },
        'page2': {
            'momentum': {'label': section_labels.get('momentum', 'Momentum score'), 'sourceMetric': 'IR performance vs. peers', 'weight': inputs['weights']['ir'],
                'score': example['irSubscoreUsed'] if example else None,
                'displayScore': num(rounded(dec(example['irSubscoreUsed']))) if example and example['irSubscoreUsed'] is not None else None,
                'sentiment': example['momentumSentiment'] if example else None,
                'brandGrowth': example['reportedBrandGrowth'] if example else None,
                'brandGrowthUsed': example['brandGrowthUsed'] if example else None,
                'peerMedianGrowth': example['derivedPeerMedianGrowth'] if example else None,
                'relativeMomentumPp': example['reportedRelativeMomentumPp'] if example else None,
                'derivedRelativeMomentumPp': example['derivedRelativeMomentumPp'] if example else None,
                'measurementSubject': example.get('measurementSubject', example['company']) if example else None,
                'revenueScope': example['revenueScope'] if example else None,
                'growthBasis': example.get('growthBasis') if example else None,
                'peerNames': [p['company'] for p in example['peers']] if example else [],
                'peerRank': example['irPeerRank'] if example else None,
                'peerCountIncludingBrand': example['irPeerCountIncludingBrand'] if example else None,
                'explanation': content.get('momentumExplanation') if example else None,
                'cardDescriptor': component_insights.get('momentum', {}).get('descriptor'),
                'cardInsight': component_insights.get('momentum', {}).get('insight'),
                'cardKpi': insight_kpi(component_insights.get('momentum', {}), example),
                **({'financialScoreScope': 'Parent-unit peer comparison', **hybrid_scope} if parent_hybrid else {}),
                **({'historicalFinancialContext': historical_context} if historical_context else {}),
                **({key: example.get(key) for key in ['financialBenchmarkStatus', 'minimumPeerCount',
                    'financialBenchmarkGaps', 'rejectedFinancialProxies']}
                   if example and example.get('financialBenchmarkStatus') else {})},
            'social': {'label': section_labels.get('social', 'Social score'), 'sourceMetric': 'Social signal vs. the brand’s baseline', 'weight': inputs['weights']['social'],
                'score': example['socialSubscoreUsed'] if example else None,
                'displayScore': num(rounded(dec(example['socialSubscoreUsed']))) if example and example['socialSubscoreUsed'] is not None else None,
                'sentiment': example['socialSentiment'] if example else None,
                'baselineMedianLikes': example['baselineMedianLikes'] if example else None,
                'showMedianLikes': example['showMedianLikes'] if example else None,
                'socialLiftPp': example['socialLiftPp'] if example else None,
                'baselineWindow': example['baselineWindow'] if example else None,
                'showWindow': example['showWindow'] if example else None,
                'comparisonType': example['socialComparisonType'] if example else None,
                'metric': example['metric'] if example else None,
                **({key: example.get(key) for key in ['baselineMedianMetricValue', 'comparisonMedianMetricValue', 'socialMetricType']}
                   if example and 'baselineMedianMetricValue' in example else {}),
                'captureDate': example['socialCaptureDate'] if example else None,
                'baselinePostCount': example['baselinePostCount'] if example else None,
                'showPostCount': example['showPostCount'] if example else None,
                'baselineWindowStart': example.get('baselineWindowStart') if example else None,
                'baselineWindowEnd': example.get('baselineWindowEnd') if example else None,
                'showWindowStart': example.get('showWindowStart') if example else None,
                'showWindowEnd': example.get('showWindowEnd') if example else None,
                'account': example.get('socialAccount') if example else None,
                'timezone': example.get('socialTimezone') if example else None,
                'archiveReference': example.get('socialArchiveReference') if example else None,
                'selectionRule': example.get('socialSelectionRule') if example else None,
                'explanation': content.get('socialExplanation') if example else None,
                'cardDescriptor': component_insights.get('social', {}).get('descriptor'),
                'cardInsight': component_insights.get('social', {}).get('insight'),
                'cardKpi': insight_kpi(component_insights.get('social', {}), example),
                **({'aggregation': example['socialAggregation'], 'campaignKeys': example['campaignKeys'],
                    'eligibleCampaignCount': example['eligibleCampaignCount'], 'excludedCampaignCount': example['excludedCampaignCount'],
                    'archiveRetentionDate': example.get('socialArchiveRetentionDate')}
                   if example and example.get('socialAggregation') == 'median-eligible-campaign-lifts' else {}),
                **({'aggregation': example['socialAggregation'], 'portfolioSocialKeys': example['portfolioSocialKeys'],
                    'includedPortfolioBrandCount': example['includedPortfolioBrandCount']}
                   if example and example.get('socialAggregation') in ['median-selected-brand-fiscal-lifts', 'median-selected-brand-matched-comment-lifts', 'median-selected-banner-retail-year-lifts'] else {}),
                **({key: example[key] for key in ['socialIncludedCalendarMonths', 'socialExcludedCalendarMonths']}
                   if example and 'socialIncludedCalendarMonths' in example else {}),
                **({key: example.get(key) for key in ['socialPlatform', 'socialSampleNotes', 'socialObservedCoverage',
                    'socialAggregates', 'alternativeSocialWindow', 'outOfWindowSocialSample', 'socialCaptureTimestamp',
                    'socialCaptureTimezone', 'socialRetrievalDate']}
                   if example and example.get('socialSampleNotes') else {})},
            'strength': {'label': 'Momentum strength' if presentation else 'Strength score', 'sourceMetric': 'Trend across comparable seasons', 'weight': inputs['weights']['trend'],
                'score': example['trendSubscoreUsed'] if example else None,
                'displayScore': num(rounded(dec(example['trendSubscoreUsed']))) if example and example['trendSubscoreUsed'] is not None else None,
                'sentiment': example['strengthSentiment'] if example else None,
                'category': example['strengthSentiment'] if example else None,
                'reportedCategory': example['reportedStrengthCategory'] if example else None,
                'reportedScore': example.get('reportedStrengthSubscore') if example else None,
                'categoryBasis': 'Agreed four-category rule based on change and latest peer-relative position; reported category and score retained separately',
                'ruleScoreConsistent': example['strengthRuleScoreConsistent'] if example else None,
                'priorCycleKey': example['priorCycleKey'] if example else None,
                'comparisonType': example['trendComparison'] if example else None,
                'changePp': example['trendChangePp'] if example else None,
                'reportedChangePp': example.get('reportedStrengthChangePp') if example else None,
                **({'reportedChangeBasis': 'Source company-only annual growth acceleration; separate from agreed peer-gap change'} if example and example.get('scoreProfile') == 'brand-annual-wwd-proxy' else {}),
                'latestPeerGapPp': example['reportedRelativeMomentumPp'] if example else None,
                'explanation': content.get('strengthExplanation') if example else None,
                'cardDescriptor': component_insights.get('strength', {}).get('descriptor'),
                'cardInsight': component_insights.get('strength', {}).get('insight'),
                'cardKpi': insight_kpi(component_insights.get('strength', {}), example),
                **({'cardDescriptorOverride': component_insights['strength']['manualOverride']}
                   if component_insights.get('strength', {}).get('manualOverride') else {}),
                **({'financialScoreScope': 'Parent-unit peer-relative trend', **hybrid_scope} if parent_hybrid else {})},
        },
        'page3': {
            'leaderboardId': content.get('leaderboardId', None if retailer_annual else 'weighted-brand-board-v1-draft'), 'rank': None, 'rankedCount': 0,
            'state': content.get('leaderboardState', 'Retailer annual proxy · no approved comparable cohort' if retailer_annual else 'Content scope and board eligibility pending' if new_company else 'Leaderboard pending comparable weighted scores'),
            'highlightProspectId': package['packageKey'] if package['type'] == 'Brand' and content.get('leaderboardId', True) is not None else None,
            'scope': content.get('leaderboardScope', 'Separately scoped retailer annual comparison; excluded from shared brand board' if retailer_annual else 'Same-method brands with matched cycles, financial scopes and approved evidence'),
            'note': 'IR peer rank is a component comparison; it is not an overall leaderboard rank.',
        },
        'page4': {
            'invitation': package['customerContent']['invitation'], 'ctaLabel': 'Unlock November signal',
            'ctaDestination': None, 'confirmationCopy': None, 'analyticsEvent': None,
            'internalDataFields': package['commercialContext']['internalDataFields'],
            'copyStatus': 'Proposed invitation retained from existing package; next step pending',
        },
        'evidence': {
            'sourceDocument': example['sourceDocument'] if example else None,
            'irSourceUrls': example['irEvidenceUrls'] if example else [],
            'socialSourceUrls': example['postEvidenceUrls'] if example else [],
            'sellingWindowSourceUrls': example.get('sellingWindowEvidenceUrls', []) if example else [],
            'sourceReferences': example.get('sourceReferences', []) if example else [],
            'scopeLabel': example.get('scopeLabel') if example else None,
            **({'overallScoreScope': 'Parent-context hybrid', **hybrid_scope,
                'standaloneBrandCommercialContext': example.get('standaloneBrandCommercialContext')}
               if parent_hybrid else {}),
            'evidenceAsOf': '2026-10-28' if example and example.get('scoreProfile') == 'brand-annual-wwd-proxy' else None,
            'componentScoreBasis': example['componentScoreBasis'] if example else None,
            **({'scoreProfile': example['scoreProfile'], 'reportedOverallSentiment': example.get('reportedOverallSentiment')}
               if example and example.get('scoreProfile') else {}),
            'reviewStatus': 'Primary evidence and method review pending' if example else 'CSV identity supplied; content scope, environment and scoring inputs pending' if new_company else 'Inputs pending',
            'productionReady': False, 'leaderboardEligible': False,
            'gaps': content['evidenceGaps'] if example else (([
                'Confirm company/brand/retailer content scope and live Light environment; CSV company/code is not an Allen environment mapping',
            ] if new_company else []) + [
                'Choose collection/show or comparable campaign and selling-quarter scope',
                'Collect own and agreed peer same-quarter YoY retail/DTC measurements',
                'Collect matched pre-show/show median likes with post evidence and capture timing',
                'Obtain earlier same-season peer-relative momentum and reviewed trend category',
                'Confirm final CTA destination',
            ] if not retailer else [
                'Retailer-specific scoring method not supplied; retain shared brand board',
                'Validate underlying weighted brand cohort before displaying ranks',
                'Confirm final CTA destination',
            ]),
        },
    })

assert len(records) == 74 and sum(len(r['lightEnvironments']) for r in records) == 26
assert len({r['prospectId'] for r in records}) == len({r['prospectName'].casefold() for r in records}) == 74
assert all(r['domain'] is None for r in records)
assert all(r['emailDomains'] and r['companyCodes'] for r in records if r['prospectName'] not in report_prospects)
assert sum(r['audienceType'] is None for r in records) == 46
assert sum(r['page1']['overallScore'] is not None for r in records) == 25 + sum(c['overallDisplay'] is not None for c in selected_cycles.values() if c.get('scoreProfile') == 'brand-annual-wwd-proxy') and len(selected_cycles) == 38
assert latest['overallDisplay'] == 61.2 and latest['overallSentiment'] == 'Neutral'
assert cycle_lookup['burberry-winter-2025']['overallDisplay'] == 32.6
assert cycle_lookup['burberry-summer-2025']['overallDisplay'] is None
assert selected_cycles['Ralph Lauren']['overallDisplay'] == 67.9
assert cycle_lookup['ralph-lauren-fall-2025']['overallDisplay'] == 67.1
assert cycle_lookup['ralph-lauren-spring-2025']['overallDisplay'] is None
assert selected_cycles['TOM FORD']['overallDisplay'] == 64.8
assert cycle_lookup['tom-ford-spring-summer-2026']['overallDisplay'] == 59.8
assert cycle_lookup['tom-ford-autumn-winter-2025']['overallDisplay'] is None
assert all(not r['evidence']['leaderboardEligible'] for r in records)
assert all(r['page1']['overallScore'] is None for r in records if r['audienceType'] == 'Retailer' and r['evidence'].get('scoreProfile') not in ['retailer-annual', 'retailer-parent-hybrid'])
assert all(r['page3']['leaderboardId'] is None for r in records if r['evidence'].get('scoreProfile') in ['retailer-annual', 'retailer-parent-hybrid', 'parent-segment-hybrid', 'parent-group-hybrid'])

delivery_rows = [{
    'prospect': r['prospectName'], 'coreInsight': r['page1']['coreInsight'],
    'overallScore': r['page1']['overallScore'], 'overallSentiment': r['page1']['sentiment'],
    'momentumScore': r['page2']['momentum']['displayScore'], 'momentumSentiment': r['page2']['momentum']['sentiment'],
    'socialScore': r['page2']['social']['displayScore'], 'socialSentiment': r['page2']['social']['sentiment'],
    'strengthScore': r['page2']['strength']['displayScore'], 'strengthSentiment': r['page2']['strength']['sentiment'],
    'emailDomains': r['emailDomains'], 'companyCodes': r['companyCodes'],
    **{f'{key}{suffix}': r['page2'][key][field]
       for key in ['momentum', 'social', 'strength']
       for suffix, field in [('Descriptor', 'cardDescriptor'), ('Insight', 'cardInsight')]},
    **{f'{key}Kpi{suffix}': (r['page2'][key]['cardKpi'] or {}).get(field)
       for key in ['momentum', 'social', 'strength']
       for suffix, field in [('Value', 'value'), ('Label', 'label')]},
} for r in records]
normalization = inputs['overallDisplayNormalization']
available_indices = [dec(r['overallScore']) for r in delivery_rows if r['overallScore'] is not None]
observed_min = min(available_indices) if available_indices else None
observed_max = max(available_indices) if available_indices else None
display_lower, display_upper = dec(normalization['lowerBound']), dec(normalization['upperBound'])
assert display_lower < display_upper
def normalize_overall(score):
    if score is None:
        return None
    if observed_min == observed_max:
        return num(rounded((display_lower + display_upper) / 2, normalization['decimals']))
    return num(rounded(display_lower + (dec(score) - observed_min) *
                       (display_upper - display_lower) / (observed_max - observed_min),
                       normalization['decimals']))

for r, record in zip(delivery_rows, records):
    r['normalizedFashionMomentumIndex'] = normalize_overall(r['overallScore'])
    record['page1']['normalizedFashionMomentumIndex'] = r['normalizedFashionMomentumIndex']
normalization_review = {
    **normalization, 'observedMinimum': num(observed_min), 'observedMaximum': num(observed_max),
    'availableIndexCount': len(available_indices),
    'formula': 'lowerBound + (originalIndex - observedMinimum) / (observedMaximum - observedMinimum) * (upperBound - lowerBound)',
    'missingScoreHandling': 'Unavailable original indices remain unavailable; no imputation',
    'equalScoreHandling': 'If all numeric indices are identical, use the midpoint of the display bounds',
    'sentimentHandling': 'Original score categories and sentiments remain unchanged; no category is derived from the display index',
}
enablement_rows = []
for source in enablement_input['records']:
    linked = [r for r in records if source['companyCode'] in r['companyCodes']]
    environments = list(dict.fromkeys(e for r in linked for m in r['enablementCompanies']
                                     if m['companyCode'] == source['companyCode'] for e in m['lightEnvironments']))
    enablement_rows.append({
        **source, 'linkedProspectIds': [r['prospectId'] for r in linked],
        'linkedProspects': [r['prospectName'] for r in linked], 'lightEnvironments': environments,
        'status': 'Allen mapping retained; configuration pending' if environments else 'Environment/content scope pending',
    })
assert len(enablement_rows) == 70 and all(len(r['linkedProspects']) == 1 for r in enablement_rows)
by_name = {r['prospectName']: r for r in records}
assert by_name['Coach']['companyCodes'] == ['tapestry']
assert by_name['DKNY']['companyCodes'] == ['giiiapparelgroup']
assert by_name['Calvin Klein']['companyCodes'] == ['pvh']
assert by_name['Fendi']['companyCodes'] == ['fendi', 'lvmh']
assert by_name['Marc Jacobs']['companyCodes'] == ['marcjacobs', 'whpglobal']
assert by_name['TOM FORD']['emailDomains'] == ['tomfordfashion.com', 'tomfordinternational.com']
assert by_name['Estée Lauder']['audienceType'] is None and by_name['Estée Lauder']['lightEnvironments'] == []
assert delivery_rows[0]['momentumScore'] == 34.5
assert delivery_rows[0]['momentumSentiment'] == 'Low'
assert delivery_rows[0]['socialSentiment'] == 'Positive' and delivery_rows[0]['strengthSentiment'] == 'Up and coming'
assert latest['strengthRuleScoreConsistent'] is True and latest['trendSubscoreUsed'] == 70
ralph = next(r for r in delivery_rows if r['prospect'] == 'Ralph Lauren')
assert [ralph[k] for k in ['overallScore', 'overallSentiment', 'momentumScore', 'momentumSentiment', 'socialScore', 'socialSentiment', 'strengthScore', 'strengthSentiment']] == [67.9, 'Neutral', 100, 'High', 39.7, 'Negative', 30, 'Fallback']
assert selected_cycles['Ralph Lauren']['trendChangePp'] == -11.51
assert selected_cycles['Ralph Lauren']['socialSubscoreUsed'] == 39.74
tom_ford = next(r for r in delivery_rows if r['prospect'] == 'TOM FORD')
assert [tom_ford[k] for k in ['overallScore', 'overallSentiment', 'momentumScore', 'momentumSentiment', 'socialScore', 'socialSentiment', 'strengthScore', 'strengthSentiment']] == [64.8, 'Neutral', 57.5, 'Neutral', 100, 'Positive', 30, 'Fallback']
assert selected_cycles['TOM FORD']['trendChangePp'] == -6.5
assert selected_cycles['TOM FORD']['irPeerRank'] == 2
assert selected_cycles['TOM FORD']['strengthRuleScoreConsistent'] is True
assert selected_cycles['TOM FORD']['baselinePostCount'] == 5 and selected_cycles['TOM FORD']['showPostCount'] == 4
assert len(cycles) == 102 and len(peers) == 174
assert len({s['fileName'] for s in inputs['sourceDocuments'].values()}) == 37
vf = selected_cycles['VF Corporation']; footlocker = selected_cycles['Foot Locker']
assert vf['overallDisplay'] == 38.4 and vf['overallSentiment'] == 'Needs improvement'
assert vf['irSubscoreUsed'] == 28.7482 and round(vf['socialSubscoreUsed'], 4) == 33.5085
assert vf['trendSubscoreUsed'] == 70 and vf['strengthSentiment'] == 'Up and coming' and vf['trendChangePp'] == 6.33
assert vf['baselineMedianLikes'] is None and vf['showMedianLikes'] is None
assert len(portfolio_social) == 8 and len(revenue_proxies) == 2
assert footlocker['overallDisplay'] == 36.0 and footlocker['irSubscoreUsed'] == 0 and footlocker['socialSubscoreUsed'] == 100
assert footlocker['trendSubscoreUsed'] == 30 and footlocker['strengthSentiment'] == 'Fallback'
assert footlocker['brandRevenueCurrent'] == 7.677559 and footlocker['brandRevenueReference'] == 7.988
assert revenue_proxy_lookup['footlocker-proforma-fy2024']['derivedRevenue'] == 7.988334
assert revenue_proxy_lookup['footlocker-proforma-fy2024']['usedForScoredRevenue'] is False
assert by_name['Foot Locker']['emailDomains'] == ['footlocker.com'] and by_name['Foot Locker']['companyCodes'] == ['footlocker']
assert by_name['Foot Locker']['audienceType'] is None and by_name['Foot Locker']['lightEnvironments'] == []
assert by_name['VF Corporation']['audienceType'] is None and by_name['VF Corporation']['emailDomains'] == by_name['VF Corporation']['companyCodes'] == by_name['VF Corporation']['lightEnvironments'] == []
assert by_name['VF Corporation']['page4']['invitation'] is None
ck = selected_cycles['Calvin Klein']
tommy = selected_cycles['Tommy Hilfiger']
assert ck['overallDisplay'] == 38.5 and ck['overallSentiment'] == 'Needs improvement'
assert ck['irSubscoreUsed'] == 5.075 and ck['socialSubscoreUsed'] == 100 and ck['trendSubscoreUsed'] == 30
assert ck['trendChangePp'] == -9.92 and ck['reportedStrengthChangePp'] == -9.93
assert tommy['overallDisplay'] == 54.7 and tommy['overallSentiment'] == 'Neutral'
assert tommy['irSubscoreUsed'] == 37.325 and tommy['socialSubscoreUsed'] == 100 and tommy['trendSubscoreUsed'] == 30
assert tommy['trendChangePp'] == -2.03 and tommy['strengthSentiment'] == 'Fallback'
assert by_name['Tommy Hilfiger']['lightEnvironments'] == by_name['Tommy Hilfiger']['emailDomains'] == by_name['Tommy Hilfiger']['companyCodes'] == []
assert by_name['Tommy Hilfiger']['page4']['invitation'] is None and by_name['Tommy Hilfiger']['parentCompany'] == 'PVH'
assert by_name['Calvin Klein']['lightEnvironments'] == ['PVH'] and by_name['Calvin Klein']['emailDomains'] == ['pvh.com']
assert inputs['sourceContext']['pvhCoreBrandPortfolio']['usedForDeliveryScores'] is False
assert cycle_lookup['calvin-klein-collection-fall-2025']['overallDisplay'] == 52.0
assert cycle_lookup['tommy-hilfiger-spring-summer-2025']['overallDisplay'] is None
for key in ['calvin-klein-collection-fall-2026', 'calvin-klein-collection-spring-2027', 'tommy-hilfiger-spring-2027-runway']:
    assert cycle_lookup[key]['overallDisplay'] is None and cycle_lookup[key]['irSubscoreUsed'] is None
    assert cycle_lookup[key]['financialPeriodStart'] is None and cycle_lookup[key]['financialPeriodEnd'] is None
pacsun = cycle_lookup['pacsun-calendar-ytd-2026']  # Preserved prior report regression.
assert pacsun['socialSubscoreUsed'] == 42.2 and pacsun['socialSentiment'] == 'Neutral'
assert pacsun['irSubscoreUsed'] is None and pacsun['trendSubscoreUsed'] is None and pacsun['overallDisplay'] is None
assert pacsun['irPeerRank'] is None and pacsun['financialPeriodStart'] is None and pacsun['financialPeriodEnd'] is None
assert pacsun['baselinePostCount'] == 179 and pacsun['showPostCount'] == 61
assert pacsun['socialAggregates']['baselineAllPostCount'] == 265 and pacsun['socialAggregates']['comparisonAllPostCount'] == 104
assert by_name['PacSun']['audienceType'] == 'Brand' and by_name['PacSun']['lightEnvironments'] == ['PacSun']
assert by_name['PacSun']['emailDomains'] == ['pacsun.com', 'pacificsunwear.com']
assert by_name['PacSun']['page3']['leaderboardId'] is None
for company, score in [('Amazon Fashion', 0)]:
    c = selected_cycles[company]
    assert c['socialSubscoreUsed'] == score and c['socialSentiment'] == 'Negative'
    assert c['irSubscoreUsed'] is None and c['trendSubscoreUsed'] is None and c['overallDisplay'] is None
    assert c['derivedPeerMedianGrowth'] is None and c['irPeerRank'] is None
assert by_name['Amazon Fashion']['audienceType'] == 'Retailer'
assert by_name['Ulta Beauty']['audienceType'] is None and by_name['Ulta Beauty']['lightEnvironments'] == []
assert selected_cycles['Lilly Pulitzer']['overallDisplay'] == 42.9
assert selected_cycles["Kohl's"]['overallDisplay'] == 48.9 and selected_cycles["Kohl's"]['overallSentiment'] == 'Neutral'
assert selected_cycles['Target']['overallDisplay'] is None and selected_cycles['Target']['socialSubscoreUsed'] is None
assert selected_cycles['Target']['reportedFinancialOnlyScore'] == 37.5
assert by_name["Kohl's"]['audienceType'] == 'Retailer' and by_name['Target']['audienceType'] is None
assert by_name['Target']['lightEnvironments'] == []
gap = selected_cycles['GAP Inc']
assert gap['overallDisplay'] == 60.5 and gap['overallUnrounded'] == 60.48735
assert gap['trendSubscoreUsed'] == 70 and gap['strengthSentiment'] == 'Up and coming'
assert gap['eligibleCampaignCount'] == 3 and gap['excludedCampaignCount'] == 1
assert abs(gap['socialLiftPp'] - 409.84555984555985) < 1e-9
assert gap['baselineMedianLikes'] is None and gap['showMedianLikes'] is None
assert gap['irPeerRank'] == 3 and gap['irPeerCountIncludingBrand'] == 3
assert rounded(dec(gap['derivedTrendChangePp']), 2) == dec(3.72)
assert campaigns[-1]['eligible'] is False and campaigns[-1]['derivedLiftPercent'] is None
assert cycle_lookup['gap-inc-fy2024']['overallDisplay'] is None
expected_new = {
    'Moncler': [49.8, 'Neutral', 27.5, 'Low', 100, 'Positive', 30, 'Fallback'],
    'Coach': [70.2, 'Good', 100, 'High', 13.9, 'Negative', 80, 'Strong'],
    'Estée Lauder': [81.3, 'Good', 75.7, 'High', 91.7, 'Positive', 80, 'Strong'],
    "Victoria's Secret & Co.": [61.1, 'Neutral', 50.2, 'Neutral', 100, 'Positive', 30, 'Fallback'],
}
for company, expected in expected_new.items():
    row = next(r for r in delivery_rows if r['prospect'] == company)
    assert [row[k] for k in ['overallScore', 'overallSentiment', 'momentumScore', 'momentumSentiment', 'socialScore', 'socialSentiment', 'strengthScore', 'strengthSentiment']] == expected
assert cycle_lookup['coach-fall-2025']['overallDisplay'] == 73.4
assert selected_cycles['Coach']['strengthRuleScoreConsistent'] is False
assert selected_cycles['Estée Lauder']['strengthRuleScoreConsistent'] is False
assert selected_cycles['Estée Lauder']['socialComparisonType'] == 'Annual group account'
assert cycle_lookup['moncler-grenoble-fw2026']['socialSubscoreUsed'] == 100
assert cycle_lookup['moncler-grenoble-fw2026']['irSubscoreUsed'] is None
assert cycle_lookup['moncler-grenoble-fw2026']['trendSubscoreUsed'] is None
assert cycle_lookup['moncler-grenoble-fw2026']['overallDisplay'] is None
assert all(cycle_lookup[key]['overallDisplay'] is None for key in ['moncler-grenoble-fw2024', 'estee-lauder-companies-fy2025', 'victorias-secret-fy2025', 'coach-spring-2025'])
assert [momentum_sentiment(dec(v)) for v in [0, 39.9, 40, 60, 60.01, 74.99, 75, 100]] == ['Low', 'Low', 'Neutral', 'Neutral', 'Medium', 'Medium', 'High', 'High']
assert [social_sentiment(dec(v)) for v in [0, 39.9, 40, 60, 60.01, 100]] == ['Negative', 'Negative', 'Neutral', 'Neutral', 'Positive', 'Positive']
assert [strength_sentiment(dec(v), dec(-3.1)) for v in [-3, -2, 0, 1.99, 2, 2.01, 7.8]] == ['Fallback', 'Neutral', 'Neutral', 'Neutral', 'Neutral', 'Up and coming', 'Up and coming']
assert [strength_sentiment(dec(2.01), dec(v)) for v in [-0.01, 0, 0.01]] == ['Up and coming', 'Strong', 'Strong']
assert strength_sentiment(None, dec(0)) is None and strength_sentiment(dec(3), None) is None
assert [sentiment(dec(v)) for v in [0, 39.9, 40, 69.9, 70, 100]] == ['Needs improvement', 'Needs improvement', 'Neutral', 'Neutral', 'Good', 'Good']

for company, total, label in [('RIMOWA', 46.3, 'Neutral'), ('Bloomingdales', 37.1, 'Needs improvement'), ('Fendi', 47.3, 'Neutral')]:
    record = by_name[company]
    assert record['page1']['overallScore'] == total and record['page1']['sentiment'] == label
    assert record['page1']['standaloneBrandOverallScore'] is None
    assert record['page2']['strength']['score'] == 30 and record['page2']['strength']['sentiment'] == 'Fallback'
    assert record['evidence']['standaloneBrandFinancialSeriesAvailable'] is False
    assert record['page3']['leaderboardId'] is None
assert abs(selected_cycles['RIMOWA']['trendChangePp'] + 2.055746675448863) < 1e-10
assert by_name['RIMOWA']['audienceType'] is None and by_name['RIMOWA']['lightEnvironments'] == []
assert by_name['Bloomingdales']['audienceType'] == 'Retailer' and by_name['Bloomingdales']['lightEnvironments'] == ['Bloomingdales']
assert by_name['Bloomingdales']['evidence']['standaloneBrandCommercialContext']['growthPercent'] == 7.4

# Retain Ulta's alternate absolute-growth method outside the standard delivery.
# Both calculations are explicit because supplied precision changes the rounded total.
source_context = dict(inputs.get('sourceContext', {}))
ulta_context = dict(source_context['ultaCompanyOnly'])
ulta = cycle_lookup[ulta_context['selectedCycleKey']]
ulta_prior = cycle_lookup[ulta['priorCycleKey']]
absolute_momentum = cap(50 + 5 * dec(ulta['brandGrowthUsed']) * 100)
source_weighted = sum(dec(ulta_context[key]) * dec(inputs['weights'][weight])
                      for key, weight in [('reportedMomentumScore', 'ir'), ('reportedSocialScore', 'social'), ('reportedStrengthScore', 'trend')])
raw_weighted = (absolute_momentum * dec(inputs['weights']['ir'])
                + dec(ulta['derivedSocialSubscore']) * dec(inputs['weights']['social'])
                + dec(ulta_context['reportedStrengthScore']) * dec(inputs['weights']['trend']))
ulta_context.update({
    'selectedCycleKey': ulta['cycleKey'],
    'weightedFromReportedComponents': num(source_weighted),
    'derivedAbsoluteMomentumScore': num(absolute_momentum),
    'derivedSocialScore': ulta['derivedSocialSubscore'],
    'derivedOwnGrowthChangePp': num((dec(ulta['brandGrowthUsed']) - dec(ulta_prior['brandGrowthUsed'])) * 100),
    'derivedContextOverallUnrounded': num(raw_weighted),
    'derivedContextOverallDisplay': num(rounded(raw_weighted)),
    'derivedContextOverallSentiment': sentiment(rounded(raw_weighted)),
    'standardPeerRelativeOverallScore': None,
    'productionReady': False, 'leaderboardEligible': False,
})
source_context['ultaCompanyOnly'] = ulta_context
assert num(rounded(source_weighted)) == 73.1 and ulta_context['derivedContextOverallDisplay'] == 73.0
assert ulta['overallDisplay'] is None and ulta['irSubscoreUsed'] is None and ulta['trendSubscoreUsed'] is None
active_files = {s['fileName'] for s in inputs['sourceDocuments'].values()}
received_files = active_files | {s['fileName'] for history in inputs.get('sourceDocumentHistory', {}).values() for s in history}
assert len(received_files) == 51
giii = selected_cycles['G-III Apparel Group']; meem = selected_cycles['ME+EM']
assert giii['overallDisplay'] == 33.3 and giii['irSubscoreUsed'] == 12.6235
assert giii['socialSubscoreUsed'] == 70 and giii['strengthSentiment'] == 'Fallback'
assert giii['baselineMedianLikes'] is None and giii['showMedianLikes'] is None
assert by_name['G-III Apparel Group']['lightEnvironments'] == by_name['G-III Apparel Group']['companyCodes'] == by_name['G-III Apparel Group']['emailDomains'] == []
assert by_name['G-III Apparel Group']['page4']['invitation'] is None
assert by_name['DKNY']['page1']['overallScore'] == 42.3
assert by_name['DKNY']['page1']['standaloneBrandOverallScore'] is None
assert meem['overallDisplay'] == 86 and meem['financialPeriodEnd'] == '2025-01-26'
assert meem['baselinePostCount'] == 2 and meem['showPostCount'] == 6
assert meem['trendChangePp'] == -22.71 and meem['strengthSentiment'] == 'Fallback'
for name, social in [('David Yurman', 65.19), ('NORDSTROM', 34.8101)]:
    c = cycle_lookup['david-yurman-calendar-2025-proxy'] if name == 'David Yurman' else selected_cycles[name]
    assert c['socialSubscoreUsed'] == social
    assert c['irSubscoreUsed'] is None and c['trendSubscoreUsed'] is None and c['overallDisplay'] is None and c['irPeerRank'] is None
assert cycle_lookup['david-yurman-calendar-2025-proxy']['financialPeriodStart'] is None and cycle_lookup['david-yurman-calendar-2025-proxy']['financialPeriodEnd'] is None
assert cycle_lookup['david-yurman-calendar-2025-proxy']['socialIncludedCalendarMonths'] == [7, 8, 9, 11, 12]
assert by_name['NORDSTROM']['page2']['momentum']['historicalFinancialContext']['displayScore'] == 80.6
assert by_name['NORDSTROM']['page2']['momentum']['historicalFinancialContext']['peerRank'] == 1
nord_context = dict(source_context['nordstromMixedPeriod'])
nord_source_total = dec(nord_context['reportedMomentumScore']) * dec(inputs['weights']['ir']) + dec(nord_context['reportedSocialScore']) * dec(inputs['weights']['social']) + dec(nord_context['assumedStrengthScore']) * dec(inputs['weights']['trend'])
nord_context['weightedFromReportedComponents'] = num(nord_source_total)
nord_context['roundedFromReportedComponents'] = num(rounded(nord_source_total))
source_context['nordstromMixedPeriod'] = nord_context
assert nord_context['roundedFromReportedComponents'] == 60.7 and nord_context['strengthIsObserved'] is False

fendi = selected_cycles['Fendi']
fendi_show = cycle_lookup['fendi-ss2026-show-social']
assert fendi['irSubscoreUsed'] == 50.4084 and fendi['socialSubscoreUsed'] == 53.62
assert fendi['trendChangePp'] == -2.0557 and fendi['trendSubscoreUsed'] == 30
assert fendi['overallUnrounded'] == 47.2902 and fendi['overallDisplay'] == 47.3
assert by_name['Fendi']['page1']['normalizedFashionMomentumIndex'] == 80.1
assert by_name['Fendi']['lightEnvironments'] == ['LVMH'] and by_name['Fendi']['audienceType'] == 'Brand'
assert fendi_show['socialSubscoreUsed'] == 100 and fendi_show['overallDisplay'] is None
assert fendi_show['irSubscoreUsed'] is None and fendi_show['trendSubscoreUsed'] is None
assert [fendi_show[k] for k in ['baselinePostCount', 'showPostCount']] == [21, 17]
assert source_context['fendiReportAlternatives']['percentileComparison']['reportedOverall'] == 47.0
assert source_context['fendiReportAlternatives']['usedForDeliveryScores'] is False

# The newly supplied reports establish account coverage, not scored comparisons.
for name in ['Belmont Park Village', 'Christian Louboutin']:
    c = selected_cycles[name]
    assert all(c[k] is None for k in ['irSubscoreUsed', 'socialSubscoreUsed', 'trendSubscoreUsed', 'overallDisplay', 'overallSentiment', 'socialSentiment', 'irPeerRank'])
    assert by_name[name]['page1']['normalizedFashionMomentumIndex'] is None
    assert by_name[name]['lightEnvironments'] == [name]
    assert by_name[name]['page3']['leaderboardId'] is None
assert by_name['Belmont Park Village']['audienceType'] == 'Retailer'
assert by_name['Christian Louboutin']['audienceType'] == 'Brand'
assert selected_cycles['Belmont Park Village']['showMedianLikes'] is None
assert selected_cycles['Belmont Park Village']['socialAggregates']['comparisonMissingLikesCount'] == 2
assert selected_cycles['Christian Louboutin']['showMedianLikes'] == 8590
louboutin_mentions = dict(source_context['louboutinCoverage']['retailerCaptionMentions'])
baseline_share = dec(louboutin_mentions['baselineMentions']) / dec(louboutin_mentions['baselineSampledPosts'])
comparison_share = dec(louboutin_mentions['comparisonMentions']) / dec(louboutin_mentions['comparisonSampledPosts'])
louboutin_mentions.update({
    'derivedBaselineShare': num(baseline_share), 'derivedComparisonShare': num(comparison_share),
    'derivedShareChangePercent': num((comparison_share / baseline_share - 1) * 100),
    'derivedCountChangePercent': num((dec(louboutin_mentions['comparisonMentions']) / dec(louboutin_mentions['baselineMentions']) - 1) * 100),
})
source_context['louboutinCoverage']['retailerCaptionMentions'] = louboutin_mentions


# October28 supplied observations independently reconciled from exact revenue pairs.
for company, total, momentum, social, strength in [
    ('Ulta Beauty',63.6,75.7,32.6,80), ('LVMH',32.6,11.5,42.6,70),
    ('Marc Jacobs',20.0,11.5,0.7,70), ('Louis Vuitton',31.5,11.5,39.1,70),
    ('Five Below',None,100,None,80), ('Missoni',None,None,47.9,None)]:
    c=selected_cycles[company]
    assert c['overallDisplay']==total
    for key, expected in [('irSubscoreUsed',momentum),('socialSubscoreUsed',social),('trendSubscoreUsed',strength)]:
        assert (num(rounded(dec(c[key]))) if c[key] is not None else None)==expected,(company,key)
assert cycle_lookup['ulta-beauty-fy2025']['overallDisplay'] is None
assert cycle_lookup['marc-jacobs-parent-fy2025']['overallDisplay']==31.4
assert source_context['ultaCompanyOnly']['selectedCycleKey']=='ulta-beauty-fy2025'
assert source_context['jcrewExternalProxy']['usedForDeliveryScores'] is False
assert source_context['missoniConditionalReport']['usedForDeliveryScores'] is False
assert by_name['Missoni']['companyCodes']==by_name['Louis Vuitton']['companyCodes']==by_name['LVMH']['companyCodes']==[]
assert by_name['Global Luxury Retail Group DBA Missoni']['selectedCycleKey'] is None
assert all(not by_name[n]['lightEnvironments'] and by_name[n]['page4']['invitation'] is None for n in ['Missoni','Louis Vuitton','LVMH'])
assert by_name['RIMOWA']['page2']['strength']['cardDescriptor']=='Stable'
assert by_name['RIMOWA']['page2']['strength']['cardKpi'] is None
assert by_name['Belmont Park Village']['page2']['strength']['cardKpi']['comparisonOperator']=='>'
assert by_name['Belmont Park Village']['page2']['strength']['cardKpi']['value']==1.0

# Apply explicitly requested score revisions only after the calculation regressions.
# Retain the complete calculated record/row so source observations are never rewritten.
score_revisions = inputs.get('scoreRevisions', {})
if score_revisions:
    normalization_review['calculatedBaseline'] = {
        'observedMinimum': num(observed_min), 'observedMaximum': num(observed_max),
        'displayIndices': {r['prospect']: r['normalizedFashionMomentumIndex'] for r in delivery_rows},
        'basis': 'Calculated report results before applying supplied score revisions',
    }
for company, revision in score_revisions.items():
    assert revision['usedForDelivery'] and not revision['usedForCalculatedMethod']
    assert 0 <= revision['overallScore'] <= 100
    supplied_normalized = revision.get('normalizedFashionMomentumIndex')
    if supplied_normalized is not None:
        assert display_lower <= dec(supplied_normalized) <= display_upper
    else:
        assert revision.get('normalizationPolicy') == 'cohort-min-max'
    accepted_proxy = revision.get('acceptedMixedPeriodProxy', False)
    record = by_name[company]
    row = next(r for r in delivery_rows if r['prospect'] == company)
    assert record['selectedCycleKey'] is not None
    calculated_record, calculated_row = deepcopy(record), deepcopy(row)
    weighted_revision = sum(dec(revision['components'][key]['score']) * dec(inputs['weights'][weight])
                            for key, weight in [('momentum', 'ir'), ('social', 'social'), ('strength', 'trend')])
    standard_labels = {
        'momentum': momentum_sentiment(dec(revision['components']['momentum']['score'])),
        'social': social_sentiment(dec(revision['components']['social']['score'])),
    }
    record['scoreRevision'] = {
        **deepcopy(revision),
        'categoryPolicy': 'preserve-supplied',
        'previousCalculatedRecord': calculated_record,
        'previousCalculatedDeliveryRow': calculated_row,
        'reconciliation': {
            'componentWeightedOverall': num(weighted_revision),
            'componentWeightedOverallDisplay': num(rounded(weighted_revision)),
            'suppliedOverallMinusWeighted': num(dec(revision['overallScore']) - weighted_revision),
            # Audit-only value is populated after every revision updates the cohort.
            # Delivery always retains normalizedFashionMomentumIndex supplied above.
            'standardNormalizedIndexForSuppliedOverall': None,
            'standardComponentSentiments': standard_labels,
            'strengthScoreInAgreedMapping': revision['components']['strength']['score'] in inputs['trendScoreMapping'].values(),
            'status': revision['reconciliationStatus'],
        },
    }
    record['page1'].update({
        'overallScore': revision['overallScore'], 'overallUnrounded': None,
        'sentiment': revision['overallSentiment'],
        'normalizedFashionMomentumIndex': supplied_normalized if supplied_normalized is not None else normalize_overall(revision['overallScore']),
        'normalizedSentiment': revision['normalizedSentiment'],
        'normalizationBasis': 'min-max-of-approved-report-proxy' if accepted_proxy else 'explicit-user-revision',
        'sentimentBasis': 'explicit-user-revision',
        'scoreBasis': revision['scope'] if accepted_proxy else 'User-supplied revision; not recalculated from the earlier report',
        'coreInsightEvidenceBasis': 'Earlier report context retained; not regenerated for this revision',
    })
    row.update({'overallScore': revision['overallScore'], 'overallSentiment': revision['overallSentiment'],
                'normalizedFashionMomentumIndex': supplied_normalized if supplied_normalized is not None else normalize_overall(revision['overallScore'])})
    for key, component in revision['components'].items():
        assert 0 <= component['score'] <= 100
        card = record['page2'][key]
        card.update({'score': component['score'], 'displayScore': num(rounded(dec(component['score']))),
                     'sentiment': component['sentiment'], 'cardDescriptor': component['descriptor'],
                     'categoryPolicy': 'preserve-supplied',
                     'sentimentBasis': 'explicit-user-revision',
                     'scoreEvidenceBasis': 'User-supplied revision; supporting inputs not supplied',
                     'observationStatus': 'Earlier report context; not supporting evidence for the revised score'})
        if card['cardKpi']:
            card['cardKpi']['qualifier'] = 'Earlier report observation; not supporting evidence for the supplied revised score'
        row.update({f'{key}Score': num(rounded(dec(component['score']))), f'{key}Sentiment': component['sentiment'],
                    f'{key}Descriptor': component['descriptor']})
    record['evidence'].update({
        'scoreSource': revision['authority'],
        'componentScoreBasis': revision['sourceType'],
        'reviewStatus': 'User score revision applied; supporting inputs and method reconciliation pending',
        'gaps': record['evidence']['gaps'] + [revision['reconciliationStatus'],
                 'Replacement financial/social inputs, period confirmation and normalization method were not supplied with the revision'],
    })
    if accepted_proxy:
        assert company == 'NORDSTROM' and revision['sourceContextKey'] == 'nordstromMixedPeriod'
        assert revision['overallScore'] == source_context['nordstromMixedPeriod']['reportedOverall']
        assert num(rounded(weighted_revision)) == revision['overallScore']
        historical = record['page2']['momentum']['historicalFinancialContext']
        financial_cycle = cycle_lookup[historical['cycleKey']]
        record['page1'].update({
            'collectionLabel': 'FY2024 financials / FY2025 social proxy',
            'status': 'User-approved mixed-period proxy; Strength 50 is assumed',
            'scopeLabel': revision['scope'],
            'coreInsightEvidenceBasis': 'Original source insight retained; missing current data is still disclosed',
            **{key: financial_cycle[key] for key in
               ['financialPeriodStart', 'financialPeriodEnd', 'financialPeriodType']},
            'financialPeriodLabel': 'FY2024 group financials; FY2025 nameplate social',
        })
        record['deliveryScope'] = revision['scope']
        record['evidence'].update({
            'scoreProfile': 'retailer-mixed-period-proxy',
            'reviewStatus': 'User-approved report proxy; FY2025 finances and observed Strength remain unavailable',
            'componentScoreBasis': revision['scope'],
            'gaps': calculated_record['evidence']['gaps'] + [revision['reconciliationStatus']],
        })
        historical['usedForProxyOverall'] = True
        for key, component in revision['components'].items():
            card = record['page2'][key]
            card.update({
                'scoreEvidenceBasis': component['evidenceBasis'],
                'observationStatus': 'Assumed, not observed' if key == 'strength' else component['evidenceBasis'],
                'scoreIsObserved': key != 'strength',
                'explanation': calculated_record['page2'][key]['explanation'] + ' Accepted report proxy: ' + component['evidenceBasis'] + '.',
            })
            if card['cardKpi']:
                card['cardKpi'] = deepcopy(calculated_record['page2'][key]['cardKpi'])
        record['page2']['strength'].update({
            'category': 'Neutral',
            'categoryBasis': 'Explicit report assumption accepted by the user; not an observed peer-gap change',
        })
# Bounds follow all delivered originals, including supplied revisions. A new minimum
# or maximum rescales ordinary rows; explicit normalized display values stay fixed.
available_indices = [dec(r['overallScore']) for r in delivery_rows if r['overallScore'] is not None]
observed_min = min(available_indices) if available_indices else None
observed_max = max(available_indices) if available_indices else None
normalization_review.update({'observedMinimum': num(observed_min), 'observedMaximum': num(observed_max),
                             'availableIndexCount': len(available_indices)})
for row, record in zip(delivery_rows, records):
    revision = score_revisions.get(row['prospect'])
    supplied_normalized = revision.get('normalizedFashionMomentumIndex') if revision else None
    row['normalizedFashionMomentumIndex'] = (supplied_normalized if supplied_normalized is not None
                                             else normalize_overall(row['overallScore']))
    record['page1']['normalizedFashionMomentumIndex'] = row['normalizedFashionMomentumIndex']
    if revision:
        # Audit-only ordinary min–max result; do not use this as the delivered index.
        record['scoreRevision']['reconciliation']['standardNormalizedIndexForSuppliedOverall'] = normalize_overall(row['overallScore'])
normalization_review['explicitScoreRevisions'] = {
    name: {'value': revision['normalizedFashionMomentumIndex'], 'authority': revision['authority'],
           'basis': 'Explicit supplied display value; does not use min–max normalization'}
    for name, revision in score_revisions.items() if revision.get('normalizedFashionMomentumIndex') is not None
}
if 'Estée Lauder' in score_revisions:
    elc_revision = by_name['Estée Lauder']
    assert elc_revision['page1']['overallScore'] == 78.3
    assert elc_revision['page1']['normalizedFashionMomentumIndex'] == 86.5
    assert elc_revision['scoreRevision']['previousCalculatedRecord']['page1']['overallScore'] == 81.3
    assert elc_revision['scoreRevision']['reconciliation']['componentWeightedOverall'] == 77.36
    assert elc_revision['scoreRevision']['categoryPolicy'] == 'preserve-supplied'
    assert elc_revision['page1']['normalizationBasis'] == 'explicit-user-revision'
    for key, score, label, descriptor in [('momentum', 72.7, 'High', 'Leading peers'),
                                          ('social', 86.7, 'Positive', 'Attention up'),
                                          ('strength', 75.0, 'Strong', 'Recovering')]:
        card = elc_revision['page2'][key]
        assert (card['score'], card['displayScore'], card['sentiment'], card['cardDescriptor']) == (score, score, label, descriptor)
        assert card['categoryPolicy'] == 'preserve-supplied'

# A normalized-only instruction does not revise original/component scores or bounds.
normalized_display_overrides = inputs.get('normalizedDisplayOverrides', {})
normalization_review['explicitDisplayOverrides'] = {}
for company, override in normalized_display_overrides.items():
    assert override['usedForDelivery'] and not override['usedForCalculatedMethod']
    assert display_lower <= dec(override['value']) <= display_upper
    record = by_name[company]
    row = next(r for r in delivery_rows if r['prospect'] == company)
    assert row['overallScore'] is not None, 'A normalized display override requires a complete underlying overall score'
    ordinary_value = normalize_overall(row['overallScore'])
    record['normalizedDisplayOverride'] = {
        **deepcopy(override),
        'previousDeliveredNormalizedFashionMomentumIndex': row['normalizedFashionMomentumIndex'],
        'standardNormalizedIndex': ordinary_value,
        'suppliedMinusStandard': num(dec(override['value']) - dec(ordinary_value)),
    }
    row['normalizedFashionMomentumIndex'] = override['value']
    record['page1'].update({
        'normalizedFashionMomentumIndex': override['value'],
        'normalizationBasis': 'explicit-user-display-override',
    })
    normalization_review['explicitDisplayOverrides'][company] = deepcopy(record['normalizedDisplayOverride'])

# Category ranks use the final displayed index, after every supplied revision.
# These are provisional content ranks; source/publication gates remain unchanged.
leaderboard_config = inputs['leaderboardConfig']
category_groups = inputs['leaderboardCategories']
assert leaderboard_config['scoreField'] == 'normalizedFashionMomentumIndex'
assert leaderboard_config['tiePolicy'] == 'competition'
assert leaderboard_config['sortOrder'] == 'descending'
assert leaderboard_config['excelScoreColumn'] == 'S'
assigned_names = [name for names in category_groups.values() for name in names]
assert len(assigned_names) == len(set(assigned_names)), 'Each prospect must have exactly one leaderboard category'
assert set(assigned_names) == {r['prospect'] for r in delivery_rows}, 'Leaderboard categories must cover the exact delivery companies'
leaderboards = []
for category, names in category_groups.items():
    cohort = [row for row in delivery_rows if row['prospect'] in names]
    scored = [row for row in cohort if row['normalizedFashionMomentumIndex'] is not None]
    board_id = 'fashion-momentum-' + category.lower().replace(' ', '-') + '-provisional'
    members = []
    for row in cohort:
        value = row['normalizedFashionMomentumIndex']
        rank = None if value is None else 1 + sum(other['normalizedFashionMomentumIndex'] > value for other in scored)
        row.update({'leaderboardCategory': category, 'leaderboardRank': rank})
        record = by_name[row['prospect']]
        record.update({'leaderboardCategory': category, 'leaderboardRank': rank})
        record['page3'] = {
            'leaderboardId': board_id, 'category': category, 'rank': rank,
            'rankedCount': len(scored), 'totalCount': len(cohort),
            'state': 'Provisional category leaderboard' if scored else 'Category awaiting scores',
            'scoreField': leaderboard_config['scoreField'], 'score': value, 'tiePolicy': leaderboard_config['tiePolicy'],
            'highlightProspectId': record['prospectId'] if rank is not None else None,
            'scope': leaderboard_config['status'],
            'note': 'Rank by the displayed normalized index within the user-assigned category. Component peer rank is separate. Missing totals have no rank.',
        }
        record['evidence']['categoryRankAvailable'] = rank is not None
        record['evidence']['leaderboardEligibilityBasis'] = 'Existing publication gate; provisional category rank is supplied separately on page3'
        members.append({'prospectId': record['prospectId'], 'prospect': row['prospect'],
                        'normalizedFashionMomentumIndex': value, 'rank': rank})
    members.sort(key=lambda member: (member['rank'] is None, member['rank'] or 0, member['prospect'].casefold()))
    leaderboards.append({'leaderboardId': board_id, 'category': category, 'totalCount': len(cohort),
                         'rankedCount': len(scored), 'unrankedCount': len(cohort) - len(scored),
                         'status': leaderboard_config['status'], 'members': members})

assert {board['category']: (board['totalCount'], board['rankedCount']) for board in leaderboards} == {
    'LUXE': (20, 10 + sum(selected_cycles[n]['overallDisplay'] is not None for n in ['Lafayette 148','Jacquemus','David Yurman'])), 'FAST FOLLOWER': (30, 11 + sum(selected_cycles[n]['overallDisplay'] is not None for n in ['J.Crew','PacSun'])), 'RETAILER': (13, 5 if 'NORDSTROM' in score_revisions else 4), 'OTHER': (11, 0)}
assert all((row['leaderboardRank'] is None) == (row['normalizedFashionMomentumIndex'] is None) for row in delivery_rows)
assert all(not record['evidence']['productionReady'] and not record['evidence']['leaderboardEligible'] for record in records)

# Supplementary source snapshots do not enter component/overall calculations.
supplement = deepcopy(inputs.get('salesSocialSupplement'))
supplement_fields = ('smFeb2024', 'q4VsBaseline2024', 'smFeb2025', 'q4VsBaseline2025',
                     'smFeb2026', 'q4VsBaseline2026', 'insightsDescriptive', 'insightsStatistics')
supplement_by_name = {}
if supplement:
    assert supplement['usedForScoring'] is False
    assert tuple(c['field'] for c in supplement['columns']) == supplement_fields
    assert len({r['sourceBrand'].strip().casefold() for r in supplement['records']}) == len(supplement['records']), 'Duplicate supplementary source brand'
    for item in supplement['records']:
        assert set(item['values']) == set(supplement_fields)
        if item['prospect'] is not None:
            assert item['prospect'] in by_name, 'Unknown matched supplement identity'
            assert item['prospect'] not in supplement_by_name, 'Duplicate supplement match'
            supplement_by_name[item['prospect']] = item
    supplement['summary'] = {
        'sourceRows': len(supplement['records']), 'matchedRows': len(supplement_by_name),
        'unmatchedBrands': [r['sourceBrand'] for r in supplement['records'] if r['prospect'] is None],
    }
for row, record in zip(delivery_rows, records):
    item = supplement_by_name.get(row['prospect'])
    row.update({field: item['values'][field] if item else None for field in supplement_fields})
    record['salesSocialSupplement'] = ({
        **deepcopy(item), 'source': deepcopy(supplement['source']),
        'definitions': deepcopy(supplement['definitions']), 'usedForScoring': False,
    } if item else None)

yoy_v2 = deepcopy(inputs.get('salesYoyV2Supplement'))
yoy_fields = ('q4VsBaseline2024YoyV2', 'q4VsBaseline2025YoyV2', 'q4VsBaseline2026YoyV2')
yoy_by_name = {}
if yoy_v2:
    assert yoy_v2['usedForScoring'] is False
    assert tuple(c['field'] for c in yoy_v2['columns']) == yoy_fields
    assert len({r['sourceBrand'].strip().casefold() for r in yoy_v2['records']}) == len(yoy_v2['records']), 'Duplicate YoY v2 source brand'
    for item in yoy_v2['records']:
        assert set(item['values']) == set(yoy_fields)
        if item['prospect'] is not None:
            assert item['prospect'] in by_name, 'Unknown matched YoY v2 identity'
            assert item['prospect'] not in yoy_by_name, 'Duplicate YoY v2 match'
            yoy_by_name[item['prospect']] = item
    # Derived output summary; canonical inputs retain only source observations/provenance.
    yoy_v2['summary'] = {
        'sourceRows': len(yoy_v2['records']), 'matchedRows': len(yoy_by_name),
        'unmatchedBrands': [r['sourceBrand'] for r in yoy_v2['records'] if r['prospect'] is None],
        'numericMatchedValuesByYear': {field: sum(item['values'][field] is not None for item in yoy_by_name.values()) for field in yoy_fields},
    }
for row, record in zip(delivery_rows, records):
    item = yoy_by_name.get(row['prospect'])
    row.update({field: item['values'][field] if item else None for field in yoy_fields})
    record['salesYoyV2Supplement'] = ({
        **deepcopy(item), 'source': deepcopy(yoy_v2['source']),
        'definitions': deepcopy(yoy_v2['definitions']), 'usedForScoring': False,
    } if item else None)

annual_context = source_context.get('annualReports20261028')
if annual_context:
    for company, source in annual_context['companies'].items():
        selected = selected_cycles[company]
        row = next(r for r in delivery_rows if r['prospect'] == company)
        source['deliveryReconciliation'] = {
            'derivedMomentum': selected['irSubscoreUsed'], 'derivedSocial': selected['socialSubscoreUsed'],
            'agreedStrength': selected['trendSubscoreUsed'], 'agreedStrengthCategory': selected['strengthSentiment'],
            'peerGapChangePp': selected['trendChangePp'], 'deliveryOverall': row['overallScore'],
            'deliveryNormalized': row['normalizedFashionMomentumIndex'],
            'deliveryMinusReportedOverall': num(dec(row['overallScore']) - dec(source['reportedOverall'])) if row['overallScore'] is not None else None,
            'normalizationBounds': [num(observed_min), num(observed_max)],
            'basis': 'Derive exact supplied raw pairs; apply agreed peer-relative Strength and current cohort normalization. Report own-growth Strength/display are alternative methods.',
        }

output = {
    'title': 'Fashion Momentum — compact weighted delivery table', 'dataAsOf': inputs['dataAsOf'],
    'deliveryFormatVersion': 'expanded-v29-expanded-sales-social',
    'methodVersion': inputs['methodVersion'], 'weights': inputs['weights'],
    'trendScoreMapping': inputs['trendScoreMapping'],
    'scope': {'prospects': 74, 'allenProspects': 25, 'csvAdditions': 43, 'reportAdditions': 6, 'enablementCompanies': 70,
              'environmentMappings': 26, 'brands': 21, 'retailers': 7, 'unclassified': 46},
    'sourceDocuments': inputs['sourceDocuments'], 'selectedCycles': inputs['selectedCycles'],
    'sourceReportCount': len(active_files), 'receivedSourceReportCount': len(received_files),
    'sourceDocumentHistory': inputs.get('sourceDocumentHistory', {}),
    'leaderboardConfig': leaderboard_config, 'leaderboardCategories': category_groups, 'leaderboards': leaderboards,
    'scoreRevisions': score_revisions, 'normalizedDisplayOverrides': normalized_display_overrides, 'sourceContext': source_context, 'reportProspects': inputs.get('reportProspects', []),
    'allenWorkbookReview': inputs['allenWorkbookReview'],
    'enablementSource': enablement_input['source'], 'enablementMatchRules': enablement_input['matchRules'],
    'enablementRows': enablement_rows,
    'sentimentBands': [{'name': 'Needs improvement', 'min': 0, 'maxExclusive': 40},
                       {'name': 'Neutral', 'min': 40, 'maxExclusive': 70}, {'name': 'Good', 'min': 70, 'maxInclusive': 100}],
    'sentimentBasis': 'Calculated results use overall 40/70 bands, full-precision Momentum/Social thresholds and the agreed Strength map. Explicit score revisions retain the user-supplied categories. This is not audience-opinion analysis.',
    'componentSentimentRules': inputs['componentSentimentRules'],
    'componentInsightPolicy': inputs['componentInsightPolicy'],
    'overallDisplayNormalization': normalization_review,
    'displayPrecision': 'One decimal; calculated results use full-precision components. Explicit supplied score revisions retain their given values and categories.',
    'deliveryRows': delivery_rows, 'records': records, 'cycles': cycles, 'peerObservations': peers,
    'salesSocialSupplement': supplement, 'salesSocialSupplementHistory': inputs.get('salesSocialSupplementHistory', []),
    'salesYoyV2Supplement': yoy_v2, 'salesYoyV2SupplementHistory': inputs.get('salesYoyV2SupplementHistory', []),
    'campaignObservations': campaigns,
    'portfolioSocialObservations': portfolio_social, 'revenueProxyObservations': revenue_proxies,
}
(ROOT / 'weighted-delivery.json').write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n')

def cell(value):
    if isinstance(value, list):
        value = '; '.join(value)
    return '' if value is None else str(value).replace('|', '\\|').replace('\n', '<br>')

lines = ['# Fashion Momentum — delivery table', '',
    'The delivery includes score and component-specific sentiment for **Momentum**, **Social** and **Strength**, plus prospect, one core insight, overall score/sentiment, **Email domain(s)** and **Company code(s)** from the supplied ARCEO CSV. **Momentum** is the former IR score (50%); **Strength** is the former trend score (20%); Social remains 30%. Supporting mapping, periods, sources, board and CTA metadata are retained separately. Saved **28 October 2026**.', '',
    f"**Expanded coverage:** **74 content rows** = Allen’s **25 prospects**, **43 CSV additions**, and **6 report additions** (Tommy Hilfiger, VF Corporation, G-III Apparel Group, LVMH, Louis Vuitton and Missoni). Preserve **26 Light mappings** and **70 CSV pairings**. The LVMH CSV pairing stays on Fendi; the Missoni company report is separate from Global Luxury Retail Group DBA Missoni. **{output['sourceReportCount']} active unique reports support {len(selected_cycles)} assessments**, with **{output['receivedSourceReportCount']} distinct received filenames**, **{len(cycles)} observations** and **{len(peers)} peer observations**. **{len(available_indices)} delivered provisional totals** include Nordstrom’s explicitly accepted mixed-period proxy; **{len(delivery_rows) - len(available_indices)} rows have no total**. Report-specific percentiles, external analogues and conflicting revenue remain separate supporting context. Nordstrom’s assumed Strength is used only in its expressly accepted proxy.", '',
    '**Email-domain and code mapping:** exact case-insensitive company or Allen environment matches are used, with the explicit G-III Apparel → G-III Apparel Group alias. Coach links to Tapestry; DKNY to G-III; Calvin Klein to PVH. Fendi retains both FENDI and LVMH CSV entries; Marc Jacobs retains Marc Jacobs and WHP Global. Each pairing stays separate in supporting data. Multiple domains are preserved in source order. The new fields describe supplied email domains; the separate Allen website/domain field stays blank. CSV additions do not establish a Light environment, brand/retailer classification or scoring eligibility.', '',
    '**Overall sentiment only:** below 40 = Needs improvement; 40 to below 70 = Neutral; 70 to 100 = Good. Component labels preserve their own rules. Missing inputs remain unclassified. These labels do not measure audience opinion.', '',
    '## Normalized component sentiments', '',
    '| Component | Underlying rule | Equivalent on the existing 0–100 score | Burberry |',
    '| --- | --- | --- | --- |',
    '| Momentum | High ≥+5 pp; Medium >+2 and <+5 pp; Neutral −2 to +2 pp; Low <−2 pp | High ≥75; Medium >60 and <75; Neutral 40–60 inclusive; Low <40. Transformation: score = clamp(50 + 5 × gap in pp, 0, 100). | 34.5 → **Low**, from about −3.10 pp. |',
    '| Social | Positive >+10%; Negative <−10%; Neutral −10% to +10% inclusive | Positive >60; Negative <40; Neutral 40–60 inclusive. Transformation: score = clamp(50 + lift in percent, 0, 100). | 100 → **Positive**, from +79.9% lift. |',
    '| Strength | Agreed rule: change >+2 pp and latest peer gap ≥0 Strong; change >+2 pp and gap <0 Up and coming; change −2 to +2 inclusive Neutral; change <−2 Fallback | Categorical mapping: Strong 80; Up and coming 70; Neutral 50; Fallback 30. Both the comparable-season change and current peer gap are required. | +7.80 pp improvement, but latest gap −3.10 pp → **Up and coming / 70.0**. |', '',
    '**Agreed Strength methodology:** Peter approved this four-category rule on 27 October 2026. It retains the source score map and adds the previously missing conditions. Strength now considers recovery and current competitive position. Burberry remains below peers despite improving, so **Up and coming / 70** agrees with the source example and keeps overall **61.2 / Neutral**. Exactly −2 and +2 pp are Neutral; a latest gap of exactly 0 qualifies for Strong only when improvement exceeds +2 pp. Missing current/prior inputs stay unclassified. Original reported categories and scores remain available for provenance; approved Strength scores derive from the rule.', '',
    '**Display:** Momentum 34.49 rounds to **34.5**; Strength 70 is displayed as **70.0**. Calculate the weighted overall from the original component precision, then round its display once. Keep one supported core insight rather than multiple headline/summary fields.', '',
    '## Supporting fields for page generation', '',
    '| Group / page | Fields | Generation rule |', '| --- | --- | --- |',
    '| Identity and enablement | `prospectId`, `prospectName`, `lightEnvironments`, `audienceType`, `domain`, `emailDomains`, `companyCodes`, `enablementCompanies`, `identitySource`, `deliveryScope` | Preserve Allen names/mappings; append unmatched CSV identities with unknown scope/environment. Email domains/codes come from CSV; preserve their exact source-company pairs. The separate Allen domain field stays null. |',
    '| 1 — Overall score | Core insight, collection/annual label, show date if applicable, financial dates/type/label, measurement subject/scope, overall unrounded/display score, sentiment, status and weights | All components required. Keep missing values null and distinguish group candidates from runway results. |',
    '| 2 — Momentum component | Score/display score, normalized sentiment, 50% weight, own YoY growth, peer median growth, gap in pp, peer names/count/rank, measurement subject, revenue scope and growth basis | Use the 40/60/75 component thresholds on full precision; preserve score precision for weighting and distinguish retail/DTC from total-brand organic/comparable revenue. |',
    '| 2 — Social component | Scores/labels, 30% weight, baseline/comparison medians, lift, comparison type, dated windows, capture timing and counts | Preserve show-window, annual group-account, incomplete fiscal samples, matched calendar-date windows or portfolio campaign-median comparison; aggregate eligible campaign lifts without inventing group likes. Labels measure attention, not consumer opinion. |',
    '| 2 — Strength component | Rule-derived category/score, comparable-season change, latest peer gap, reported category/score and consistency flag | Apply the agreed four-category rule and score map; preserve original reported values separately. |',
    '| 3 — Leaderboard | Board ID, cohort/method/period scope, overall rank, ranked count, current-prospect highlight, board state | Use the assigned category board and displayed normalized index, descending. Ties share competition rank; missing totals have no rank. Keep each record’s financial/social scope and provisional evidence qualifications. |',
    '| 4 — CTA | Prospect invitation, `Unlock November signal`, destination, confirmation copy, analytics event, proposed internal-data fields | Reuse invitation copy, then confirm the actual destination and next step. Unresolved fields stay null. |',
    '| Evidence and release | Source document/URLs, capture date, score basis, review status, gaps, `productionReady`, `leaderboardEligible` | Required metadata remains accessible from details. Scores remain unvalidated for publication; provisional category ranks use the displayed normalized index. |', '',
    'The screenshot’s four pages become Overall → Components → Leaderboard → CTA. Swiping/transitions are a design suggestion. Its Victoria’s Secret equal-weight formula, 71 score and “50 = unchanged” copy belong to a different method and must not populate this table.', '',
    '## Scoring rules and necessary detail', '',
    '- **Momentum (IR):** growth = current financial period / corresponding prior-year period − 1. Preserve quarterly versus annual scope and each peer’s fiscal/calendar dates. Exact supplied revenue pairs feed derived growth; reported growth/component precision remain separate. Relative momentum = own growth − agreed peer median (pp). Score = clamp(50 + 5 × gap, 0, 100).',
    '- **Social:** lift in percent = (show median likes / baseline median likes − 1) × 100. Social score = clamp(50 + lift in percent, 0, 100). Portfolio mode takes the median of eligible campaign lifts (minimum three posts per window); source and derived lifts remain separate. The report uses Positive >+10%, Negative <−10%, Neutral between; these are attention labels, not sentiment.',
    '- **Strength (trend):** change = latest peer-relative gap − earlier comparable gap. Change >+2 pp is Strong/80 when latest gap ≥0, otherwise Up and coming/70. Change from −2 to +2 pp inclusive is Neutral/50; change <−2 pp is Fallback/30. Derive the score from the agreed category; preserve reported source values separately. Require current and prior gaps, using original reported precision when available.',
    '- **Overall:** require all three scores. Never redistribute weights when a component is absent. Round the final total once to one decimal, then assign the new numeric sentiment: Good ≥70; Neutral ≥40 and <70; Needs improvement <40.',
    '- **Scope:** quarter and annual revenue are brand/company proxies, not collection-attributed sales or evidence of causation. ELC annual corporate-account attention is a distinct comparison profile. Leave unknown dates blank. Legacy sellingQuarterStart/End stay populated only for quarterly inputs; generate from financialPeriodStart/End/Type/Label.', '',
    '**Source precision:** Burberry’s report uses Momentum/IR **34.49**, Social **100**, Strength/trend **70**: 0.5 × 34.49 + 0.3 × 100 + 0.2 × 70 = **61.245**, displayed **61.2 / Neutral**. Its rounded growth figures derive Momentum **34.50**, which would produce **61.3**. Preserve the reported components and obtain original precision before release. The compact table displays **34.5** while retaining **34.49** for weighting.', '',
    '**Ralph Lauren Spring 2026:** Momentum **100 / High** (capped); Social **39.7 / Negative**, retaining reported **39.74** for weighting; Strength **30 / Fallback** because the peer-relative lead narrowed **11.51 pp**, despite the current gap remaining **+10.27 pp**. Overall = 0.5 × 100 + 0.3 × 39.74 + 0.2 × 30 = **67.922**, displayed **67.9 / Neutral**. Core insight: retail growth leads peers, but show attention fell and its lead narrowed versus Spring 2025.', '',
    '**Ralph Lauren provenance:** the report includes financial references, 35 baseline and 43 show posts for Spring 2026, dated social windows in America/New_York, and selling-window Instagram references. The referenced social archive and sampled post URLs were not supplied; snapshot ages remain unknown. Selling-window posts are timing evidence, not the baseline/show sample. Financial links are retained as supplied and have not been independently verified here. Revenue includes other Ralph Lauren labels and uses a quarter proxy. Its reported Strength rule differs from the agreed rule; the source rule is retained as provenance and the agreed rule governs all records. The observed declines classify Fallback under both rules. Scores retain provisional evidence status; category ranks use the displayed index.', '',
    '**TOM FORD Autumn/Winter 2026 (Fashion):** Momentum **57.5 / Neutral**, Social **100 / Positive**, Strength **30 / Fallback**. Own organic/comparable growth is **+5%**, versus a **+3.5%** Gucci/Zegna brand median, giving **+1.5 pp** momentum and second place in this component cohort. The same-season lead fell from **+8.0 pp** to **+1.5 pp**, a **−6.5 pp** change. Overall = 0.5 × 57.5 + 0.3 × 100 + 0.2 × 30 = **64.75**, displayed **64.8 / Neutral**. Core insight: Fashion revenue grew 5% and show attention rose, but its peer lead narrowed versus Autumn/Winter 2025.', '',
    '**TOM FORD provenance and scope:** attach the report to Allen’s existing TOM FORD identity and Tom Ford environment, preserving both CSV email domains. Financial measurements cover Tom Ford Fashion operated by Zegna Group, include wholesale and exclude Tom Ford Beauty. Preserve issuer organic/comparable adjusted growth rates rather than deriving them from unadjusted totals. Gucci is an independent benchmark; Zegna brand belongs to the related operating group. Issuer definitions differ, including 2025 license adjustments. Fashion-filtered `tomford` posts use Europe/Paris windows; latest medians are 5,371 likes across 5 baseline posts and 8,588 across 4 show posts, giving **+59.9%** attention lift. The small sample, archive, individual posts and unknown measurement ages need review. All social subscores cap at 100. Q3 2026 is a completed selling-quarter proxy; Autumn/Winter sales continue into Q4. Source links and report hash are retained without independent verification. Spring/Summer’s cross-season comparison remains provisional; the agreed Strength rule governs all cycles and agrees with both declining source classifications. This score remains unvalidated for publication; its provisional LUXE snapshot rank is separate.', '',
    '**Moncler Grenoble FW2025:** **49.8 / Neutral**, Momentum **27.5 / Low** (reported **27.54** for weighting), Social **100 / Positive**, Strength **30 / Fallback**. Show likes rose 281.1%; same-season momentum fell 13.49 pp from +9.00 to −4.49 pp. Financial scope is Moncler-brand DTC across lines, excluding Stone Island and wholesale; Grenoble is not isolated. Q4 DTC = annual minus nine-month DTC; supplied EUR pairs are retained. December availability anchors make Q4 a broad proxy; winter selling continues into Q1. **FW2026 is social-only**: 5 baseline / 20 show posts, +330.6%, Social 100. Its commercial dates, Momentum, Strength and overall stay blank. Select FW2025 as the latest complete result and do not present it as FW2026.', '',
    '**Coach Spring 2026:** **70.2 / Good**, Momentum **100 / High**, Social **13.9 / Negative**, Strength **80 / Strong**. Current lead +18.55 pp improves +4.87 pp, so the agreed rule replaces source Up and coming/70. Overall = 0.5 × 100 + 0.3 × 13.90 + 0.2 × 80 = **70.17 → 70.2**; original **68.2** remains provenance. Fall 2025 similarly becomes **73.4**, versus reported 71.4. Coach brand sales include all channels and use annual Tapestry fiscal-year proxies; June versus peer March years differ. Exact USD pairs, peer periods and selected official posts are retained. Fall 2025 and Spring 2026 reuse FY2026 financial observations, rather than representing independent revenue outcomes. Full archive, capture ages and campaign-anchor URLs remain missing. Tapestry routing stays intact.', '',
    '**Victoria’s Secret Fashion Show 2025/FY2026:** **61.1 / Neutral**, Momentum **50.2 / Neutral** (reported 50.23), Social **100 / Positive**, Strength **30 / Fallback**. Annual company sales are almost level with Wacoal/Aerie; show attention rises about 155.1% (38 baseline / 8 show posts). The 2 February 2025–31 January 2026 proxy includes months before the show, PINK and Adore Me. Wacoal March years, January retail years and company/segment scopes differ. Latest explicit gap 0.046 pp minus rounded prior 2.28 pp gives **−2.234 pp**, versus reported −2.24 pp; both classify Fallback. Retain the original-precision gap. Named financial documents lack URLs; archive, timezone and capture evidence are absent. Use agreed overall 40/70 bands instead of source 50/70.', '',
    '**Earlier calculated Estée Lauder Companies Group FY2026 candidate (superseded in delivery by the explicit user revision):** **81.3 / Good**, Momentum **75.7 / High** (reported arithmetic 75.65), Social **91.7 / Positive** (91.72 for weighting), Strength **80 / Strong**. Annual momentum improves about 14.30 pp and is ahead by 5.129 pp: Strong/80 replaces reported Up and coming/70. Overall = 0.5 × 75.65 + 0.3 × 91.72 + 0.2 × 80 = **81.341 → 81.3**; original **79.3** stays in provenance. The source table says 75.6 while weighting uses 75.65; preserve arithmetic precision and flag review. This is a **group** candidate on CSV Estée Lauder, with code/group identity and live environment pending. Beauty includes Tom Ford Beauty and excludes Fashion. Social uses annual @esteelaudercompanies medians: FY2026 667.5/76 posts versus FY2025 471/66 (+41.7%); 52/76 current posts name portfolio brands. It is not runway lift, all-portfolio reach or a subsidiary-brand score. ELC/Coty June years differ from L’Oréal calendar years; retain peer periods and named sources. Source URLs, archive and capture ages are missing. Keep this profile outside an unreviewed runway leaderboard.', '',
    '**Gap Inc portfolio FY2025:** **60.5 / Neutral**, Momentum **33.0 / Low** (reported **32.9747** for weighting), Social **100 / Positive**, Strength **70 / Up and coming**. Consolidated annual revenue growth of about 1.86% trails the A&F/AEO median of 5.26%; peer gap −3.41 pp, component rank 3/3. The annual gap improves 3.723 pp from supplied exact revenues, versus reported 3.71 pp (3.70 from rounded reported gaps), but remains below peers. Overall = 0.5 × 32.9747 + 0.3 × 100 + 0.2 × 70 = **60.48735 → 60.5**. Annual FY2025 runs 2 February 2025–31 January 2026; FY2023 has 53 weeks versus 52 in FY2024/FY2025. Social is the median of three eligible brand campaign lifts: Gap +22,352.9%, Old Navy +409.8%, Banana Republic −33.1%. Athleta has no baseline and only one event post, so is excluded under the minimum-three-posts rule. No group baseline/event median is invented. Campaign anchors, medians/counts, caption terms, derived windows and financial URLs are retained in child observations. Old Navy announcement 22 October differs from availability 28 October; selling context crosses Q3/Q4, with no invented quarter dates. Archive retention on 20 October 2026 is not post-like capture timing. Supplied exact revenues derive Momentum 33.0397 and peer gap −3.392 pp, versus reported 32.9747 and −3.41 pp; both totals round to 60.5. All data and links remain provisional; independent financial checks, archive and capture ages are missing. Existing GAP Inc Allen/CSV mapping and Gap-brand invitation stay intact; review group-versus-brand CTA scope. Agreed overall 40/70 bands supersede source 50/70.', '',
    '**Lilly Pulitzer FY2025:** **42.9 / Neutral**, Momentum **40.7 / Neutral**, Social **28.4 / Negative** (28.38 for weighting), Strength **70 / Up and coming**. Segment annual sales grow about 4.28%, trailing the Ralph Lauren/J.Jill median by a reported 1.86 pp. The reported gap improves 7.45 pp; prior peer reference revenues/growth are unavailable and are not backsolved. Instagram medians fall from 770/125 posts to 603.5/230 posts (−21.6%). These are incomplete fiscal-year samples with missing months and unequal observation spans; matched April 26–October 22 medians instead rise from 533 to 555 (+4.1%). Preserve this sensitivity without replacing the main sample. Likes captured 20 October 2026 are accumulated counts, not fiscal-year earned likes. Source financial-only 49.1 remains separate from the combined score; links and database aggregates remain unverified.', '',
    '**Kohl’s FY2025 annual retailer candidate:** **48.9 / Neutral**, Momentum **35.6 / Low** (35.5849 for weighting), Social **70.5 / Positive** (70.4819), Strength **50 / Neutral**. Agreed overall 40/70 bands supersede source 50/70, changing only the label from Needs improvement. Merchandise-only revenue excludes other revenue/construction and differs from the Kohl’s total-revenue benchmark used for Target. Reported annual peer-gap improvement +0.61 pp (rounded gaps imply +0.62) stays Neutral. TikTok median 41.5/8 posts rises to 50/180 (+20.48%); the prior fiscal year covers only its final month, so this is an available-post proxy. January-only +45% lift and source 56.3 overall remain unused sensitivity. Deduplication, source SQL/raw-row retention and the capture label 2026-10-27T09:50:52.084760 are report claims; timestamp timezone and raw rows are not supplied. Preserve Retailer classification, Kohl’s environment, CSV and CTA; exclude this candidate from the shared brand board pending scope review.', '',
    '**Target FY2025 financial-only retailer candidate:** Momentum **40.5 / Neutral**, Strength **30 / Fallback**; **Social, weighted overall and overall sentiment stay blank**. Its reported financial-only **37.5 / Needs improvement** rescales Momentum/Strength weights and is retained in supporting fields, never used as the 50/30/20 overall. The seven available Instagram posts are October 2026 and outside both completed fiscal years. Consolidated operating revenue includes merchandise and ancillary income; Walmart/Kohl’s total-revenue peers differ in mix and fiscal dates. Prior peer reference revenues/growth are absent. The CSV identity/code/domain stays Target / target / target.com; audience type, environment and CTA remain unknown. Keep this retailer proxy outside the shared brand board.', '',
    '**Superseded Ulta Beauty FY2025 social-only candidate (before 28 October):** Social **32.6 / Negative** (reported **32.57**); **Momentum, Strength, peer rank and overall/sentiment stay blank**. Own annual net sales grow about 9.71% and accelerate 8.92 pp, but own growth change is not peer-relative Strength. The source requires two comparable peers with three eligible annual revenue observations each. Douglas EUR 4.451 bn to 4.5753 bn (+2.79%) is directional September-year context; its prior eligible reference year is unavailable. Sephora standalone revenue is missing, and LVMH Selective Retailing is a rejected mixed-group substitute. Sally Beauty and Bath & Body Works remain rejected/incomplete alternatives per source review. The explicit Incomplete benchmark gate prevents financial scores/ranks from numeric edits until review. Instagram medians 1285/268 posts to 1061/667 posts (−17.43%) give the social score; totals rise 136.2% with 148.9% more posts. Three duplicate IDs were removed per source. Monthly presence is not a census; the first 18 FY 2024 days have no posts, and accumulated post ages/format/paid exposure differ. UTC fiscal grouping and 20 October 2026 capture are retained as report claims. Ulta remains an unclassified CSV identity with no environment/CTA; links and raw SQL/rows remain unverified. The current replacement-peer result is **63.6 / Neutral**; the earlier incomplete cycle stays in history.', '',
    '**Amazon Fashion FY2026 matched-date social-only candidate:** Social **0 / Negative**; **Momentum, Strength, rank and overall/sentiment stay blank**. Zero is a real capped component score, never an overall score. TikTok September 27–October 26 2025 (62 posts, median 43) versus the same 30 calendar dates in 2026 (27 posts, median 14) gives **−67.44%**; all numeric-like account posts, no campaign caption filter. The 2025 posts had an extra year to accumulate likes, so the decline cannot establish weaker demand, audience opinion or early engagement velocity. Available full-year publication cohorts are incomplete and mismatched: 170 FY 2025 posts/median 39 versus 330 FY 2026 partial/median 37; their −5.1% change is unused descriptive context. Instagram’s ten October 2026 posts are excluded. Amazon Fashion has no standalone revenue series; consolidated/AWS/online-store totals, GMV and estimates are rejected. Zalando/ASOS names are reference context without numeric inputs in the attachment. Amazon fiscal years are calendar years, but FY 2026 is incomplete; financial outcome dates remain blank. Capture 27 October 2026 / label 2026-10-27T09:50:52.084760 and America/New_York publication grouping are retained; capture timezone, raw 89 rows/SQL and primary verification remain open. Preserve Allen’s Amazon Fashion Retailer identity/environment, CSV pair and invitation; exclude this matched-window proxy from the shared brand board.', '',
    '**PacSun calendar YTD2026 social-only:** Social **42.2 / Neutral**, from Instagram medians **643 → 593** (**−7.78%**) in matching **January 1–October 6** windows for 2025 and 2026. These are calendar-YTD proxies; official PacSun fiscal dates and three-year standalone revenue remain unverified. **Momentum, Strength, rank and overall/sentiment stay blank**. A&F/Urban Outfitters consolidated annual revenue pairs and year-ending dates are context only; no estimates or isolated sales claims are substituted for own accounts. Medians use **179 numeric-like posts of 265 baseline** (86 missing, 32.5%) and **61 of 104 latest** (43 missing, 41.3%). Recorded zero likes enter the medians; missing likes are never converted to zero. Observed dates differ (January 10–September 28 2025; January 24–October 6 2026), older posts have longer to accumulate likes, and missingness may be selective. Annual samples (2024: 8 stored/4 numeric, median 0.5; 2025: 270/180, median 644.5; 2026 partial: 104/61, median 593) are unused context; the sparse 2024 baseline is rejected. TikTok’s 12 recent October posts lack a prior-year baseline and are unused. Capture **2026-10-20T18:41:26Z**, UTC capture timezone and America/New_York publication grouping are retained as source claims; SQL/all 369 rows, deduplication and source financial checks are not independently verified. Preserve Allen’s **PacSun / Brand / PacSun environment**, code pacsun, both **pacsun.com / pacificsunwear.com** email domains and original invitation. This proxy has no approved weighted cohort or overall rank.', '',
    '**Separate PVH brand results:** **Calvin Klein Collection Spring 2026: 38.5 / Needs improvement**, Momentum **5.1 / Low** (derived 5.075), Social **100 / Positive**, Strength **30 / Fallback**. **Tommy Hilfiger Spring 2026 campaign: 54.7 / Neutral**, Momentum **37.3 / Low** (derived 37.325), Social **100 / Positive**, Strength **30 / Fallback**. Growth comes from PVH total-brand revenue, including retail, wholesale and licensing: Calvin Klein −6.81%, Tommy −0.36% versus rounded Ralph Lauren/G-III median +2.175%. Both use PVH Q2 **May 4–August 2, 2026** as a selling proxy. Their social anchors differ: Calvin Klein **September 12, 2025 runway** (8319/28 baseline posts to 19427/37 event posts) and Tommy **February 24, 2026 campaign** (6022/11 to 11185/6). Social windows use all-account event −15/−1 baseline and caption-related day 0/+7 posts in America/New_York. Capture ages and full archives remain unknown.', '',
    '**PVH Strength, precision and scope:** prior-year same-season **financial positions** supply the Strength baseline, rather than claiming two comparable runway collections. Calvin Klein reported gaps +0.94→−8.98 give −9.92 pp from rounded inputs; the source says −9.93 pp. Tommy −0.51→−2.54 gives −2.03 pp, only 0.03 below the Fallback boundary. Both remain Fallback 30 under the agreed rule. This method extension, earlier Ralph Lauren quarter and G-III PVH licensing relationship require review. Source component tables contain display-only precision. Recompute from supplied rounded growth and medians: Calvin Klein5.075×0.5+100×0.3+30×0.2=38.5375→38.5; Tommy37.325×0.5+100×0.3+30×0.2=54.6625→54.7. Source totals 38.5438/54.6568 remain separate and are not backsolved. Tommy’s earlier source Momentum 47.4 versus derived 47.45→47.5 stays explicit. Calvin Klein Fall 2025 remains 52.0; Tommy Spring 2025 has no overall without its earlier Strength baseline. Future Calvin Klein Fall 2026/Spring 2027 and Tommy Spring 2027 are social-only, with exact financial dates left blank. Tommy Spring 2027 has one event post; no complete commercial result is implied.', '',
    '**PVH identity and unused portfolio aggregate:** populate existing **Calvin Klein / PVH environment / pvh.com / pvh** and preserve its invitation. **Tommy Hilfiger** is a new, user-requested report row, absent from Allen and CSV; environment, domain, code and invitation stay blank. Parent PVH is context only and grants no routing or enablement mapping. The report’s combined **47.3 PVH core-brand portfolio score** and FY 2025 annual revenue weights are retained in `sourceContext`, explicitly **unused for either brand score**. Heritage Brands is excluded from that source aggregate. All original 68 identities,26 mappings and 70 CSV pairings remain intact. There is no approved cross-profile leaderboard.', '',
    '**VF Corporation FY 2026:** **38.4 / Needs improvement**, Momentum **28.7 / Low** (source 28.7482 for weighting), Social **33.5 / Negative** (derived 33.5085176; source 33.5085), Strength **70 / Up and coming**. Fiscal dates: FY 2024 April 2, 2023–March 30, 2024; FY 2025 March 31, 2024–March 29, 2025; FY 2026 March 30, 2025–March 28, 2026. Group revenue is consolidated continuing operations: Supreme retrospectively excluded; Dickies included through November 12, 2025 sale and full earlier years. Reported gap −10.58→−4.25 improves 6.33 pp while still trailing Columbia/Deckers. Columbia calendar years end about 3 months earlier; exact Deckers start dates remain blank. USD-billion inputs9.916→9.505→9.605 and peers derive Momentum 28.8144 and alternative overall38.5, whereas the source supplies original28.7482 and total 38.4. Keep both; do not hide the precision difference or treat the perimeter as fixed organic growth.', '',
    '**VF selected portfolio attention:** use the median of three equal brand lifts, not pooled/revenue-weighted group likes. The North Face 6279/120 numeric posts→4563/184 (−27.33%); Vans 11302/149→10237/317 (−9.42%); Timberland 4138.5/160→3456/181 (−16.49%). Timberland total counts167/190 exclude 7/9 missing; other total/missing counts are unknown. North Face earlier sample startsJune 27, 2024 and misses the first quarter. Child medians/counts/window dates/flags feed the editable Brand social sheet and parent calculation. Missing included inputs leave the group component blank; recorded zeros remain valid. Excluding North Face yields source 39.5 sensitivity, retained unused. Capture 2026-10-20T18:41:26Z/UTC and America/New_York publication grouping are source labels;1127 raw rows/SQL are referenced, not supplied. VF is a report addition with unknown type, blank environment/domain/code/invitation and no board.', '',
    '**Foot Locker FY 2025 at Dick’s:** **36.0 / Needs improvement**, Momentum **0 / Low**, Social **100 / Positive**, Strength **30 / Fallback**. This is Foot Locker’s wider acquired unit (including Kids Foot Locker, Champs, WSS and atmos), not Dick’s consolidated growth. FY 2023 January 29, 2023–February 3, 2024 has53 weeks; FY 2024 February 4, 2024–February 1, 2025 and FY 2025 February 2, 2025–January 31, 2026 have52. Standalone FY 2024 revenue7.988 bn is the scoring denominator; FY 2023 amount is not supplied/backsolved, so earlier −2.20% growth remains reported. FY 2025 combined unaudited pro forma21.786502 minus legacy Dick’s14.108943 gives **7.677559 bn**. The FY 2024 residual 21.431183−13.442849=7.988334 bn is a **cross-check only**,0.334 million above reported 7.988. The Revenue proxies sheet exposes and recalculates both residuals. Dick’s acquired Foot Locker September 8, 2025;3.106 bn post-acquisition segment sales are partial and excluded from annual growth. Acquisition/intercompany/perimeter assumptions need verification.', '',
    '**Foot Locker social, peers and identity:** January 2025 median284/3 posts (observedJanuary9–18) versus January 2026 median457.5/10 (January1–21) gives +61.09%, Social 100. This is a tiny matched year-end proxy, not complete annual social. Accumulated ages/coverage differ. Recent Instagram and later FY 2026 matched YTD −44.1% remain unused. JD GBP growth and Academy/Foot Locker USD growth are compared as percentages; revenue levels are not converted. Peer exact dates, JD restatement/53-week base and acquisition scope remain review gaps. Reported gap −4.71→−10.15 declines 5.44 pp/Fallback. Source capture 2026-10-27T09:50:52.084760 has unknown timezone;204 raw TikTok rows/SQL are not supplied. Preserve CSV Foot Locker / footlocker.com / footlocker, unknown audience type and absent environment/invitation. No Dick’s routing or new board is inferred. Agreed40/70 bands supersede both reports’50/70 bands; both totals remain Needs improvement.', '',
    '**RIMOWA FY2025 parent-context hybrid:** **46.3 / Neutral**, Momentum **50.4 / Neutral** (source 50.4084), Social **50.4 / Neutral** (source 50.3650), Strength **30 / Fallback**. Financial inputs are LVMH Fashion and Leather Goods EUR millions 42,169→41,060→37,770, compared with Gucci and Hermès annual reported revenues. They do not measure RIMOWA standalone sales or a luggage peer cohort. Reported parent gaps +2.1374→+0.0817 decline 2.0557 pp, only 0.0557 pp beyond Fallback. Neutral Strength sensitivity gives 50.3; both totals are Neutral under agreed 40/70 bands, superseding the source Needs improvement headline at 46.3. RIMOWA Instagram medians 2,740/269 posts→2,750/176 give +0.365%; all comparison likes are numeric and all 12 months represented, but coverage and accumulated ages remain uncontrolled. Capture is labelled 20 October 2026; UTC grouping and SQL/raw-row claims remain unverified. Existing CSV rimowa.com/rimowa and unknown type/environment/CTA stay intact. Standalone-brand overall remains null; no LVMH routing is inferred. The separately approved LUXE snapshot rank retains this parent-proxy scope.', '',
    '**Bloomingdales FY2025 parent-context hybrid:** **37.1 / Needs improvement**, Momentum **47.5 / Neutral** (source 47.5246), Social **24.6 / Negative** (24.6019), Strength **30 / Fallback**. Financial inputs measure Macy’s Inc. merchandise net sales USD billions 23.092→22.293→21.764, including other banners, versus Dillard’s retail and Kohl’s merchandise sales. Other/credit-card and construction revenue are excluded; the earlier base has 53 weeks versus 52 later. Reported parent gaps +2.17→−0.50 decline 2.67 pp. Bloomingdale’s own comparable sales grew **7.4%** on an owned/licensed/marketplace basis; this separate positive observation is preserved and never substituted for total-sales growth. The hybrid cannot establish declining brand sales. Instagram medians 628/23 posts→468.5/202 give −25.4%; the earlier sample starts April 16, 2024 and misses February/March/August, while the latest contains 3 recorded zeros and all 12 months. Matched-month sensitivity 37.2 remains unused. Capture 20 October 2026 and America/New_York grouping are source claims; full archives/SQL are unsupplied. Preserve Allen spelling, Retailer classification, Bloomingdales environment, bloomingdales.com/code and invitation. Standalone-brand overall remains null and all ranks stay unavailable.', '',
    '**Ulta refreshed annual benchmark:** FY2025 **63.6 / Neutral**, Momentum **75.7**, Social **32.6**, agreed Strength **80 / Strong**. Exact net sales USD millions 11,207.303→11,295.654→12,392.820 and Matas/Adore peers give latest gap **+5.1383 pp**, improving **8.8820 pp**. Source **61.6** uses own-growth Strength **70**, a different rule retained as provenance. Earlier company-only73.1/raw73.0 remains tied to the superseded incomplete cycle in Method. FY2023 has53weeks; acquisitions, geography/channel differences, lagging peer year ends and accumulated social snapshots keep the result provisional.', '',
    '**G-III Apparel Group FY2026:** **33.3 / Needs improvement**, Momentum **12.6 / Low** (source 12.6235), Social **70 / Positive comment activity**, Strength **30 / Fallback**. Consolidated sales USD billions 3.098242→3.180796→2.957012 are compared with PVH/Oxford, including licensing/business mix and unverified fiscal alignment. Reported gaps +7.47→−7.48 deteriorate 14.95 pp. Social uses three equal brand lifts in median comments for August–December 2024/2025: DKNY 8/113 posts→17/93 (+112.5%), Donna Karan 13/53→9.5/54 (−26.92%), Karl Lagerfeld 37.5/46→45/87 (+20%). Their median is +20%, with all five months and numeric comments recorded. No common likes metric is available; Karl Lagerfeld likes fell 43.6%. Comments may include complaints/spam/replies; Positive means activity, not opinion or broad engagement. Unknown exact October 2026 capture date/time, publication timezone/table and referenced raw SQL stay unavailable. Social sensitivity 0–100 gives overall 12.3–42.3, whose upper end is Neutral under agreed 40/70 bands; the source’s all-Needs-improvement claim used <50. The earlier single-brand 14.2 score was not attached and is not imported. Add a separate group report row with no inferred environment/domain/code/CTA. DKNY’s own row, invitation, G-III environment and g-iii.com/giiiapparelgroup pairing stay unchanged.', '',
    '**ME+EM FY2025 latest filed year:** **86.0 / Good**, Momentum **100 / High**, Social **100 / Positive**, Strength **30 / Fallback**. Filed turnover GBP millions 81.977→119.511→147.945 grows 23.79%, exceeding Reiss/J.Jill median by a reported 19.89 pp; its earlier 42.60 pp lead narrows 22.71 pp. Latest filed financial end is **26 January 2025**; missing FY2026 filings are not filled with a forecast or relabelled. Starts follow the day after supplied 52-week year ends and remain subject to primary-account confirmation. Reiss uses consolidated parent/restated turnover and J.Jill uses consistent restated FY2022 facts; reported GBP/USD growth is compared without converting revenue levels, with differing fiscal labels/53-week peer base. October–December 2023/2024 Instagram medians 523/2 posts→1,335.5/6 rise 155.35%. Earlier posts are October 6/December 31 with November uncovered; this two-post baseline cannot establish a stable normal level. Full available 2/22-post sensitivity also caps Social at 100. Across Social 0–100, overall ranges 56–86, so Good depends on this provisional sample. Capture 20 October 2026/Europe-London grouping, deduplication and SQL/archive claims remain unverified. Preserve Allen Brand/environment, meandem.com/meem and original invitation.', '',
    '**Superseded David Yurman calendar-2025 matched-month partial:** **Social 65.2 / Positive** (source 65.19), from medians 1,086/106 posts→1,251/95 in **July, August, September, November and December** 2024/2025. These are five non-contiguous common months, not continuous July–December or verified fiscal years. October 2025 is absent and sparse May/June 2024 are excluded. Wider May 24–December 31 sensitivity gives **+8.02% / Neutral** from 1,103/135→1,191.5/126 and remains unused. All 201 main posts have numeric likes, with missing excluded/zeros retained; medians are not month-weighted and snapshot ages/content differ. Own standalone revenue and fiscal dates remain unverified, so **Momentum, Strength, rank and overall/sentiment stay blank**. Candidate Signet/Richemont three-year series are retained with differing January/March periods, group/price mix and continuing-operation scope; no peer benchmark is applied. Capture 20 October 2026/UTC grouping and 500-post archive/SQL claims remain unverified; the single recent TikTok post is excluded. Preserve CSV davidyurman.com/davidyurman and unknown type/environment/CTA.', '',
    f'**NORDSTROM FY2025 current partial:** **Social 34.8 / Negative** (source 34.8101), Instagram medians 750.5/50 posts→636.5/198. Current own net sales after the May 20, 2025 acquisition are unverified; **standard current Momentum, observed Strength and standard overall stay blank; the accepted mixed-period proxy is delivered separately as 60.7 / Neutral, normalized {cell(by_name["NORDSTROM"]["page1"]["normalizedFashionMomentumIndex"])}, RETAILER #2**. Separately retain **FY2024 historical Momentum 80.6 / High**, source 80.6079, rank 1/3: consolidated merchandise sales including Rack 14.219→14.557 USD billions grow 2.38%, leading Macy’s/Dillard’s median by 6.12 pp. This is not FY2025 financial performance. The source **60.7 / Neutral** mixes FY2024 financials, FY2025 nameplate Social and assumed Neutral Strength 50. Source components weight to 60.74698; the source proxy and 56.7/66.7 Strength sensitivities are retained in `sourceContext`/Method, unused for the standard current-year calculation; the user explicitly accepted its 60.7 proxy for Delivery, including historical Momentum 80.6 and assumed Neutral Strength 50. Missing evidence is never an observed Neutral component. Parent Liverpool/partial acquired-period revenue is not substituted for an annual series. All 248 comparison likes are numeric and months represented unevenly; post ages, nameplate/Rack scope and raw 391-post archive/SQL remain review gaps. Preserve exact Allen NORDSTROM spelling, Retailer classification/environment, nordstrom.com/nordstrom and invitation.', '',
    '## Fendi annual parent-context hybrid', '',
    f'The supplied report selects a separate annual alternative: **47.3 / Neutral**, **normalized display {by_name["Fendi"]["page1"]["normalizedFashionMomentumIndex"]}**. Momentum **50.4 / Neutral** and Strength **30 / Fallback** describe LVMH Fashion and Leather Goods versus Gucci/Hermès, while Social **53.6 / Neutral** describes Fendi FY2025 versus FY2024. Fendi standalone commercial pace and standalone overall remain unavailable. Preserve Allen Fendi/LVMH routing and both fendi.com/fendi and lvmh.com/lvmh source pairings.', '',
    'The Spring/Summer 2026 show is a separate social-only cycle: 24 September2025; baseline9–23 September, show24 September–1 October, Europe/Rome. Medians7860/21 posts→12370/17 give57.4% lift and Social100/Positive. #FendiSS26 selection excludes the Palazzo Fendi opening. The report’s alternative **47.0 percentile score** uses five matched months and a different11-observation mixed-year cohort; retain it in `sourceContext.fendiReportAlternatives`, not the original or70–98 display index. Referenced SQL/posts/full cohort were not supplied; independent evidence review remains pending.', '',
    '## Belmont Park Village and Christian Louboutin coverage', '',
    '**Belmont Park Village:** two captured 2026 posts lack numeric likes and a baseline; village annual revenue/tenant sales, occupancy and aligned peers remain missing. All component scores and both overall indices stay blank. WWD, 19 March 2026, reports strong 2025 spend/conversion and average monthly footfall **more than doubled in Q4 versus Q3**. Revenue-card supplementary KPI is **>+100%**, labelled monthly footfall lower bound; it is not sales growth. Operating references require independent verification.', '',
    '**Christian Louboutin:** one captured TikTok post published 20 October 2026 has 8,590 likes and 38 comments, correcting a blanket missing-social-data interpretation. No matched baseline exists. The source found no own Instagram match in its checked tables, including louboutinworld; this does not establish absence from Instagram. Retailer caption mentions rise from 5 to 7, but sampled share falls from 5/489 (1.022%) to 7/1,019 (0.687%), a relative decline of 32.82%; shifting samples and small counts prevent scoring. Verified own-brand financial series/fiscal dates and aligned peers are absent. Exor revenue and a EUR1 billion ambition are not brand actuals. All scores, sentiments, overall and normalized index stay blank.', '',
    'Both reports populate existing Allen identities, environments, classifications, CSV domains/codes and invitations. Source query date is 27 October 2026; raw SQL/post/caption records, accompanying calculation files and capture ages/timezones were not supplied. The observations remain provisional; coverage-only rows have no rank. Supporting descriptive context is in sourceContext.belmontOperatingCoverage and sourceContext.louboutinCoverage, separate from score inputs.', '',
    '## Additional annual, proxy and social-only reports', '',
    '**New Balance FY2025:** agreed original **66.0 / Neutral**, Momentum **100 / High**, Social **0 / Negative**, Strength **80 / Strong**. Published sales growth 20% in 2024 and 19% in 2025 is used, rather than 17.95% derived from rounded$7.8 bn/$9.2 bn totals. Reported peer gaps 14.5941→21.5376 pp improve 6.9435 pp and the current gap is positive, so agreedStrong 80 replaces sourceUp and coming 70/sourceoriginal 64. Sourcepercentile components 100/10/55 and total 64 use a different eleven-observation cohort and stay unused. Nike May years end seven months before calendar-year New Balance/adidas; earlier 20% comes from secondary reporting. Matched social months Jul/Aug/Sep/Oct/Dec use 25,102.5/48 posts→11,197.5/20, a 55.39% fall. CSV type/environment/CTA remain unknown.', '',
    '**Marc Jacobs FY2025 parent-group hybrid:** **20.0 / Needs improvement**, Momentum **11.5 / Low**, Social **0.7 / Negative**, Strength **70 / Up and coming**. The new source replaces LVMH Fashion and Leather Goods/Gucci with LVMH consolidated group/Hermès/Moncler. Group gap improves **2.5939 pp** to **−7.6925 pp**; this is not Marc Jacobs revenue. Five matched-month social medians 4,658→2,360 remain unchanged. Source percentile 25 is separate; earlier segment 31.4 and percentile 41 stay in history. Preserve both existing environment/CSV mappings and the invitation.', '',
    '**DKNY FY2026 parent-group/comment hybrid:** original **42.3 / Neutral**, Momentum **12.6 / Low**, Social **100 / Positive comment activity**, Strength **30 / Fallback**. G-III consolidated financials and full-precision reported gaps 7.474154→−7.475304 pp do not establish DKNY revenue. Five matched months Jul/Aug/Sep/Oct/Dec use comments 8/93 posts→15/89, +87.5%; all 182 comment observations numeric. Likes only 7/93 and 14/89 are excluded from scoring. This differs from the separate G-III group Aug–Dec three-brand comment portfolio. Both records retain separate provisional scope; DKNY own commercial pace and standalone likes-based overall stay unavailable.', '',
    '**Superseded social-only additions (retained history):** J.Crew **Social 0 / Negative**, medians 2,232/133 posts→867/285 (−61.16%); all 418 selected posts numeric. Jacquemus annual **Social 0 / Negative**,108,294/19 numeric of 23→39,968/37 of 38 (−63.09%); its separate Le Paysan show 29June 2025 uses 14–28June baseline 163,276/3 posts versus 29June–6July 77,416/9 (−52.59%, Social 0). Missing likes are excluded, not zero. Source socialpercentiles 10 remain unused context. Lafayette 148 **Social 30.4 / Negative**,51/37 posts→41/64 (−19.61%) in Jun–Sep 2025/2026; no 2024 baseline exists and this is a newer four-month proxy. For all three companies, Momentum, Strength and overall remain unavailable; no assumed Strength or redistributed weights.', '',
    '**Exemplar historical banner social-only:** **Social 24.8 / Negative** from equal Saks/Neiman banner lifts−29.28%/−21.15%, median−25.22%. Retail-calendar windows 4Feb 2024–1Feb 2025 and 2Feb 2025–31Jan 2026; numeric likesSaks 53/53→269/269, Neiman 203/203→330/337. Bergdorf excluded for onebaselinepost. The historical **9.3 partial proxy** combines company-only Q2FY2025 sales with annual social and rescales 50/30 to 62.5/37.5%; it remains unused source context. Acquisition/restructuring prevents verified comparable annual group financials; neither reported quarterly decline nor official emergence establishes 2026 recovery. Full standard overall and normalized display stay blank.', '',
    '**Earlier 28 October reports and display scale (before annual refresh):** all ten uploads have new source hashes, with superseded files preserved. LVMH’s selected **32.6** uses full-year corporate social; the source five-month capped score 27.1 and percentile 28 remain context. Louis Vuitton’s selected parent-group hybrid **31.5** uses agreed peer-relative Strength 70; source own-group Strength 30 and overall 23.5 stay separate. Five Below has Momentum 100 and Strength 80 but missing Social/overall. Missoni has Social 47.9, with conditional 30.2 withheld from standard financial/overall scoring because 2025 revenue conflicts. J.Crew remains social-only; the optional unrelated Gap 26.5/30.5 proxy stays context. The 25 available originals span **20.0–86.0**, rescaling display values to 70–98. Original values change only for newly evidenced Ulta and the revised Marc Jacobs proxy; other existing displayed originals remain unchanged.', '',
    '## Explicit Estée Lauder score revision', '',
    f'User-supplied revision: **normalized 86.5 / Good**, **underlying 78.3 / Good**, **Momentum 72.7 / High · Leading peers**, **Social 86.7 / Positive · Attention up**, **Strength 75.0 / Strong · Recovering**. The component-weighted result would be **77.36 → 77.4**, while standard min–max normalization of 78.3 on the current cohort would be **{by_name['Estée Lauder']['scoreRevision']['reconciliation']['standardNormalizedIndexForSuppliedOverall']:.1f}**. Momentum 72.7 would normally be Medium; Strength 75 is outside the agreed category map. All supplied values and labels are retained as an explicit revision. Earlier observations/insights remain context; replacement supporting inputs are pending. JSON `records.scoreRevision` and Excel **Score revisions** preserve the calculated 81.3 and reconciliation.', '',
    '## Category leaderboards', '',
    'Delivery columns **Z (Category)** and **AA (Leaderboard rank)** cover all 74 rows. Rank each category by **column S, the displayed normalized Fashion Momentum Index**, descending. Equal displayed values share a competition rank (1, 2, 2, 4); missing totals have blank ranks and do not enter the ranked count. Provisional category ranks preserve original score/scope/evidence qualifications and do not approve publication.', '',
    '| Category | Companies | Ranked | Currently #1 |',
    '| --- | ---: | ---: | --- |',
    *[f"| {board['category']} | {board['totalCount']} | {board['rankedCount']} | " +
      (', '.join(f"{member['prospect']} — {member['normalizedFashionMomentumIndex']:.1f}" for member in board['members'] if member['rank'] == 1) or 'No available scores') + " |"
      for board in leaderboards], '',
    'Explicit supplied normalized displays remain fixed; other values and competition ranks follow the current cohort. Categories are user-assigned business groupings and preserve audience type, brand/parent scope and environment mappings.', '',
    '## All-prospect delivery rows', '',
    '| Prospect | One core insight | Overall score | Normalized Fashion Momentum Index (70–98) | Overall sentiment | Momentum score | Momentum sentiment | Social score | Social sentiment | Strength score | Strength sentiment | Email domain(s) | Company code(s) | Category | Leaderboard rank |',
    '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
for r in delivery_rows:
    values = [r[k] for k in ['prospect', 'coreInsight', 'overallScore', 'normalizedFashionMomentumIndex', 'overallSentiment',
              'momentumScore', 'momentumSentiment', 'socialScore', 'socialSentiment',
              'strengthScore', 'strengthSentiment', 'emailDomains', 'companyCodes', 'leaderboardCategory', 'leaderboardRank']]
    lines.append('| ' + ' | '.join(cell(v) for v in values) + ' |')
if supplement:
    lines += ['', '## Supplementary sales and social snapshot', '',
        f"Source: {supplement['source']['fileName']}, tab {supplement['source']['sheet']}, received {supplement['source']['receivedDate']}. Delivery AB:AI contains the eight requested fields. This supplementary import does not change scoring, component copy, KPIs or ranks; the separate annual-report refresh changes its five selected assessments.", '',
        supplement['definitions']['social'], '', supplement['definitions']['sales'], '',
        supplement['definitions']['forecast2026'], '', supplement['definitions']['missing'], '',
        supplement['definitions']['insights'], '',
        f"Matched {len(supplement_by_name)} of {len(supplement['records'])} source brands. Unmatched: {', '.join(supplement['summary']['unmatchedBrands']) or 'none'}. Unmatched rows are retained in the source snapshot and workbook; no identity/category/score is inferred.", '',
        '| Source brand | Delivery prospect | ' + ' | '.join(c['label'] for c in supplement['columns']) + ' | Source qualifications |',
        '| --- | --- | ' + ' | '.join('---' for c in supplement['columns']) + ' | --- |']
    for item in supplement['records']:
        values = [item['sourceBrand'], item['prospect']]
        for spec in supplement['columns']:
            value = item['values'][spec['field']]
            values.append(f'{value * 100:.1f}%' if value is not None and spec['type'] == 'percent' else value)
        values.append('; '.join(item.get('reviewNotes', [])))
        lines.append('| ' + ' | '.join(cell(v) for v in values) + ' |')

if annual_context:
    lines += ['', '## Five annual report refresh', '',
        'The new reports replace the selected PacSun, Lafayette 148, Jacquemus, J.Crew and David Yurman partials with provisional annual WWD proxies. Company revenue is source-labelled, not independently verified public disclosure. Underlying WWD workbook/source log and raw social extraction were not supplied.', '',
        '2026 matched-month social uses earlier financial years (FY2024 for Jacquemus; FY2025 for the others). The agreed peer-relative Strength rule remains active; company-only source Strength and fixed 20–94 normalized displays remain alternatives. Core insights are accepted earlier-source copy; refreshed component cards/KPIs carry current periods. Supplementary snapshots remain independent.', '',
        '| Prospect | Source raw FMI | Agreed raw FMI | Source display | Delivery display | Strength (agreed) |',
        '| --- | --- | --- | --- | --- | --- |']
    for company, source in annual_context['companies'].items():
        result = source['deliveryReconciliation']
        lines.append('| ' + ' | '.join(cell(value) for value in [company, source['reportedOverall'], result['deliveryOverall'], source['reportedNormalizedFashionMomentumIndex'], result['deliveryNormalized'], result['agreedStrengthCategory']]) + ' |')

if yoy_v2:
    lines += ['', '## Q4 sales YoY v2', '',
        f"Source: {yoy_v2['source']['fileName']}, tab {yoy_v2['source']['sheet']}, received {yoy_v2['source']['receivedDate']}. Delivery AJ:AL appends the three requested fields. This scoped YoY import preserves the other 35 fields; the separate annual-report refresh updates its five selected assessments.", '',
        *[text for definition in yoy_v2['definitions'].values() for text in (definition, '')],
        f"Matched {len(yoy_by_name)} of {len(yoy_v2['records'])} source rows; unmatched: {', '.join(yoy_v2['summary']['unmatchedBrands']) or 'none'}. Numeric matched values by year: {yoy_v2['summary']['numericMatchedValuesByYear']}.", '',
        '| Source brand | Delivery prospect | ' + ' | '.join(c['label'] for c in yoy_v2['columns']) + ' | Source qualifications |',
        '| --- | --- | --- | --- | --- | --- |']
    for item in yoy_v2['records']:
        values = [item['sourceBrand'], item['prospect']]
        for spec in yoy_v2['columns']:
            value = item['values'][spec['field']]
            values.append(f'{value * 100:,.1f}%' if value is not None else None)
        values.append('; '.join(item.get('reviewNotes', [])))
        lines.append('| ' + ' | '.join(cell(v) for v in values) + ' |')

lines += ['', '## Fashion Momentum Index display normalization', '',
    f"A separate display index maps the {len(available_indices)} available original indices from {num(observed_min)}–{num(observed_max)} onto {normalization['lowerBound']}–{normalization['upperBound']}, with {normalization['decimals']} decimal place. Original indices, component scores, sentiments and insights remain unchanged. Missing totals remain blank.", '',
    f"`Normalized index = {normalization['lowerBound']} + (original index − current minimum) / (current maximum − current minimum) × {normalization['upperBound'] - normalization['lowerBound']}`.", '',
    f"This uses all numeric selected overall indices in Delivery, including explicitly scoped parent hybrids. It is a display rescaling of the current snapshot and the basis for provisional category ranking. Excel formulas recompute the bounds when original indices change; identical indices use the midpoint (84). Estée Lauder's supplied display remains 86.5. ME+EM's supplied display remains 86.2, with ordinary result {normalize_overall(by_name['ME+EM']['page1']['overallScore']):.1f} and original 86.0 unchanged. These displays remain separate from the cohort formula.", '',
    '## Component insights for design', '',
    'The accepted card labels are Fashion Momentum Index, Trend / Peer Trajectory, Social / Show Attention and Revenue / Commercial Pace. The three authored descriptors and insights are separate from calculated score categories. Core insights are retained except minimal factual corrections for revised evidence; scores use the agreed method.', '',
    'Revenue / Commercial Pace copy describes own revenue or an explicitly identified own comparable-sales measure. The retained 20% score and category still measure peer-relative momentum strength. Do not infer own revenue from a parent hybrid score. These insights describe the saved source snapshot and must be reviewed if source inputs change.', '',
    'Each component adds one highlighted KPI and its label. Percent values are stored as decimal fractions; growth gaps use percentage points. Missing observations stay blank. Historical/proxy/coverage labels remain explicit. Show/campaign windows run from event day through day +7 inclusive, versus the previous 15 days.', '',
    inputs['componentInsightPolicy']['commercialDisplayCorrections'], '',
    'RIMOWA’s commercial-strength descriptor is Stable by user-directed display override, with no supporting standalone data supplied. Its KPI remains blank and its undisclosed-revenue insight is retained. The override is separate from numerical peer-relative Strength scores/categories and both Fashion Momentum Index columns.', '',
    '| Prospect | Trend descriptor | Trend / Peer Trajectory insight | Trend KPI | Trend KPI label | Social descriptor | Social / Show Attention insight | Social KPI | Social KPI label | Commercial descriptor | Revenue / Commercial Pace insight | Revenue KPI | Revenue KPI label |',
    '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']

def kpi_display(record, key):
    kpi = record['page2'][key]['cardKpi']
    if not kpi:
        return None
    value = dec(kpi['value']) * (100 if kpi['unit'] == '%' else 1)
    digits = kpi['decimals']
    prefix = kpi.get('comparisonOperator', '')
    if kpi['unit'] == 'count':
        return f'{value:,.0f}'
    return f'{prefix}{value:+.{digits}f}{" pp" if kpi["unit"] == "pp" else "%"}'

for r in delivery_rows:
    if r['momentumInsight'] is not None:
        record = by_name[r['prospect']]
        values = [r['prospect']]
        for key in ['momentum', 'social', 'strength']:
            values += [r[f'{key}Descriptor'], r[f'{key}Insight'], kpi_display(record, key), r[f'{key}KpiLabel']]
        lines.append('| ' + ' | '.join(cell(v) for v in values) + ' |')
lines += ['', '## Supporting inputs for repeatable generation', '',
    'Category rank fields are `leaderboardCategory` / `leaderboardRank`; `records.page3` and `leaderboards` expose the four provisional boards. Keep seasonal and peer observations as child tables keyed by `prospectId` / `cycleKey`; this prevents one brand’s multiple seasons or environments from becoming duplicate leaderboard entries.', '',
    '| Input table | Grain and fields to collect |', '| --- | --- |',
    '| Cycles | One collection/campaign or annual group observation. Show date if applicable; financial period type/label/dates; exact revenue pairs/currency/units; reported/derived growth and score precision; social medians/counts/windows/type; earlier key; agreed and reported Strength; source references/validation. Retain incomplete observations without a total. Explicit Incomplete benchmark status blocks financial scores/ranks until validated. |',
    '| Campaigns | One brand campaign keyed to a portfolio cycle. Anchor, derived dated windows, baseline/event medians and counts, minimum-post eligibility, derived/reported lifts, exclusion reason, caption terms, selling context, source URL and archive-retention versus capture timing. Portfolio lift is median of eligible derived lifts. |',
    '| Brand social | One selected brand and fiscal likes or matched-month comments comparison; explicit metric, dated windows, medians/numeric and total counts, included flag, derived lift/label, capture/timezone and coverage limits. The parent median requires every included brand to have valid inputs; no pooled group medians. |',
    '| Revenue proxies | One pro forma annual residual: combined sales minus legacy business sales. Show dates, original standalone/derived values, reconciliation and whether the residual is scored or a check. Missing components remain blank. |',
    '| Peers | One observation × peer. Exact revenue pairs/currency/units, reported/derived growth, scope, peer-specific period type/label/dates, URLs or named references. Preserve date gaps, related-group benchmarks and fiscal/calendar differences. |',
    '| Post evidence | One sampled post, with dated window/type, account, URL/date, capture timestamp, likes or null and selection/exclusion reason. Medians/counts are supplied, but full records and capture ages remain missing. Coach selected official show posts are partial evidence only. |',
    '| Board cohort | Four user-assigned categories in leaderboardCategories; rank by final displayed normalized index; competition ties and blank missing ranks. Records retain method, cycle and source scope; existing evidence/publication gates remain pending. |', '',
    'For IR, prefer exact revenue pairs. If only a reported growth rate is available, preserve it with a reported-data label and precision. The example uses reported component scores rather than inventing unseen raw inputs. Future records can derive components from verified inputs. Currency translation, constant-currency versus reported growth, retail/DTC versus consolidated scope and fiscal/calendar alignment need consistent treatment.', '',
    'Use `deliveryRows` in [weighted-delivery.json](weighted-delivery.json) for the thirty-eight-field delivery, including six authored descriptor/insight fields, six KPI value/label fields and `normalizedFashionMomentumIndex`. `records.page1` also exposes the normalized index. `records.page2` exposes `cardDescriptor` / `cardInsight` / `cardKpi` (value, unit, precision, qualifier and source cycle); the original `explanation` retains technical score provenance. `cycles` / `peerObservations` / `campaignObservations` retain calculations and original reported values. `enablementRows` and the **Enablement** sheet preserve all 70 source-company/code/domain pairings and their linked content rows. Choose `selectedCycleKey` explicitly. Update `prospectContent.componentInsights` in [weighted-delivery-inputs.json](weighted-delivery-inputs.json) for copy; scoring sources or [arceo-enablement-inputs.json](arceo-enablement-inputs.json) for approved CSV snapshot changes, then rebuild.', '',
    '## Data entry and design handoff', '',
    '1. Check CSV identity/code/domain pairs; confirm audience/group scope and environment for additions. Leave the absent website-domain field blank. Select the collection or annual observation and explicit financial/social periods.',
    '2. Fill source-backed own/peer IR measurements and matched baseline/show social inputs. Record source URLs, counts and timing.',
    '3. Link a comparable earlier season; apply the agreed Strength rule to the change and current peer gap. Preserve reported versus derived component basis.',
    '4. Generate all three component scores and the weighted overall only when complete. Draft copy stays conditional on actual values.',
    '5. Review evidence and board comparability before adding overall ranks. Review supplied annual retailer candidates separately; they do not establish a comparable brand-board method.',
    '6. Generate the four screens using the table fields; resolve CTA/analytics and test all 26 environment mappings.', '',
    '[Package entry](README.md) · [Earlier attention-method delivery snapshot](delivery-table.md) · [Earlier implementation requirements](implementation-handoff.md)', '']
(ROOT / 'weighted-delivery.md').write_text('\n'.join(lines))
print(f'Weighted delivery generated: {len(records)} content rows (25 Allen + 43 CSV additions + {len(report_prospects)} report addition), 26 Allen mappings, 70 CSV pairings; {len(selected_cycles)} assessments from {output["sourceReportCount"]} unique reports, {len(cycles)} cycles and {len(peers)} peer observations; no validated ranks.')
