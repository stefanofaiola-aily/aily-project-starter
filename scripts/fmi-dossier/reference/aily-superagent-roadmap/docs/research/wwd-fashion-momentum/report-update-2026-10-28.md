# Report update — 28 October 2026

Ten supplied reports refresh the canonical delivery inputs, JSON, Markdown and versioned Excel. The agreed 50/30/20 peer-relative method and separate 70–98 display normalization are unchanged. Report claims and linked external evidence remain provisional; no live app/data refresh or customer publication is implied.

## Selected delivery results

| Subject | Previous original | Current original | Normalized 70–98 | Delivery scope / gap |
| --- | ---: | ---: | ---: | --- |
| Belmont Park Village | Unavailable | Unavailable | Unavailable | Coverage/operating context only. Q4 2025 vs. Q3 monthly footfall >100%; no village revenue or social baseline. |
| Ulta Beauty | Unavailable | 63.6 | 88.5 | Complete provisional own-unit result with Matas/Adore replacement peers. |
| RIMOWA | 46.3 | 46.3 | 81.2 | LVMH segment hybrid. User Stable commercial descriptor and blank own-revenue KPI retained. |
| Missoni | Unavailable | Unavailable | Unavailable | Social 47.9 only. Conflicting 2025 revenue prevents standard financial/overall scoring. |
| Marc Jacobs | 31.4 | 20.0 | 70.0 | Revised LVMH whole-group hybrid; prior segment 31.4 retained as a historical alternative. |
| LVMH | Unavailable | 32.6 | 75.3 | Whole-group result with full-calendar-year corporate social. Separate report-only identity. |
| Louis Vuitton | Unavailable | 31.5 | 74.9 | Brand social / LVMH group hybrid; no standalone brand revenue. |
| J.Crew | Unavailable | Unavailable | Unavailable | Direct social-only result. Optional unrelated Gap analogue remains supporting context. |
| Five Below | Unavailable | Unavailable | Unavailable | Momentum 100 and agreed Strength 80; no social input or overall. |
| DKNY | 42.3 | 42.3 | 79.5 | Existing G-III parent/comment hybrid unchanged; standalone brand finances absent. |

## Method differences retained as source context

- Ulta source 61.6 uses own-growth Strength 70. The agreed peer-gap improvement (+8.8820 pp, latest +5.1383 pp) gives Strong 80 and overall 63.6. Prior company-only 73.1/raw 73.0 remain tied to the earlier incomplete cycle.
- Five Below source Strength 70 uses own-growth acceleration. The agreed improving positive peer gap gives Strong 80. Missing Social prevents an overall; weights are not redistributed.
- Louis Vuitton source 23.5 uses LVMH own-growth Strength 30. The agreed improving negative group peer gap gives Up and coming 70 and hybrid 31.5. No group revenue is attributed to the brand.
- LVMH source percentile 28 and five-month capped 27.1 use a different scale/window. Full-year capped 32.6 is selected. Marc Jacobs source percentile 25 is retained but capped 20.0 is delivered.
- Missoni source conditional 30.2 and company-only Fallback 30 remain unselected because WWD 2025 sales 125m conflict with 130m/+5% and fiscal/consolidation scope is unresolved. Its matched 25 June–30 December social observation remains available.
- J.Crew source percentile 26.5 / capped 30.5 uses external Gap financials; sensitivities 39–40 and old 2018/2019 actuals do not establish current J.Crew revenue. The selected direct total remains blank.
- RIMOWA’s corrected source own-segment change −5.38 pp and agreed peer-gap change −2.05575 pp both produce Fallback 30. User-directed Stable is a separate unsupported own-commercial display override, not a numeric correction. The displayed original remains 46.3.

## Additional Estée Lauder revision

The user subsequently supplied an exact revision: normalized **86.5 / Good**, underlying **78.3 / Good**, Momentum **72.7 / High · Leading peers**, Social **86.7 / Positive · Attention up**, Strength **75.0 / Strong · Recovering**. Delivery applies these values without inferring new observations. The weighted components give **77.36 → 77.4**; the requested underlying total differs by **0.94**. The standard display formula would give **94.7**, Momentum would be Medium, and Strong normally maps to 80. The user’s exact values/categories are retained as a named exception.

Excel **Score revisions** and JSON `records.scoreRevision` expose the authority, missing supporting-data status, full earlier calculated record (81.3), earlier delivery row and reconciliation. Existing core/component insights and KPIs remain earlier-report context. Their reference periods and observations were not refreshed; JSON marks the KPI qualifier. All other original and normalized values remain unchanged by this revision, since the available minimum and maximum stay 20.0 and 86.0. Rebuilds preserve the exception until explicitly superseded.

