# Updating a Fashion Momentum prospect

This guide covers the saved research snapshot and the designer/app delivery contract. It does not publish an app, enable a tenant or refresh a live database. The latest inputs, JSON, Markdown and Excel belong in the same PR.

## Start after pulling the repository

Pull `main` for the merged reports, supplied revisions, category leaderboards and eight-field sales/social snapshot from [PR #166](https://github.com/Aily-Labs/aily-superagent-roadmap/pull/166). While the YoY v2 and five-report annual additions are under review, use branch `codex/fashion-momentum-yoy-v2`. After it merges, pulling `main` includes those columns too.

Open this repository in Codex. The repository skill lives at [`.agents/skills/update-fashion-momentum/SKILL.md`](../../../.agents/skills/update-fashion-momentum/SKILL.md); start a new chat if it is not listed yet. Use:

> Use $update-fashion-momentum to add or refresh [exact prospect name] from [report path]. Keep existing scores unless the supplied evidence changes their inputs. Rebuild the delivery and report what changed and what remains missing.

The report is evidence to extract, not authority to change the agreed methodology. The human's requested changes take precedence. Python 3.10+ is sufficient for checks; the full Excel rebuild also needs the Codex bundled Node and `@oai/artifact-tool` runtime. Ask Codex to load workspace dependencies if it cannot locate them. No private npm package installation or Peter-specific paths are required.

## Source and output ownership

| File | Maintain it for |
| --- | --- |
| `weighted-delivery-inputs.json` | Report provenance, observations, explicit selected cycles, component copy, KPIs and documented overrides. Main editable source. |
| `prospect-inputs.json` | Allen's final 25 prospects and 26 Light environment mappings. Preserve the approved mapping. |
| `prospect-packages.json` | Saved prospect context, invitation copy and routing input. |
| `arceo-enablement-inputs.json` | Approved 70 CSV company/code/email-domain pairings. Preserve each pairing; email domains are not website domains. |
| `weighted-delivery.json` | Generated app/content contract: `deliveryRows`, `records`, calculations and provenance. |
| `weighted-delivery.md` | Generated review/reference table. |
| `weighted-delivery.xlsx` | Generated, versioned designer/reviewer workbook, including live formulas and supporting inputs. |
| `delivery-build.json` | Generated hashes certifying which source/build files produced the three outputs. |

Excel is committed to this repository, so pulling the branch gives the current workbook. Use JSON for durable changes. Excel can be used for local formula exploration and review; copy approved changes back into the JSON inputs and rebuild before committing. A downloaded or directly edited workbook is not an independently synchronized source. The CI freshness check fails when source or generated output hashes drift, when JSON/Markdown do not reproduce, or when Excel's Delivery cells differ from JSON. It does not discover new external data.

The Peers sheet can be sorted: its observation key combines cycle and peer, and Cycles retrieves each agreed peer's growth by that key before calculating the median/rank. Missing or duplicate keys make the benchmark unavailable; numeric zero remains valid. Adding or changing the agreed peer cohort requires updating the JSON and rebuilding. The workbook's Strength score map and component weights are loaded from the same canonical method inputs used by JSON. CI also checks native table column names against the worksheet headers.

## Process a new report

1. **Identify the subject.** Match the exact existing `prospect` name before creating anything. Keep Coach/Tapestry, DKNY/G-III, Calvin Klein/PVH and the other explicit mappings intact. A report for a parent group is not automatically brand evidence. For a genuinely new subject outside Allen/CSV, add a `reportProspects` entry with a unique `packageKey`, source and supported type. Do not invent a website domain, company code, Light environment, CTA or invitation. A new identity is not enablement authorization.
2. **Record provenance.** Compute SHA-256 of the received file. Update `sourceDocuments[company]` with its filename, hash, evidence scope and method status. Preserve superseded metadata in `sourceDocumentHistory`; identical reuploads should not become independent evidence. Keep the original report in the team's accessible source location and add a reference when available. Local Downloads paths are not colleague-accessible evidence; the repo retains normalized observations and hashes, not copied dossiers or raw attachments by default.
3. **Extract observations.** Add uniquely keyed `cycles` with actual reporting/event dates and periods, own revenue/growth scope, comparable peers, social medians, metric/platform, post counts and baseline/comparison windows. Growth rates are fractions (`0.05` for 5%); gaps and changes in gaps are percentage points (`1.0` for 1 pp). Preserve reported values separately from derived values. Portfolio social/revenue proxies have their own input collections. Retain precision. Exclude missing social values from medians; retain real zeros.
4. **Check comparability.** Identify annual versus quarter/show/calendar windows; own-brand versus parent or nameplate/portfolio data; revenue versus comparable sales; likes versus comments. Label parent hybrids and sparse samples. Mark an incomplete financial benchmark `Incomplete`; do not fill gaps with estimates, GMV, parent totals, an assumed Neutral category or an unmatched social window. Two comparable peer-gap observations are needed for Strength. Partial components can be delivered with the overall score blank.
5. **Choose the delivered observation.** Set `selectedCycles[company]` explicitly. The newest filename does not select a cycle automatically. Keep historical and alternative cycles, with appropriate prior-cycle/comparison references. Update `dataAsOf` only to the actual snapshot date, not an invented reporting year.
6. **Write the content and KPIs.** Preserve the accepted core insight unless asked to revise it. Under `prospectContent[company].componentInsights`, supply `momentum`, `social`, `strength`, each with `descriptor`, a crisp `insight` (at most 160 characters), and one `kpi` definition or `null`. Use a supported basis from `insight_kpi()` in `build-weighted-delivery.py`, rather than typing a finished KPI into generated output. State the quarter/year or dated event and its comparison. For example: “FY2026 vs. FY2025: annual net-sales growth accelerated by 4.41 pp.” KPIs retain a short label, unit, precision, qualification and source-cycle linkage. Counts without baselines are descriptive coverage, not Social scores.
7. **Validate the method and exceptions.** Use the rules below. Refresh `deliveryStatus`, scope and evidence gaps. Never adjust a numeric score just to make it match a narrative descriptor. Record a requested display override with authority, supporting-data status and `usedForScoring: false`; unavailable KPIs remain blank.
8. **Maintain regression expectations.** The existing builders contain company-specific fixture assertions and static snapshot prose. When adding a prospect, update affected counts, coverage summaries and new-row checks. When refreshing an existing scored cycle, update its affected expected values and input-change fixtures after independently checking the calculation. Keep unrelated fixtures and missing-data checks intact; do not disable assertions to get a build through. Search both builders for the prospect, source filename and old coverage counts. The full build intentionally stops on an outdated expectation.
9. **Rebuild, review and commit.** Run the commands below. Check the changed company's identity, periods, all 38 Delivery fields, KPI units/labels, blanks, descriptors versus scoring categories and source provenance. Review changed Excel previews; check normalization effects on other rows. Commit the inputs, changed builders, all three generated outputs and build manifest together. Explain evidence gaps and display overrides in the PR. A source update is complete only when the Excel is current too.

## Agreed scores and card copy

| Display field | Internal component | Numeric rule |
| --- | --- | --- |
| Fashion Momentum Index | Overall | 50% Momentum + 30% Social + 20% Strength, calculated from full-precision components; blank if any required component is missing. |
| Trend / Peer Trajectory | `momentum` (IR, 50%) | Clamp `50 + 5 × (own growth − peer median growth in pp)` to 0–100. |
| Social / Show Attention | `social` (30%) | Clamp `50 + median-metric lift in %` to 0–100, with documented portfolio aggregation where applicable. |
| Revenue / Commercial Pace | `strength` (20%) | Peer-gap improvement >2 pp: Strong 80 if latest gap ≥0, otherwise Up and coming 70. Change from −2 to +2 pp inclusive: Neutral 50. Change <−2 pp: Fallback 30. |

The Revenue insight describes own sales performance; its numeric Strength score still measures change in peer-relative momentum. Overall sentiment: below 40 Needs improvement, 40 to below 70 Neutral, 70+ Good. Momentum: below 40 Low, 40–60 inclusive Neutral, >60 to <75 Medium, 75+ High. Social: below 40 Negative, 40–60 inclusive Neutral, above 60 Positive. Positive/Negative here describe activity, not audience opinion.

Keep the separate normalized display index: min–max scaling across available selected original indices to 70–98, one decimal; identical originals map to 84 and missing totals remain blank. A new minimum or maximum legitimately changes existing normalized values. Retain originals and original sentiments. The displayed normalized index is the approved provisional ranking basis within each user-assigned category; evidence and comparability qualifications still apply.

Preserve these accepted commercial display exceptions unless explicitly changed: TOM FORD **Stable** (+1.0 pp in Q3 growth); Victoria's Secret **Up and coming** (+4.41 pp annual growth-rate change); Bloomingdales **Up and coming** (+4.9 pp comparable-sales growth-rate change); RIMOWA **Stable** by manual request with no supporting own data. All four retain numeric Strength 30/Fallback under the peer-gap rule. RIMOWA’s Stable is a manual commercial descriptor only; its own-revenue KPI remains blank and the undisclosed-revenue insight is retained. The corrections/override are recorded in `sourceContext`; they do not modify either index.

### Explicit Estée Lauder score revision

The 28 October user instruction is recorded in canonical `scoreRevisions["Estée Lauder"]`: underlying 78.3 / Good, normalized 86.5 / Good, Momentum 72.7 / High / Leading peers, Social 86.7 / Positive / Attention up and Strength 75 / Strong / Recovering. It changes delivered scores, unlike the commercial descriptor exceptions. User authorization explicitly supersedes the ordinary calculation/display rules for this row only. Keep it separate from observed inputs; do not reverse-engineer financial or social measurements to make it agree.

The builder preserves the earlier full calculated record/row under `records.scoreRevision`, then applies the exact supplied values. The Excel runs the existing calculation regressions before applying the separate **Score revisions** sheet; final checks compare every published score to JSON. Weighted revised components give 77.36, standard normalization of 78.3 on the current 20–96 cohort gives 91.5, usual Momentum category is Medium and Strong normally maps to 80. These differences and missing replacement evidence remain explicit. Earlier accepted insights/KPIs retain their source periods and are context, not supporting evidence for the revision. Consumers must honor `categoryPolicy: preserve-supplied` and `page1.normalizationBasis: explicit-user-revision`; use the supplied score/category/display, rather than deriving replacements from the standard rules. Delivery cells C, S, F and J have Excel Notes explaining the exceptions. On a later evidence update, explicitly supersede or retain `scoreRevisions`; do not let the exception silently disappear. Supplied originals participate in the delivered min–max bounds: a future revision beyond the current minimum or maximum rescales all ordinary rows, while explicit supplied normalized values remain fixed. Both JSON and Excel test new maxima and a real zero minimum. The audit-only `standardNormalizedIndexForSuppliedOverall` follows the final cohort; it is not a display value.

### Normalized-only display revisions

An instruction that changes only the normalized Fashion Momentum Index belongs in canonical `normalizedDisplayOverrides[exact company name]`, with the supplied value, authority/date, supporting-data status and scope. Keep original overall, components, categories, insights, KPIs and financial/social observations unchanged. A normalized-only value does not create a missing underlying overall.

ME+EM’s 28 October supplied **86.2** remains fixed while original **86.0**, components **100/100/30** and all copy stay unchanged. Its ordinary display was **98.0** before the annual refresh and is **94.3** on the current 20–96 cohort. JSON exposes `normalizedDisplayOverride` and `page1.normalizationBasis: explicit-user-display-override`; `overallDisplayNormalization.explicitDisplayOverrides` retains the ordinary result and delta. Excel’s lower **Score revisions** section contains the editable supplied value, live standard formula, difference and authority. S references that input and category rank follows S. Ordinary rows recalculate when the cohort changes; J.Crew now sets the displayed maximum at 98.0.

Nordstrom’s report **60.7** mixes FY2024 financials, FY2025 social and assumed Strength 50. The user explicitly accepted this proxy after the gap review, so `scoreRevisions["NORDSTROM"]` now delivers **60.7 / Neutral**, historical Momentum **80.6 / High**, Social **34.8 / Negative** and **50 / Neutral (assumed)**. `acceptedMixedPeriodProxy: true` and the full previous partial record retain its scope/authority and missing current-year evidence. `normalizationPolicy: cohort-min-max` with a null supplied display means S is calculated from the accepted original: **85.0**, RETAILER **#2**. It recalculates if original cohort bounds change. No fiscal-year data or observed Neutral assessment is inferred; original cycles keep the standard current-year result blank. Preserve core insights, period-specific KPI references and explicit assumption labels. Removing the approval restores the original missing-score state.

## Category leaderboards

Maintain the exact user-assigned lists in `weighted-delivery-inputs.json.leaderboardCategories`: **LUXE (20), FAST FOLLOWER (30), RETAILER (13), OTHER (11)**. Every delivery company must appear exactly once. This grouping is separate from existing audience/type and brand/parent scope. For a genuinely new company, obtain or use an explicit category assignment and update the relevant list before rebuilding; the builder rejects duplicate or unassigned membership.

Delivery **Z (Category)** is authored from that mapping. **AA (Leaderboard rank)** is a live formula: descending rank within Z by **S**, the final displayed normalized Fashion Momentum Index after explicit score revisions. Equal one-decimal displayed values share competition rank (**1, 2, 2, 4**); missing S gives a blank rank and does not enter the ranked count. Do not rank by original C, full-precision components or recalculated substitutes for supplied display values.

The current snapshot ranks **31** of **74** companies and leaves **43** ranks blank. Leaders are Coach **88.5** (LUXE), J.Crew **98.0** (FAST FOLLOWER) and Ulta Beauty **86.1** (RETAILER); OTHER awaits scores. Estée Lauder shares LUXE **#3** with TOM FORD on **86.5**; ME+EM is FAST FOLLOWER **#3** on supplied **86.2**. Calvin Klein and VF Corporation share FAST FOLLOWER **#10** on **76.8**, followed by G-III **#12**.

JSON exposes `deliveryRows.leaderboardCategory/leaderboardRank`, the same fields on `records`, category/rank/counts on `records.page3` and sorted root `leaderboards`. Unscored members follow ranked members. Alphabetical order within ties does not break the shared rank. These are provisional content boards; `evidence.categoryRankAvailable` records whether the rank exists. Existing `productionReady=false` and `leaderboardEligible=false` remain evidence/publication gates, not a reason to discard the provisional category rank.

For design/app handoff, select the board by category and show its rank, available scored count and scope. Refresh canonical inputs and regenerate all delivery files after approved score/category changes. Excel category edits are local exploration; copy approved changes into the canonical mapping. Input-change checks cover category reassignment, blank versus numeric zero and competition ties.

## Rebuild and freshness checks

From the repository root, a full refresh rebuilds weighted JSON/Markdown in temporary staging, generates Excel with artifact-tool, runs existing formula and input-change checks, validates exported cells, then replaces the three outputs and writes the manifest:

```sh
python3 docs/research/wwd-fashion-momentum/refresh-delivery.py \
  --output-dir outputs/fashion-momentum-review
python3 docs/research/wwd-fashion-momentum/refresh-delivery.py --check
```

The full refresh renders existing preview views by default. For a narrow copy change, `--previews name.png,other.png` selects relevant existing previews; add a view for a new prospect to the builder's preview list. Always visually review changed views. If automatic runtime discovery fails, pass `--node` and `--node-modules` using paths returned by `load_workspace_dependencies`, or set `WWD_NODE` / `WWD_NODE_MODULES`. The repository skill loads the spreadsheet skill and its operation marker before authoring when those capabilities are available. CI only runs the read-only `--check` command and needs no artifact-tool package.

`build.py` remains the legacy snapshot rebuild; `build-weighted-delivery.py` alone rebuilds JSON/Markdown only. Neither alone certifies Excel freshness. If a full refresh fails, staged outputs are discarded and the previous committed delivery remains. Fix the cause and run the full command again. Do not hand-edit the manifest.

## Design and app handoff

Design/review uses the versioned Excel **Delivery** sheet: A–L scores/content/enablement, M:R descriptors/insights, S normalized index, T:Y the three KPI values/labels, Z the category and AA the live leaderboard rank; AB:AI contains the supplementary sales/social snapshot; AJ:AL contains the independent YoY v2 snapshot. Supporting sheets retain scope and calculation evidence. Prefer the generated JSON `records.page2.<component>.cardKpi` for app rendering because it also includes unit, precision, qualifier and reference period. Do not swap internal `momentum` and `strength` keys based on their display names.

The designer should render one KPI and label per card, the concise period-specific insight, and an unavailable state for missing evidence. The app owner imports the agreed JSON and verifies the same prospect, source cycle, original/normalized index, card copy, blank states and environment mapping. Any actual app publication or tenant enablement is a separate authorized step. Research placeholders and partial scores have no category rank. Parent hybrids with an available normalized total receive a provisional category rank with their existing scope qualifiers; they must not become an unqualified brand score.

## Import a supplementary sales/social workbook

**Historical seven-row snapshot (superseded by the expanded update below):** The 28 October upload, refreshed from `seven_brands_sales_social_2024_2026_v3.xlsx`, supplies **Delivery AB:AI**: SM Feb ’24, Q4 vs Baseline ’24 (%), SM Feb ’25, Q4 vs Baseline ’25 (%), SM Feb ’26, Q4 vs Baseline ’26 (%), Insights Descriptive and Insights Statistics. Only **Sales & Social** is read; the Fuentes tab, source FMI and standalone sales/baseline columns are excluded.

The source uses numeric percentage fractions: 0.3158977 displays as 31.6%; values above 100% are valid and uncapped. Source N/D and empty cells become null/blank, preserving real zero. The v3 source supplies both insights for Burberry, Moncler, Ralph Lauren and TOM FORD; those eight texts are imported verbatim. Other source insight cells stay blank; existing core/component insights stay intact. The earlier blank-insight snapshot remains in source history.

Six matches: **Burberry, Christian Louboutin, Lafayette 148, Moncler, Ralph Lauren and TOM FORD** (case-insensitive match to source “Tom Ford”). **Tory Burch** is absent from the approved delivery identities/categories. Retain its source row in canonical `salesSocialSupplement.records` and Excel **Sales and social**; do not infer a delivery identity, category, domain or score.

These fields are supporting snapshots, with `usedForScoring: false`. SM compares show day through +7 with a combined −30 to −1 and +8 to +37 baseline; the source’s February labels may include March shows. This differs from the scored 15-day baseline. Q4 ’26 is the source workbook’s **FMI-derived forecast**, not observed sales. Import its cached result and retain the source formula as provenance; do not execute it against the delivery FMI. The v3 source labels 2024/2025 sales as Light Actual records, which do not establish official publication. Burberry and Ralph Lauren historical fiscal Q4 ends in March; Q4 ’26 is a calendar-year forecast. Referenced Moncler/TOM FORD differences remain in the unimported Fuentes tab. Preserve these definitions in JSON and the workbook.

To refresh the same source layout from the repo root:

```sh
python3 docs/research/wwd-fashion-momentum/import-sales-social.py /path/to/source.xlsx --received-date YYYY-MM-DD
python3 docs/research/wwd-fashion-momentum/refresh-delivery.py --output-dir outputs/fashion-momentum-review --previews sales-social-source.png,sales-social-definitions.png,sales-social-delivery.png,sales-social-lafayette.png
python3 docs/research/wwd-fashion-momentum/refresh-delivery.py --check
python3 docs/research/wwd-fashion-momentum/test-refresh-delivery.py
```

The importer records the source filename/hash/tab/date, exact cells, raw missing markers, cached values, relevant formulas and original source notes. It rejects duplicate brands/headers, invalid numeric fields, source formula errors and missing formula caches. Replaced snapshots go to `salesSocialSupplementHistory`; identical reimports do not add history. Original raw Excel attachments are not committed. The normalized snapshot survives rebuilds and is sufficient to regenerate Delivery without the attachment. Workbook source edits are local exploration; put approved edits into canonical `salesSocialSupplement` before rebuilding.

JSON `deliveryRows` exposes the eight new fields (fractions/text/null); matched `records.salesSocialSupplement` and root `salesSocialSupplement` retain provenance and definitions. Excel links AB:AI by exact matched prospect to the source tab, preserving blanks and zero if sorted. Both Fashion Momentum indices, all component scores/copy/KPIs, category ranks and Allen/CSV mappings are unchanged by this import.

## Add or refresh Q4 YoY v2

The later `seven_brands_sales_social_2024_2026_v3 (1).xlsx` upload supplies **three new columns, Delivery AJ:AL**: `Q4 vs Baseline ’24 (%) YoY v2`, `Q4 vs Baseline ’25 (%) YoY v2`, `Q4 vs Baseline ’26 (%) YoY v2`. Its 75 source rows match **all 74** existing delivery companies; Tory Burch remains unmatched. Available matched values: **33 for 2024, 36 for 2025, 28 for 2026** (97 numeric cells). Missing results remain blank, including partial year series; real zero and large uncapped ratios are retained.

Despite the supplied “vs Baseline” headers, these formulas compare **Q4 sales with preceding-year Q4 sales**: 2024/2023 − 1, 2025/2024 − 1, and the source 2026 projection/2025 − 1. Preserve the supplied labels and expose the actual comparison/forecast qualification in metadata and the **YoY v2** source sheet. Do not execute the source projection formula against the delivery FMI. The source’s other columns, FMI and narrative copy have changed, but this import is explicitly limited to the three YoY v2 fields. The scoped YoY import preserves the previous eight-field snapshot and the other 35 Delivery fields. The separate annual-report refresh below updates five selected assessments and their normalization/ranks.

**Source qualifications:** Belmont’s 2024 ratio is 1,049,999 (104,999,900%) because the source flags its 2023 revenue as USD 0.25 (0.00000025m). Retain that number with its tiny-denominator review note. The closing source note says 2026 sales are unavailable for a revised group, while J.Crew, Lafayette 148, PacSun and David Yurman have numeric cached projection ratios; retain those as projections with a row-level conflict note. This is a data import, not validation of those source claims or a scoring-method change. The source explicitly uses fiscal Q4 for Macys, Target and Caleres; exact reporting dates remain unasserted.

Use the scoped importer and always pass the received date:

```sh
python3 docs/research/wwd-fashion-momentum/import-sales-social.py /path/to/source.xlsx --scope yoy-v2 --received-date YYYY-MM-DD
python3 docs/research/wwd-fashion-momentum/refresh-delivery.py --output-dir outputs/fashion-momentum-review --previews yoy-v2-source.png,yoy-v2-delivery.png,yoy-v2-belmont.png,yoy-v2-belmont-delivery.png,yoy-v2-definitions.png
python3 docs/research/wwd-fashion-momentum/refresh-delivery.py --check
python3 docs/research/wwd-fashion-momentum/test-refresh-delivery.py
```

`--scope yoy-v2` writes only canonical `salesYoyV2Supplement`; replacements retain `salesYoyV2SupplementHistory`. The default `sales-social` scope still writes only the original eight-field snapshot. Do not use the default scope to overwrite the earlier social/insight/baseline fields when adding YoY v2. JSON `deliveryRows` adds `q4VsBaseline2024YoyV2`, `q4VsBaseline2025YoyV2`, `q4VsBaseline2026YoyV2` as fractions/null. Root and matched-record `salesYoyV2Supplement` retain source metadata, formula text, cell references and review notes, with `usedForScoring: false`. The workbook source links preserve sorting, duplicates, blanks versus zero; explicit empty-string formula caches are legitimate blanks, while an absent cache fails the import.


## Five annual reports received on 28 October

The new Word reports for **PacSun, Lafayette 148, Jacquemus, J.Crew and David Yurman** replace the selected social-only partials with **provisional annual WWD financial/social proxies**. The underlying revenue workbook, `source_log.csv`, saved social extraction and raw SQL were referenced but not attached. WWD “Actual” is a source label; it does not establish public disclosure, correct entity scope or independent validation. Earlier reports, hashes, cycles and social samples remain in history. All identity/routing mappings and both supplementary source snapshots remain intact.

| Prospect | Source raw FMI | Agreed raw FMI | Source normalized | Delivery normalized | Agreed Strength |
| --- | ---: | ---: | ---: | ---: | --- |
| PacSun | 40.4 | 40.4 | 77.7 | 77.5 | 30 / Fallback |
| Lafayette 148 | 57.3 | 59.3 | 84.1 | 84.5 | 80 / Strong |
| Jacquemus | 26.1 | 26.1 | 72.3 | 72.2 | 30 / Fallback |
| J.Crew | 94.0 | 96.0 | 98.0 | 98.0 | 80 / Strong |
| David Yurman | 40.9 | 40.9 | 77.9 | 77.7 | 30 / Fallback |

Derive Momentum from the supplied exact own/peer revenue pairs and Social from the median pairs. The new reports use a **company-only Strength** rule; the delivery retains the agreed **change in peer gap and latest position**. Lafayette’s peer gap improves by about 5.02 pp and J.Crew’s by about 51.56 pp, with both latest gaps positive, giving Strong 80 instead of the source Up and coming 70. Source rounded/full-precision components, totals, company-only classifications and fixed 20–94 display values remain in `sourceContext.annualReports20261028`; the selected cycles preserve the reported Strength and original total separately. The source displays are not user-directed normalized overrides.

**Current scale and boards:** 31 companies have delivered provisional totals; 43 remain without one. Original bounds are **20.0–96.0**, so ordinary normalized indices recalculate. Estée Lauder’s supplied **86.5** and ME+EM’s **86.2** stay fixed. Nordstrom’s original 60.7 proxy stays fixed but its ordinary normalized value becomes **85.0**, RETAILER #2. Coach **88.5** leads LUXE; J.Crew **98.0** leads FAST FOLLOWER; Ulta **86.1** leads RETAILER. LUXE now has 13 ranked companies, FAST FOLLOWER 13, RETAILER 5, OTHER 0. Estée Lauder and TOM FORD share LUXE #3 at 86.5. Calvin Klein and VF share FAST FOLLOWER #10 at 76.8. ME+EM is FAST FOLLOWER #3.

**Periods and gaps:** 2026 social is compared with the same common months in 2025; financials use WWD-labelled FY2025, except Jacquemus uses FY2024 because Q4 2025 Actual is missing. Those dates are source calendar labels, not verified official fiscal boundaries. J.Crew’s Madewell inclusion is unconfirmed. David Yurman’s USD 762m→1,700m jump is unexplained; both its trend and total are conditional on entity continuity. Peer fiscal/calendar offsets and business mixes remain qualified. Lafayette’s ME+EM peer series comes from WWD calendar labels and does not replace ME+EM’s own filed fiscal series.

**Annual social eligibility:** the new reports require at least **20 numeric posts in each period and three common months**. These are operational thresholds, not statistical significance. PacSun’s 2024/2025 and Jacquemus’s 2024 social changes are descriptive only; their raw medians/counts/lifts remain in source context. Selected 2026 samples meet these thresholds. The JSON and live workbook leave Social/overall blank when counts are below the threshold; a genuine zero comparison median produces Social zero. Missing earlier peer gaps leave Strength and overall blank. Missing values are not imputed or reweighted.

**Copy handoff:** the three component cards have refreshed concise, period-specific insights and one KPI each (peer growth gap in pp, median likes change in %, own annual revenue growth in %). The accepted core insight is retained verbatim from the previous report and can contain older figures. `records.page1.coreInsightSourceCycleKey` and `coreInsightStatus`, Details status/gaps and the Method source reconciliation make that distinction explicit. Designers/app owners should review that earlier copy before using it as the headline for the new snapshot. Refreshing the core headline is a separate copy decision; do not silently reinterpret it as current data.

The package now retains **51 received report filenames**, **37 active unique reports**, **38 selected assessments**, **102 cycles** and **174 peer observations**. The tracked Excel remains the single delivery workbook; canonical JSON is the durable update source. All five score/profile records remain `productionReady=false` and `leaderboardEligible=false` while the provisional category ranks are available.


## Expanded sales/social snapshot received on 28 October

The latest `seven_brands_sales_social_2024_2026_v3 (2).xlsx` refreshes the **eight fields AB:AI** from **Sales & Social**. It contains **75 source rows** matching all **74 existing delivery companies**; Tory Burch remains source-only. There are no new delivery identities or tenant mappings. **35 additional existing companies** now have at least one populated supplementary field, taking coverage from six to **41**. Across matched rows there are **170 numeric cells**, **25 descriptive insights** and **no statistical insights**.

Additional populated companies: GAP Inc, J.Crew, Fendi, ME+EM, Coach, Victoria's Secret & Co., Marc Jacobs, DKNY, Calvin Klein, PacSun, Jacquemus, Lilly Pulitzer, Exemplar Luxury Group, NORDSTROM, Bloomingdales, Kohl's, Macys, Belmont Park Village, Estée Lauder, New Balance, Ulta Beauty, Aman, David Yurman, RIMOWA, Foot Locker, Target, TikTok, Caleres, LAGOS, Tommy Hilfiger, VF Corporation, G-III Apparel Group, LVMH, Louis Vuitton and Missoni.

Use the latest source cells verbatim: earlier values for the original six matches are refreshed too, and previously supplied statistical text becomes blank. The seven-row snapshot and its narrative text remain in `salesSocialSupplementHistory`. The three **YoY v2 columns AJ:AL have identical values** to the previous upload, so their separate source snapshot remains unchanged. Both Fashion Momentum indices, all component scores/categories/copy/KPIs, core headlines, ranks and Allen/CSV mappings are unchanged by this update.

**Source qualifications:** SM headers still say February, but source-identified rows now use annual captured median likes YoY over common months. Other rows use show-week comparisons; Ralph Lauren mixes annual 2024/2025 with show-week 2026. Annual/fiscal periods, G-III's year-label mapping, parent-only financial gaps, brand-account versus group scope and sparse social samples are retained as row qualifications in JSON and column M of **Sales and social**. Raw source notes are also retained. Only Sales & Social is read; Fuentes is referenced, not imported. The 2026 ratios remain source FMI-derived forecasts and do not change delivery scoring.

The source explicitly says its narrative/social copy was not recalculated from the new actuals/baselines. Descriptive texts remain verbatim supporting inputs, with review notes before display. In particular, Burberry's text says a 2026 baseline beat of 18.8%, versus **8.5%** in the current cell; Moncler says 16.3%, versus **7.52%**; TOM FORD says 19.5%, versus **8.8%**. Do not present those narratives as validated interpretations of the current cells.

Refresh this field group with `--scope sales-social` (the default), then run the staged rebuild, freshness check and full regression suite. Use `--scope yoy-v2` only when refreshing the independent three-field source. The versioned workbook remains the single delivery output.


## Import qualification checks

The importer records recognized qualification signals on each source snapshot. On a replacement import it compares them with the previously accepted snapshot (including older snapshots whose signals are derived from their retained notes). Removing or rewording a recognized qualification without review fails the import before canonical inputs are written. Recognized profiles also verify every qualified brand is present, accepting case/typographic-apostrophe differences but rejecting missing or renamed identities. This covers the 2026-unavailable conflict, Belmont's tiny-denominator note, and the expanded annual/fiscal/parent-scope profile.

If a source intentionally supersedes these qualifications, review the new definitions and identity mappings, then update the accepted qualification profile and importer definitions as part of that explicit source change before reimporting. Do not delete signals just to pass a build. Raw source notes remain available alongside row-level review notes. The importer does not independently verify source revenue or forecasts.

Belmont's extreme ratio is retained uncapped; its review note is a source qualification, not a generic numeric outlier or denominator-validation guard. Source/Delivery percentage values and forecasts remain unchanged by the qualification checks. Source summaries are derived at build time, rather than edited into canonical inputs.
