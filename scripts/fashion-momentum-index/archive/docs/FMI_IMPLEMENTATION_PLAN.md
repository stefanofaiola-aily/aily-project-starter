# FMI implementation and app-ready delivery

Saved agreed implementation plan. This document records the requirements, not a
claim that all historical data or human approvals are available.

Related documents:

- [Executive summary](CONTROLLED_EXECUTIVE_SUMMARY.md)
- [Operating guide and refresh commands](CONTROLLED_PIPELINE.md)
- [Verification and current coverage](CONTROLLED_VERIFICATION.md)

## 1. Outcome and operating rules

Implement three notebooks backed by reusable service logic:

1. Extract database data and review mappings.
2. Calculate controlled raw FMI and peer diagnostics.
3. Rescale, calculate forecast uplift and generate Excel.

Cover all 92 prospects. Each receives either reviewed results or specific missing-input statuses.

Preserve the agreed defaults:

- Financial and social measurements originate from Light/shared databases or authenticated exports of those databases.
- Reports provide identity, collection dates, reporting-scope clues and evidence—not manually copied production measurements.
- Human-managed inputs use Excel; calculation policy uses versioned YAML.
- Delivered scores require reviewed inputs.
- Historical show tests freeze information at the end of show date +37 days, in the show's timezone.
- One selected headline per prospect uses approved peer-median growth; pairwise results remain diagnostics.
- Historical outputs remain unchanged audit references.
- App implementation and deployment are outside scope; this work supplies the app's data contract.

Strict historical replay remains dependent on eligible financial and forecast vintages. Current forecasts and later social captures must not substitute for historical evidence.

## 2. Inputs, mapping and extraction

Create `FMI_inputs.xlsx` with Entities, Peers, Analyses, Financial review and Post review sheets.

Required human decisions are identity mappings, approved peers, reporting scope, analysis route, periods, headline selection, forecast target and collection-post relevance. Source amounts and likes are not editable overrides.

### Mapping rules

- Keep Light company code, ticker and shared symbol separate.
- Support approved aliases and reviewed private-symbol mappings when tickers are null.
- Keep parent/group proxies explicitly labelled; never automatically substitute them for standalone brand revenue or forecasts.
- Correct Chanel and Valentino handles to `chanelofficial` and `maisonvalentino`.
- Treat competitor-table entries as candidate peers, not authoritative identifiers.
- Preserve unresolved names and blank peer lists as review tasks.
- Use the same approved peer set for both growth comparisons.

### Extraction rules

- Use separate Light and shared connections, injected into the service.
- Initialize AilySettings once per entry point. Keep tenant/environment in shell or `.env`.
- Preserve tenant `ro`, verify read-only transaction settings, and issue bounded SELECTs with explicit columns.
- Record source relation, row IDs, extraction time, query scope and resolved policy.
- Preserve user-owned changes, existing review decisions and historical files.
- Keep extracts and notebook outputs out of git.

Financial extraction must retain revenue-level provenance, underlying source candidates and correction events. Distinguish reported, interpolated, estimated and corrected values. Verify scope, currency, units, period boundaries and historical availability.

Do not interpret repeated values as reported quarters, combine cumulative periods, or sum quarterly-looking rows into annual revenue without an approved aggregation definition. Do not equate Light fiscal labels with shared calendar labels.

Social extraction must use the verified history table when the posts view is absent. Filter captures to the cutoff before deduplication; retain the latest eligible observation per stable post identity. Unknown capture timing is ineligible for strict replay. Missing likes remain missing.

## 3. Score, rescaling and uplift

Use three comparable revenue observations to calculate earlier and latest year-on-year growth:

```text
growth_pct = 100 × (current / prior − 1)
gap_pp = brand_growth_pct − median(approved_peer_growth_pct)

IR = clip(50 + 5 × latest_gap_pp, 0, 100)

social_lift_pct = 100 × (current_median_likes / baseline_median_likes − 1)
Social = clip(50 + social_lift_pct, 0, 100)

trend_change_pp = latest_gap_pp − earlier_gap_pp
```

Trend rules, in order:

- Change >+2 pp: 70.
- Change <−2 pp: 30.
- Otherwise, both gaps ≥+5 pp: 80.
- Otherwise: 50.

```text
raw_fmi = 0.50 × IR + 0.30 × Social + 0.20 × Trend
```

Missing required components or peers prevent the headline FMI; do not substitute neutral values or redistribute weights. Retain independently valid components and diagnostics.

Classify unrounded raw FMI: High ≥70, Medium ≥60, Neutral ≥40, otherwise Low.

### Social windows

- Show sample: reviewed collection posts on days 0…+7.
- Baseline: pooled posts on days −30…−1 and +8…+37.
- Minimum five usable posts per sample.
- Annual route: explicit comparable windows, at least 20 usable posts per year and three common months.
- Instagram is the controlled v1 metric. Other historical platform methods remain audit references.
- Sample thresholds are operational screening rules, not statistical confidence guarantees.

Use only commercial information available by the cutoff. Subsequent collection sales cannot support a forecast claimed to precede them. Forecast targets require explicit calendar/collection alignment.

### Rescaling

Rescale reviewed selected headlines:

```text
display_fmi = 70 + 28 × (raw_fmi − cohort_min) / (cohort_max − cohort_min)
```

Round half-up to one decimal. Equal/single-score cohorts map to 84.0; empty cohorts remain empty. Exclude diagnostics and unavailable scores. Record cohort membership and extrema. Raw classifications remain unchanged.

### Forecast uplift

Apply uplift to the rounded display score:

```text
uplift_fraction = 0.11 × expm1(8 × display_fmi / 100) / expm1(8)
adjustment = baseline × uplift_fraction
adjusted_forecast = baseline + adjustment
```

A baseline must be positive, scope/metric/unit/currency-compatible, historically available by the cutoff and target a period after it. Missing baseline does not erase a valid FMI or policy rate, but adjusted revenue remains unavailable.

Record two limitations explicitly: dynamic cohort rescaling can change an unchanged brand's uplift; the 70–98 range produces positive uplift for every available score. Uplift remains a business scenario, not calibrated predictive accuracy.

## 4. Expanded Excel and app data contract

Generate `weighted-delivery.xlsx` from one typed result model. Use stable field keys, stable IDs and explicit units. Do not implement a separate calculation path for the app.

### Delivery: one row per prospect

Include these column groups:

| Group | Required columns |
|---|---|
| Identity | Brand/entity/analysis IDs, names, Light code, ticker, shared symbol, financial subject, scope, proxy flag/label, social platform/handle/profile ID |
| Analysis | Route, collection, show date, timezone, cutoff, financial/social period labels, headline selection, policy/run/cohort IDs |
| FMI | Raw FMI, display FMI, raw classification, IR/Social/Trend scores, weights and weighted contributions |
| Revenue | Oldest/earlier/latest revenue, corresponding period labels and dates, currency, units, earlier/latest growth |
| Peer comparison | Approved peer names/count, earlier/latest peer-median growth, earlier/latest gaps in pp, comparability status |
| Trend | Change in peer-relative gap, rule-derived trend label and score |
| Social | Current/baseline windows, total/usable/included/excluded post counts, median likes, likes lift, coverage/relevance-review status |
| Forecast | Target period, forecast vintage, baseline revenue, uplift rate, absolute adjustment, adjusted forecast, matching prior-year actual, baseline and adjusted forecast YoY |
| Quality | Component/FMI/forecast statuses, missing-input reasons, source classifications, historical eligibility and evidence references |

Add optional context columns where supported by eligible observations:

- Current/baseline median comments, comment lift and usable-comment counts.
- Current/baseline median video views, view lift and usable-view counts.
- Post counts by source format and paid-partnership status, including unknown-status counts.
- Eligible follower count and capture timestamp.
- Prior follower count and growth only where comparable eligible captures exist.
- Cost of revenue, gross profit, EBITDA and corresponding margins for the selected financial periods, where verified and scope-compatible.

These context fields do not change FMI weights or uplift. Do not invent engagement rates from mismatched follower captures, substitute views for missing likes, or treat partial totals as complete.

### Supporting sheets

Use separate sheets for genuinely different data grains:

- **Financial periods:** one row per selected entity/metric/period/vintage, including amounts, period boundaries, source classification, publication/capture dates and correction provenance.
- **Peers:** one row per analysis-peer comparison, containing earlier/latest growth, gaps, pair diagnostics, approval and limitations.
- **Social posts:** retained observation per post/analysis, including dates, likes, comments, views, format, paid-partnership flag, relevance and inclusion/exclusion reason.
- **Evidence:** source references, mappings, approvals, vintage limitations and run/cohort/policy metadata.
- **Fields:** field key, Excel label, description, type, unit, derivation, required/optional status and whether it influences FMI.

The field dictionary is the app handover contract. Store rates as fractions, percentage-point gaps as pp, scores as 0–100 numbers, and amounts with explicit currency/unit multipliers. Dates and numbers remain typed values.

Missing fields remain null/blank with specific statuses. Available reviewed drivers may be displayed even when the complete FMI is unavailable. Late or unverified observations may remain in evidence, but must not appear as eligible historical app metrics.

Keep the headline columns first, supporting columns grouped, and identifying columns/header rows frozen. Generate narratives from final values rather than copying historical text.

## 5. Implementation sequence and verification

Implement in this order:

1. Reconcile historical scoring, rescaling, Trend, social-window and forecast methods.
2. Introduce Excel inputs and migrate existing human CSV configuration once.
3. Implement identity resolution, provenance and strict-cutoff extraction.
4. Implement headline scoring and pair diagnostics.
5. Implement optional context metrics without changing scoring.
6. Implement rescaling, configurable uplift, third notebook and expanded Excel.
7. Validate all prospects and document unresolved coverage/vintage requirements.

Keep business logic in an FMI service with injected clients and extend the existing Click CLI. Use ConfigRepository for tenant-specific settings and record the fully resolved YAML policy.

Tests must cover:

- Aliases, code/ticker differences, null tickers, shared-only peers and parent/brand mismatches.
- Duplicate/conflicting sources, corrections, reporting scope, annual aggregation and fiscal alignment.
- Historical availability, post-cutoff revisions and missing forecast vintages.
- Capture filtering before deduplication, timezone boundaries, missing versus zero metrics and review preservation.
- Scoring/clipping boundaries, Trend rule order and missing-component propagation.
- Rescaling endpoints, half-up rounding, empty/equal cohorts and membership changes.
- Exponential uplift benchmarks, monotonicity and compatible baseline requirements.
- Optional context missingness, sample denominators, follower comparability and unchanged FMI when context fields change.
- Stable IDs, field types/units, supporting-sheet joins and no row multiplication.
- Excel/service calculation parity, recalculation after input changes and app-facing fields never leaking ineligible historical values.

Run isolated unit tests and the required pytest, Ruff, formatting and type checks. Recalculate, scan formula errors and visually verify every workbook sheet.

Acceptance: all 92 prospects are represented, available metrics are traceable, unavailable results are explicit, and the Excel contains both headline results and the underlying app-display fields. Historical uplift remains unavailable wherever a valid dated baseline cannot be established.