## Identity and evidence

LVMH, Louis Vuitton and Missoni are separate report additions without inferred domain, company code, Light environment, invitation or CTA. The existing LVMH CSV pairing stays on Fendi. The Missoni company report is not assigned to Global Luxury Retail Group DBA Missoni, whose CSV identity describes an unverified distributor scope. Five Below uses its existing exact CSV pairing. All 70 approved company/code/email-domain pairings and 26 Light mappings are unchanged.

Previous report metadata and hashes are retained in `sourceDocumentHistory`, and historical cycles keep their original source filename/hash. New-cycle inputs preserve exact revenues, periods, matched social windows and source locators. Full raw SQL/post records and independent external verification remain missing. Ulta and Marc Jacobs core insights received minimal factual corrections because replacement evidence made their old unavailable-peer/near-peer claims obsolete; prior wording is retained in `sourceContext`.

## Designer and app handoff

Use the **Delivery** sheet for scores, original sentiment, one core insight, three short component insights and KPI value/label. Column C is the original; column S is the separate normalized display. Never derive sentiment from column S. Use `records.page2.<component>.cardKpi` for units, precision, comparison/reference period and qualifiers. Missing evidence stays unavailable. Belmont’s >100% KPI is a reported lower bound for monthly footfall, not revenue growth. Parent hybrids must retain their scope labels.

The original range is now 20.0–86.0 across 25 available totals, so existing normalized values rescale. Except newly evidenced Ulta, revised Marc Jacobs and the subsequent supplied Estée Lauder revision, previous displayed originals and sentiments remain unchanged. There are 74 content rows, 38 assessments, 25 scoped totals (19 own-unit and 6 hybrids; 24 calculated and one supplied revision), 11 partials and 2 coverage-only assessments. 37 active unique report filenames and 46 received filenames are recorded; repeated files do not become independent evidence.

Excel is versioned in the repository. Update canonical JSON inputs and run `refresh-delivery.py`; commit inputs, affected builders, generated JSON/Markdown/Excel and `delivery-build.json` together. CI checks freshness but does not collect new external evidence.

## Approved category leaderboards

The delivery adds **Z: Category** and **AA: Leaderboard rank**, expanding it to **27 fields**. All 74 exact company names are assigned once to the user-approved LUXE (20), FAST FOLLOWER (30), RETAILER (13) and OTHER (11) groups. This is a content grouping; existing identities, audience types, environment mappings and evidence scope remain unchanged.

Ranks use **S**, the displayed normalized Fashion Momentum Index, descending within category. Ties share competition ranks (1, 2, 2, 4); missing scores keep their category and blank rank. **26 companies are ranked; 48 are unranked.** Coach 91.3 leads LUXE (10 scored), New Balance 89.5 leads FAST FOLLOWER (11 scored), and Ulta Beauty 88.5 leads RETAILER (5 scored). OTHER has no scored companies. Estée Lauder remains LUXE #5 on the explicitly supplied 86.5. Calvin Klein and VF Corporation share FAST FOLLOWER #8 (77.8); G-III follows at #10.

The Excel formulas respond to category/score changes. JSON exposes row fields, matching `records.page3` and sorted root `leaderboards`. Boards remain provisional with the existing evidence/publication gates retained. Original scores, normalized displays, insights and KPIs are unchanged by this addition. The [update guide](prospect-update-guide.md#category-leaderboards) defines canonical mapping ownership and app rendering.

## ME+EM normalized-only revision and Nordstrom review

The subsequent user instruction sets ME+EM’s normalized Fashion Momentum Index to **86.2** instead of ordinary **98.0**. Original **86.0 / Good**, component scores **100 / 100 / 30**, categories, insights, KPIs and observations remain unchanged. `normalizedDisplayOverrides` owns this display-only value with authority/date; JSON and the lower **Score revisions** section retain the ordinary normalization and difference (**−11.8**). ME+EM becomes FAST FOLLOWER **#4**, with New Balance **89.5** now #1. Only ME+EM’s displayed index and affected FAST FOLLOWER ranks change; the 25/49 coverage counts and all other display values remain unchanged.

Nordstrom’s uploaded report does contain indicative **60.7**. Its formula uses **FY2024 financial Momentum 80.6079**, **FY2025 Social 34.8101**, and an **assumed Strength 50**. The report explicitly calls this a rough mixed-period proxy, with FY2025 standalone annual net sales unverified after the May 2025 acquisition. The saved `sourceContext.nordstromMixedPeriod` and Method section already retain 60.7, its arithmetic and assumptions. Standard current-year Momentum, observed Strength, overall, normalized display and category rank remain blank. Completing the standard score requires verified FY2025 annual net sales and a second eligible peer-gap observation for measured Strength. No Nordstrom figures or methodology are changed by this review.

## Validation

Full artifact-tool staged rebuild, independent exact-input arithmetic, all seventeen freshness/failure/ranking tests, inherited and updated workbook input-change regressions, all 27 Delivery-field/export/cache comparisons, native table header checks, formula-error scan and changed-view visual review passed, including displayed-score ranking, competition ties, missing/zero handling and live category edits. Original mapping preservation and source-method separation were independently checked.

## Received reports

- Belmont Park Village: `belmont_park_village_momentum_score (2).md` — SHA-256 `b33e6bddea50b06009ac7d19ad951f97df903869fb34a013aa30d64ac4b34545`
- Ulta Beauty: `ulta_beauty_fiscal_year_comparison (2).md` — SHA-256 `3647f318da5991652d151ffb54a62cb3b933cd9d1bc045466dd3284fb843f3d7`
- RIMOWA: `rimowa_fy_proxy_momentum_score (1).md` — SHA-256 `e179b14e8d03a3762e504d7ab155fd9320970da0500ea5df6a67ae7ef1f53058`
- Missoni: `missoni_2024_2025_report.md` — SHA-256 `052a6531c377ee89cb00bde79ae0e58a50a84a0e5c5430032f764ab04da54c02`
- Marc Jacobs: `marc_jacobs_momentum_score (1).md` — SHA-256 `44a080a269305fc7bf690714753e11b80c8a8138a654d814f224e6b0f99ecd69`
- LVMH: `lvmh_momentum_score.md` — SHA-256 `6343f0767024b79ae773883015aafa84cc91f89bb9869d429fcf9cfef7ae8e4d`
- Louis Vuitton: `louis_vuitton_lvmh_group_proxy.md` — SHA-256 `b0e6e6669cb0c97f8c438b40b684fa271bd28730e857297d97759dbf8f282771`
- J.Crew: `jcrew_momentum_score (1).md` — SHA-256 `e4f8ed1e360d63c0df8db3250a49c649d92ca5dc9ec02fe0919385340dff3571`
- Five Below: `five_below_momentum_report.md` — SHA-256 `36a7ad60f661ba2439d4ac28447544750d2195e65f5da1a980263414e85d5a6c`
- DKNY: `dkny_momentum_score (1).md` — SHA-256 `6b36319fcab9388fcfdfd16a56d89e63a2471c68bdb07c231783031486129baa`

## PR review follow-up

PR #166 feedback is addressed with Excel Notes on the supplied original/normalized values and category cells, explicit machine-readable category/normalization policies, and assertions preserving the supplied Momentum High and Strength Strong labels. Normalization now takes every delivered original into account after revisions: a new maximum or real-zero minimum rescales ordinary rows while explicit display values stay fixed. JSON and workbook regressions cover both cases. The audit-only standard normalized value remains separate from Delivery. RIMOWA’s numeric 30/Fallback and manual Stable descriptor are stated explicitly in the guide. The ten active report hashes were recomputed against the original local uploads and matched; their external claims remain independently unverified.


## Subsequent approval of Nordstrom’s indicative proxy

Following the gap review, the user explicitly instructed us to use Nordstrom’s report proxy. Delivery now exposes **60.7 / Neutral**, normalized **87.3**, RETAILER **#2**; Momentum **80.6 / High** is FY2024 historical, Social **34.8 / Negative** is FY2025, and Strength **50 / Neutral** is an explicit, unobserved assumption. `scoreRevisions["NORDSTROM"]` records the approval, source, full previous partial record and arithmetic **60.74698 → 60.7**. Its null supplied normalized value plus `normalizationPolicy: cohort-min-max` means the display recalculates over the original cohort, unlike Estée Lauder’s and ME+EM’s fixed display exceptions.

There are now **26 delivered totals and 48 blanks**, with **5 ranked retailers**. Ulta stays #1; Nordstrom enters #2, Kohl’s moves to #3, Bloomingdales #4 and Foot Locker #5. No other original or normalized values change. Core insights, reference-period KPIs, Allen/CSV identities, source documents and raw calculations are retained. Current FY2025 sales and observed Strength remain missing; the original standard current-year overall stays blank in source observations. Prior statements in this update describe the pre-approval gap review.

The versioned Excel and JSON label the accepted proxy’s scope and assumed Strength. Regression checks verify the delivered values, dynamic normalization, unchanged standard gaps and restoration of the previous partial if approval is removed.
