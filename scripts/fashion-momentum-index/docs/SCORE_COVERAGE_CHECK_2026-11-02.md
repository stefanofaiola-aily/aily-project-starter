# FMI score coverage: regression and recovery

One-time check: 2 November 2026. Forecast target: **Calendar Q4 2026 (1 October–31 December)**.

## What happened

- The archived delivery had **42 scores** under `presentation / latest_available`. The saved pre-dossier input confirms those settings.
- The current input uses **`dossier / dossier`**: exact dossier financial subjects, scopes and periods, collection relevance, social windows and Trend rules. The brand list stayed familiar, but the effective inputs and eligibility rules changed.
- The simple CSV handoff did not itself remove scores. The zero-score run rejected financial rows without scope/unit/period evidence. The prior repair restored nine scores through verified issuer-table measurements.
- This check restores **17 scores**, including **11 of 31 mandatory dinner brands** and **7 of 18 explicitly invited brands**. Twenty mandatory brands still cannot be scored from the currently specified, verified inputs.
- More archived scores did not mean more verified standalone/segment measurements: that run allowed latest-quarter/group proxies and constant-scale assumptions. Restoring those assumptions silently would produce a different methodology.

| Delivery stage | Complete FMI | Mandatory dinner FMI / 31 | Explicitly invited FMI / 18 |
|---|---:|---:|---:|
| Archived presentation/latest-available run | 42 | 26 | 14 |
| After CSV simplification, before source repair | 0 | 0 | 0 |
| Before this coverage recovery | 9 | 4 | 2 |
| Fresh repaired dossier-parameter run | 17 | 11 | 7 |

The dinner file has 32 non-empty records but 31 unique brands: Michael Kors is listed twice. Invitation blanks mean unknown, not “not invited”. All 94 prospect rows remain in the delivery so missing outcomes stay visible.

## Concrete differences behind the old score count

| Brand | Archived measurement basis | Current required basis | Why this matters |
|---|---|---|---|
| Burberry | Native/latest March quarters, consolidated subject | June retail/DTC quarters for 2024, 2025, 2026 | Different channel and selling season; collection captions now explicitly selected. |
| Moncler | Native/latest June quarters | Moncler DTC October–December 2023, 2024, 2025 | Different season and scope; no Moncler Group/Stone Island substitution. |
| Coach / Kate Spade | Tapestry consolidated latest quarters | Brand-segment annual FY2024, FY2025, FY2026 | Consolidated Tapestry is not the brand revenue. Annual segment tables are now decoded. |
| Michael Kors | Capri consolidated latest quarters | Michael Kors segment annual FY2024, FY2025, FY2026 | Capri disposed of Versace. Michael Kors segment observations preserve the required brand scope. |
| Fendi / Dior | LVMH consolidated latest quarters | Explicit LVMH Fashion & Leather Goods annual proxy 2023–2025 | Group and segment totals differ. Proxy stays labelled, not standalone maison revenue. |
| Marc Jacobs | Latest parent/group quarter proxy | Explicit LVMH consolidated annual 2023–2025 proxy | Annual comparisons and original percentile normalization are different from the old quarter simulation. |
| Calvin Klein / Tommy Hilfiger | PVH group | Brand-segment discrete quarters | True brand segment observations give different IR growth. |
| Zara / Uniqlo and other incomplete dossiers | Latest parent/native-quarter assumptions | Missing financial/social period definitions must first be completed | Brand names and tickers alone cannot specify an annual comparison or collection relevance. |

Example from the archived Burberry row: `financial_scope_status=configured_subject_not_verified_standalone_scope`, `financial_unit_status=source_native_constant_scale_assumption_no_conversion`, and `social_selection_basis=document_dates_with_window_proxy_not_reviewed_collection_relevance`. Those are assumptions, not verified dossier-matching evidence.

## Changes made once, without adding another workflow

1. Added deterministic adapters for authenticated shared issuer tables: Tapestry Coach/Kate Spade annual net sales, Capri Michael Kors annual revenue, GAP consolidated annual revenue, Abercrombie consolidated annual revenue for GAP’s approved peer comparison, and Ralph Lauren consolidated annual revenue for peers.
2. Retained native fiscal-year labels separately from shared calendar labels. Annual starts use the explicit prior-year end where available. Inferred older 52-week starts are labelled; explicit 53-week sources are retained. Equal amounts with stronger verified boundaries are preferred. Unverified quarters still cannot be summed into annual revenue.
3. Filled Burberry’s missing collection-caption pattern (`summer\s*2026|burberrysummer26`) after checking actual shared Instagram captions. Dates, numeric engagement observations and sample thresholds were not invented or overridden.
4. Set the explicit input option **`headline_method: weighted_components`**. Current raw FMI is the configured weighted sum of available IR, Social and dossier Trend components. This recovers Fendi, Marc Jacobs and LVMH, which had all three components but were blocked solely by unavailable historical percentile reference cohorts. Their output still says the historical percentile cannot be replicated. `dossier_reference` restores that gate if exact reference replication is wanted.
5. Counted verified issuer segment observations in delivery source coverage even where the brand has no ticker. This avoids showing zero financial candidates beside a valid Coach/Kate Spade/Michael Kors score. It does not import incompatible parent forecasts.
6. Re-ran the actual notebooks in order. There is still only **input JSON → extract → score → delivery**. CSVs are internal handoffs, not new human-managed inputs. No recurring dossier generation or additional audit archive was introduced.

One usable assigned peer is sufficient. Multiple usable peers use the median. The same subset is used for earlier and latest growth, and used/excluded peers are shown. A missing second peer does not invalidate the first. Parent proxies are used only where the dossier/input explicitly names the financial subject; brand-segment data is never silently replaced by a parent total.

## Fresh retrieval and forecast limitations

- Extraction time: `2026-11-02T08:43:26.542307+00:00`. Verified read-only Light and separate shared sessions; scoped, bounded SELECTs after schema discovery.
- Retrieved 15,455 prepared financial observations, including 169 decoded issuer measurements; 102,490 Instagram capture rows; 873 profile captures. Capture rows are not unique posts or eligible sample counts.
- 14 source queries are recorded in `data/extract/queries.csv`. Financial reads include Light actual/forecast, the shared consolidated view, FMP/interpolated/Perplexity sources and correction/source evidence. Social reads use the available Instagram history source and filter captures before deduplication.
- A separate bounded issuer check fetched 146 documents for candidate codes/names including Tapestry, Capri, Oxford, Chanel, Valentino and Victoria’s Secret. This relation returned Tapestry/Capri and the supported public issuer sources, but no Oxford, Chanel, Valentino or VSCO issuer bodies in the checked 2022–2026 range. This is relation/query coverage, not proof they exist nowhere in AWS.
- The score run has **38 Social components**. The 77 incomplete FMI rows retain valid individual components and source context. Native rows can exist yet fail the requested period/scope/unit tests.
- All 17 available FMI rows have both the legacy and new uplift **rates**. There are **zero compatible adjusted forecasts**: native forecast rows do not establish the required scope, unit scale and full fiscal/calendar target alignment. Historical publication vintages also remain unavailable.
- Q4 2026 remains the forecast target, not an instruction to move FMI revenue periods to Q4. These results are retrospective calculations from current source captures, not strict information-at-show-date replay.
- Cohort rescaling is dynamic: additional scores can change an existing brand’s display score and uplift rate even if its raw FMI is unchanged. The 70–98 display range yields positive uplift for every available score. Uplift is a business scenario, not validated predictive accuracy.

## Dinner priority: score comparison and remaining reason

Scores below are **raw FMI**, before cohort display rescaling. Components are shown as IR / Social / Trend. A dash means unavailable, never zero.

| Brand | Invited | Archived raw | Before repair | Repaired raw | IR / Social / Trend | Outcome / next input |
|---|---|---:|---:|---:|---|---|
| Burberry | Unknown | 46.92 | — | 46.72 | 5.43 / 100.00 / 70.00 | Recovered: collection-caption rule; retail/DTC measurements already available. |
| Moncler | Yes | 50.21 | 66.26 | 66.26 | 60.51 / 100.00 / 30.00 | FMI available; dossier periods/scopes differ from the archived latest-quarter simulation. |
| GAP Inc | Unknown | 22.30 | — | 57.59 | 27.18 / 100.00 / 70.00 | Recovered: verified annual/segment issuer tables, native fiscal labels and usable assigned peers. |
| Abercrombie & Fitch | Unknown | 25.12 | — | — | — / — / — | Incomplete financial dates or reporting scope; Social annual windows missing |
| J.Crew | Yes | 26.08 | — | — | — / 100.00 / — | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| Fendi | Yes | 59.06 | — | 47.29 | 50.41 / 53.62 / 30.00 | Recovered: current weighted headline. Historical percentile remains a separate frozen reference. |
| Hermès | Unknown | 67.15 | 62.09 | 62.09 | 100.00 / 20.30 / 30.00 | FMI available; dossier periods/scopes differ from the archived latest-quarter simulation. |
| ME+EM | Yes | — | — | — | — / 100.00 / — | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| Coach | Yes | 94.00 | — | 68.17 | 100.00 / 13.90 / 70.00 | Recovered: verified annual/segment issuer tables, native fiscal labels and usable assigned peers. |
| Michael Kors | Yes | 28.74 | — | 16.31 | 0.00 / 21.05 / 50.00 | Recovered: verified annual/segment issuer tables, native fiscal labels and usable assigned peers. |
| Victoria's Secret & Co. | Yes | 74.18 | — | — | — / — / — | Incomplete financial dates or reporting scope; No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series; Social sample below minimum usable-post count; Social baseline missing or zero |
| Marc Jacobs | Yes | 26.05 | — | 19.97 | 11.54 / 0.67 / 70.00 | Recovered: current weighted headline. Historical percentile remains a separate frozen reference. |
| Tory Burch | Yes | 74.04 | — | — | — / 55.36 / — | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Lafayette 148 | Yes | 13.96 | — | — | — / 26.52 / — | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| Lilly Pulitzer | Yes | 23.14 | — | — | — / 28.38 / — | No verified source amount matching the requested financial scope/period(s) |
| Christian Dior | Yes | 61.82 | 38.89 | 38.89 | 50.41 / 25.62 / 30.00 | FMI available; dossier periods/scopes differ from the archived latest-quarter simulation. |
| Valentino | Yes | 94.00 | — | — | — / 26.65 / — | No verified source amount matching the requested financial scope/period(s) |
| Etro | Yes | 86.00 | — | — | — / 37.21 / — | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| The Row | Unknown | — | — | — | — / 32.89 / — | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Prada | Unknown | 80.29 | 63.43 | 63.43 | 100.00 / 24.78 / 30.00 | FMI available; dossier periods/scopes differ from the archived latest-quarter simulation. |
| Chanel | Unknown | 38.39 | — | — | — / 41.07 / — | No verified source amount matching the requested financial scope/period(s) |
| Kate Spade | Yes | 64.41 | — | 6.41 | 0.00 / 1.37 / 30.00 | Recovered: verified annual/segment issuer tables, native fiscal labels and usable assigned peers. |
| Rag & Bone | Yes | — | — | — | — / — / — | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series; Social annual windows missing |
| American Eagle | Unknown | 64.04 | — | — | — / — / — | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series; Analysis route/social windows missing |
| Uniqlo | Unknown | 68.04 | — | — | — / — / — | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series; Social annual windows missing |
| Zara | Unknown | 47.16 | — | — | — / — / — | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series; Social annual windows missing |
| H&M | Unknown | 23.87 | — | — | — / — / — | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series; Social annual windows missing |
| Mango | Unknown | 24.38 | — | — | — / — / — | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series; Social annual windows missing |
| Levi's | Unknown | 72.32 | — | — | — / — / — | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series; Analysis route/social windows missing |
| Armani | Yes | — | — | — | — / — / — | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series; Analysis route/social windows missing |
| Longchamp | Yes | — | — | — | — / — / — | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series; Analysis route/social windows missing |

## Dinner data-engineering detail

For every mandatory brand: requested revenue roles, selected source amounts, social dates/samples and missing reasons. Candidate counts include duplicate/underlying observations and must not be treated as complete periods. Amounts below use the selected source currency and unit multiplier, not manually copied dossier numbers.

### Burberry

- Identity: Light `BRBY.L`; ticker `BRBY.L`; shared symbol `BRBY.L`; Instagram `burberry`. Required subject/scope: **Burberry / retail_dtc**.
- Requested revenue: oldest: Prior year Apr–Jun 2025, 2024-04-01…2024-06-30, calendar_selling_window_proxy; earlier: Apr–Jun 2025, 2025-03-30…2025-06-28, exact boundaries; latest: Apr–Jun 2026, 2026-03-29…2026-06-27, exact boundaries.
- Selected revenue: oldest: 458,000,000 GBP × 1.0, 2024-03-31…2024-06-29; denormalized.finance_specific_investor_relations; [source](https://www.burberryplc.com/content/dam/burberryplc/corporate/documents/investors/results-reports/2025/q1-fy26-results/Burberry%20Q1%20FY26%20Results%20Announcement%20July%202025.pdf.downloadasset.pdf); earlier: 433,000,000 GBP × 1.0, 2025-03-30…2025-06-28; denormalized.finance_specific_investor_relations; [source](https://www.burberryplc.com/content/dam/burberryplc/corporate/documents/investors/results-reports/2025/q1-fy26-results/Burberry%20Q1%20FY26%20Results%20Announcement%20July%202025.pdf.downloadasset.pdf); latest: 455,000,000 GBP × 1.0, 2026-03-29…2026-06-27; denormalized.finance_specific_investor_relations; [source](https://www.burberryplc.com/content/dam/burberryplc/corporate/documents/investors/results-reports/2026/q1/Burberry%20Q1%20FY27%20Trading%20Update%20Press%20Release%20.pdf.downloadasset.pdf).
- Data retrieved: **82 revenue candidates**, **16 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `show`; show `2025-09-22`; timezone `Europe/London`; current `2025-09-22/2025-09-29`; baseline `2025-09-07/2025-09-21`. Current/baseline usable scoring posts: **25 / 23**; median likes **6456.00 / 3589.00**. Portfolio members: —.
- Peers used: **Ralph Lauren**; excluded/reasons: Moncler: financial:moncler:latest:missing_verified_retail_dtc_2026-04-01_2026-06-30; missing_comparable_three_quarter_series.
- FMI missing reasons: none.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/FMI_delivery/02_Brand_reports/burberry/burberry_show_momentum_score.docx`.

### Moncler

- Identity: Light `MONC.MI`; ticker `MONC.MI`; shared symbol `MONC.MI`; Instagram `moncler`. Required subject/scope: **Moncler / retail_dtc**.
- Requested revenue: oldest: Prior year Oct–Dec 2024, 2023-10-01…2023-12-31, calendar_selling_window_proxy; earlier: Oct–Dec 2024, 2024-10-01…2024-12-31, exact boundaries; latest: Oct–Dec 2025, 2025-10-01…2025-12-31, exact boundaries.
- Selected revenue: oldest: 1,011,000,000 EUR × 1.0, 2023-10-01…2023-12-31; denormalized.finance_specific_investor_relations; [source](https://www.monclergroup.com/wp-content/uploads/2025/04/moncler-group-q1-2025-interim-management-statement-presentation.pdf); earlier: 1,071,900,000 EUR × 1.0, 2024-10-01…2024-12-31; denormalized.finance_specific_investor_relations; [source](https://www.monclergroup.com/v3/assets/blt61bda6b71f29a239/bltaef93ab3e71b90f1/6aac09f6c45acd1c4a769b81/Moncler-Group_Corporate_Presentation_FY25.pdf); latest: 1,104,200,000 EUR × 1.0, 2025-10-01…2025-12-31; denormalized.finance_specific_investor_relations; [source](https://www.monclergroup.com/v3/assets/blt61bda6b71f29a239/bltaef93ab3e71b90f1/6aac09f6c45acd1c4a769b81/Moncler-Group_Corporate_Presentation_FY25.pdf).
- Data retrieved: **111 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `show`; show `2025-03-15`; timezone `Europe/Paris`; current `2025-03-15/2025-03-22`; baseline `2025-02-28/2025-03-14`. Current/baseline usable scoring posts: **12 / 8**; median likes **17102.00 / 4487.00**. Portfolio members: —.
- Peers used: **Burberry**; excluded/reasons: Canada Goose: financial:canada-goose:oldest:missing_verified_retail_dtc_2023-10-01_2023-12-31; financial:canada-goose:earlier:missing_verified_retail_dtc_2024-09-30_2024-12-29; financial:canada-goose:latest:missing_verified_retail_dtc_2025-09-29_2025-12-28; missing_comparable_three_quarter_series.
- FMI missing reasons: none.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/FMI_delivery/02_Brand_reports/moncler/moncler_show_momentum_score.docx`.

### GAP Inc

- Identity: Light `GAP`; ticker `GAP`; shared symbol `GAP`; Instagram `gap`. Required subject/scope: **GAP Inc / consolidated**.
- Requested revenue: oldest: FY2023, —…—, native_fiscal_year; earlier: FY2024, —…—, native_fiscal_year; latest: Gap Inc FY2025 annual portfolio proxy, 2025-02-02…2026-01-31, exact boundaries.
- Selected revenue: oldest: 14,889,000,000 USD × 1.0, 2023-01-29…2024-02-03; denormalized.finance_specific_investor_relations; [source](https://s204.q4cdn.com/320226404/files/doc_news/Gap-Inc.-Reports-Fourth-Quarter-and-Fiscal-2024-Results-Provides-Fiscal-2025-Outlook-2025.pdf); earlier: 15,086,000,000 USD × 1.0, 2024-02-04…2025-02-01; denormalized.finance_specific_investor_relations; [source](https://s204.q4cdn.com/320226404/files/doc_news/Gap-Inc.-Reports-Fourth-Quarter-and-Fiscal-2024-Results-Provides-Fiscal-2025-Outlook-2025.pdf); latest: 15,366,000,000 USD × 1.0, 2025-02-02…2026-01-31; denormalized.finance_specific_investor_relations; [source](https://s204.q4cdn.com/320226404/files/doc_news/Gap-Inc--Reports-Fourth-Quarter-and-Fiscal-2025-Results-Provides-Fiscal-2026-Outlook-2026.pdf).
- Data retrieved: **58 revenue candidates**, **16 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `UTC`; current `—`; baseline `—`. Current/baseline usable scoring posts: **— / —**; median likes **— / —**. Portfolio members: Gap; Old Navy; Banana Republic.
- Peers used: **Abercrombie & Fitch**; excluded/reasons: American Eagle Outfitters: financial:american-eagle-outfitters:oldest:missing_verified_consolidated_None_None; financial:american-eagle-outfitters:earlier:missing_verified_consolidated_None_None; financial:american-eagle-outfitters:latest:missing_verified_consolidated_None_None; missing_comparable_three_quarter_series.
- FMI missing reasons: none.
- Forecast missing reason: `missing_native_quarter_revenue_ending_near_2026-12-31`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/FMI_delivery/02_Brand_reports/gap_inc/gap_inc_portfolio_momentum_score.docx`.

### Abercrombie & Fitch

- Identity: Light `ANF`; ticker `ANF`; shared symbol `ANF`; Instagram `abercrombie`. Required subject/scope: **Abercrombie brand net sales / —**.
- Requested revenue: oldest: FY2023, —…—, native_fiscal_year; earlier: FY2024, —…—, native_fiscal_year; latest: FY2025, —…—, native_fiscal_year.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **51 revenue candidates**, **16 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `UTC`; current `—`; baseline `—`. Current/baseline usable scoring posts: **— / —**; median likes **— / —**. Portfolio members: —.
- Peers used: **Gap**; excluded/reasons: American Eagle: financial:american-eagle:oldest:missing_verified_brand_segment_None_None; financial:american-eagle:earlier:missing_verified_brand_segment_None_None; financial:american-eagle:latest:missing_verified_brand_segment_None_None; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:abercrombie-fitch:oldest:missing_dossier_dates_or_scope; financial:abercrombie-fitch:earlier:missing_dossier_dates_or_scope; financial:abercrombie-fitch:latest:missing_dossier_dates_or_scope; social:missing_annual_windows; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `missing_native_quarter_revenue_ending_near_2026-12-31`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/abercrombie_and_fitch_momentum_score Incomplete.docx`.

### J.Crew

- Identity: Light `JCREW`; ticker `—`; shared symbol `JCREW`; Instagram `jcrew`. Required subject/scope: **J.Crew / dossier_labelled_company**.
- Requested revenue: oldest: FY2023, 2023-01-01…2023-12-31, exact boundaries; earlier: FY2024, 2024-01-01…2024-12-31, exact boundaries; latest: FY2025, 2025-01-01…2025-12-31, exact boundaries.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **57 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `UTC`; current `2026-01-01/2026-10-28`; baseline `2025-01-01/2025-10-28`. Current/baseline usable scoring posts: **367 / 548**; median likes **1435.00 / 928.00**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: Gap: financial:gap:oldest:missing_verified_dossier_labelled_company_2023-02-01_2024-01-31; financial:gap:earlier:missing_verified_dossier_labelled_company_2024-02-01_2025-01-31; financial:gap:latest:missing_verified_dossier_labelled_company_2025-02-01_2026-01-31; missing_comparable_three_quarter_series; PVH Corp: financial:pvh-corp:oldest:missing_verified_dossier_labelled_company_2023-02-01_2024-01-31; financial:pvh-corp:earlier:missing_verified_dossier_labelled_company_2024-02-01_2025-01-31; financial:pvh-corp:latest:missing_verified_dossier_labelled_company_2025-02-01_2026-02-01; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:j-crew:oldest:missing_verified_dossier_labelled_company_2023-01-01_2023-12-31; financial:j-crew:earlier:missing_verified_dossier_labelled_company_2024-01-01_2024-12-31; financial:j-crew:latest:missing_verified_dossier_labelled_company_2025-01-01_2025-12-31; peers:no_assigned_peer_with_comparable_three_quarter_series; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/FMI_delivery/02_Brand_reports/jcrew/j_crew_annual_momentum.docx`.

### Fendi

- Identity: Light `LVMHF`; ticker `LVMHF`; shared symbol `LVMHF`; Instagram `fendi`. Required subject/scope: **LVMH Fashion and Leather Goods / parent_segment**.
- Requested revenue: oldest: FY2023, 2023-01-01…2023-12-31, exact boundaries; earlier: FY2024, 2024-01-01…2024-12-31, exact boundaries; latest: FY2025, 2025-01-01…2025-12-31, exact boundaries.
- Selected revenue: oldest: 42,169,000,000 EUR × 1.0, 2023-01-01…2023-12-31; denormalized.finance_specific_investor_relations; [source](https://lvmh-com.cdn.prismic.io/lvmh-com/Z5kVBpbqstJ999KR_Financialdocuments-December31%2C2024.pdf); earlier: 41,060,000,000 EUR × 1.0, 2024-01-01…2024-12-31; denormalized.finance_specific_investor_relations; [source](https://lvmh-com.cdn.prismic.io/lvmh-com/aXjqHgIvOtkhB_8I_Financialdocuments-December31%2C2025.pdf); latest: 37,770,000,000 EUR × 1.0, 2025-01-01…2025-12-31; denormalized.finance_specific_investor_relations; [source](https://lvmh-com.cdn.prismic.io/lvmh-com/aXjqHgIvOtkhB_8I_Financialdocuments-December31%2C2025.pdf).
- Data retrieved: **122 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `Europe/Rome`; current `2025-01-01/2025-12-31`; baseline `2024-01-01/2024-12-31`. Current/baseline usable scoring posts: **336 / 604**; median likes **8616.00 / 8315.00**. Portfolio members: —.
- Peers used: **Gucci; Hermès**; excluded/reasons: —.
- FMI missing reasons: none.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/FMI_delivery/02_Brand_reports/fendi/fendi_momentum_score.docx`.

### Hermès

- Identity: Light `HERMES`; ticker `RMS.PA`; shared symbol `RMS.PA`; Instagram `hermes`. Required subject/scope: **Hermès / consolidated**.
- Requested revenue: oldest: FY2023, 2023-01-01…2023-12-31, exact boundaries; earlier: FY2024, 2024-01-01…2024-12-31, exact boundaries; latest: FY2025, 2025-01-01…2025-12-31, exact boundaries.
- Selected revenue: oldest: 13,427,000,000 EUR × 1.0, 2023-01-01…2023-12-31; denormalized.finance_specific_investor_relations; [source](https://assets-finance.hermes.com/s3fs-public/node/pdf_file/2025-02/1739475049/hermes_20250214_pr_2024fullyearresults_va.pdf?VersionId=qQriZY_1BlBwpp2OmhmriU1k0MRVbUjd); earlier: 15,170,000,000 EUR × 1.0, 2024-01-01…2024-12-31; denormalized.finance_specific_investor_relations; [source](https://assets-finance.hermes.com/s3fs-public/node/pdf_file/2025-02/1739475049/hermes_20250214_pr_2024fullyearresults_va.pdf?VersionId=qQriZY_1BlBwpp2OmhmriU1k0MRVbUjd); latest: 16,002,000,000 EUR × 1.0, 2025-01-01…2025-12-31; denormalized.finance_specific_investor_relations; [source](https://assets-finance.hermes.com/s3fs-public/node/pdf_file/2026-02/1770842738/hermes_20260212_pr_2025fullyearresults_va.pdf?VersionId=b_gXeCpcnuB3ftYcPgTb8IVxf8wfnw0k).
- Data retrieved: **74 revenue candidates**, **0 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `Europe/Paris`; current `2025-01-01/2025-12-31`; baseline `2024-01-01/2024-12-31`. Current/baseline usable scoring posts: **255 / 262**; median likes **7905.00 / 11244.00**. Portfolio members: —.
- Peers used: **Prada; Gucci**; excluded/reasons: —.
- FMI missing reasons: none.
- Forecast missing reason: `missing_native_quarter_revenue_ending_near_2026-12-31`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/hermes_momentum_score F.docx`.

### ME+EM

- Identity: Light `MEEM`; ticker `—`; shared symbol `MEEM`; Instagram `meandem`. Required subject/scope: **ME+EM / consolidated**.
- Requested revenue: oldest: —, 2022-01-31…2023-01-29, exact boundaries; earlier: —, 2023-01-30…2024-01-28, exact boundaries; latest: —, 2024-01-29…2025-01-26, exact boundaries.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **57 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `Europe/London`; current `2024-10-01/2024-12-31`; baseline `2023-10-01/2023-12-31`. Current/baseline usable scoring posts: **6 / 2**; median likes **1335.50 / 523.00**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: Reiss: financial:reiss:oldest:missing_verified_consolidated_2022-01-30_2023-01-28; financial:reiss:earlier:missing_verified_consolidated_2023-01-29_2024-01-27; financial:reiss:latest:missing_verified_consolidated_2024-01-28_2025-01-25; missing_comparable_three_quarter_series; J.Jill: financial:j-jill:oldest:missing_verified_consolidated_2022-01-30_2023-01-28; financial:j-jill:earlier:missing_verified_consolidated_2023-01-29_2024-02-03; financial:j-jill:latest:missing_verified_consolidated_2024-02-04_2025-02-01; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:me-em:oldest:missing_verified_consolidated_2022-01-31_2023-01-29; financial:me-em:earlier:missing_verified_consolidated_2023-01-30_2024-01-28; financial:me-em:latest:missing_verified_consolidated_2024-01-29_2025-01-26; peers:no_assigned_peer_with_comparable_three_quarter_series; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/FMI_delivery/02_Brand_reports/me_em/me_em_fy_momentum_score.docx`.

### Coach

- Identity: Light `—`; ticker `—`; shared symbol `—`; Instagram `coach`. Required subject/scope: **Coach / brand_segment**.
- Requested revenue: oldest: FY2024, —…—, native_fiscal_year; earlier: FY2025, 2024-06-30…2025-06-28, exact boundaries; latest: FY2026, 2025-06-29…2026-06-27, exact boundaries.
- Selected revenue: oldest: 5,095,300,000 USD × 1.0, 2023-07-02…2024-06-29; denormalized.finance_specific_investor_relations; [source](https://tapestry.gcs-web.com/news-releases/news-release-details/tapestry-inc-reports-fourth-quarter-and-full-year-fiscal-2024); earlier: 5,598,500,000 USD × 1.0, 2024-06-30…2025-06-28; denormalized.finance_specific_investor_relations; [source](https://tapestry.gcs-web.com/news-releases/news-release-details/tapestry-inc-reports-fiscal-2025-fourth-quarter-and-full-year); latest: 6,914,700,000 USD × 1.0, 2025-06-29…2026-06-27; denormalized.finance_specific_investor_relations; [source](https://tapestry.gcs-web.com/node/23341/pdf).
- Data retrieved: **6 revenue candidates**, **0 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `show`; show `2025-09-15`; timezone `America/New_York`; current `2025-09-15/2025-09-22`; baseline `2025-08-31/2025-09-14`. Current/baseline usable scoring posts: **24 / 17**; median likes **2996.50 / 4689.00**. Portfolio members: —.
- Peers used: **Michael Kors; Ralph Lauren**; excluded/reasons: —.
- FMI missing reasons: none.
- Forecast missing reason: `no_financial_rows_for_configured_subject`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/FMI_delivery/02_Brand_reports/coach/coach_show_momentum_score.docx`.

### Michael Kors

- Identity: Light `—`; ticker `—`; shared symbol `—`; Instagram `michaelkors`. Required subject/scope: **Michael Kors / brand_segment**.
- Requested revenue: oldest: FY2024, —…—, native_fiscal_year; earlier: FY2025, 2024-03-31…2025-03-29, native_fiscal_year; latest: FY2026, 2025-03-30…2026-03-28, native_fiscal_year.
- Selected revenue: oldest: 3,522,000,000 USD × 1.0, 2023-04-02…2024-03-30; denormalized.finance_specific_investor_relations; [source](https://s22.q4cdn.com/557169922/files/doc_financials/2025/q4/4Q25-earnings-release.pdf); earlier: 3,016,000,000 USD × 1.0, 2024-03-31…2025-03-29; denormalized.finance_specific_investor_relations; [source](https://s21.q4cdn.com/247539420/files/doc_financials/2025/q4/4Q25-earnings-release.pdf); latest: 2,874,000,000 USD × 1.0, 2025-03-30…2026-03-28; denormalized.finance_specific_investor_relations; [source](https://s21.q4cdn.com/247539420/files/doc_financials/2026/q4/4Q26-press-release-052626-9pm.pdf).
- Data retrieved: **6 revenue candidates**, **0 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `America/New_York`; current `2025-03-30/2026-03-28`; baseline `2024-03-31/2025-03-29`. Current/baseline usable scoring posts: **518 / 628**; median likes **2564.50 / 3609.50**. Portfolio members: —.
- Peers used: **Coach; Ralph Lauren**; excluded/reasons: —.
- FMI missing reasons: none.
- Forecast missing reason: `no_financial_rows_for_configured_subject`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/michael_kors_momentum_score F.docx`.

### Victoria's Secret & Co.

- Identity: Light `VSCO`; ticker `VSXY`; shared symbol `VSCO`; Instagram `victoriassecret`. Required subject/scope: **Victoria's Secret & Co. / consolidated**.
- Requested revenue: oldest: undefined; earlier: undefined; latest: FY2026 company net sales, 2025-02-02…2026-01-31, exact boundaries.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **45 revenue candidates**, **9 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `show`; show `2025-10-15`; timezone `America/New_York`; current `2025-10-15/2025-10-22`; baseline `2025-09-30/2025-10-14`. Current/baseline usable scoring posts: **0 / 38**; median likes **— / 132569.00**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: Wacoal: financial:wacoal:oldest:missing_dossier_dates_or_scope; financial:wacoal:earlier:missing_dossier_dates_or_scope; financial:wacoal:latest:missing_dossier_dates_or_scope; missing_comparable_three_quarter_series; Aerie: financial:aerie:oldest:missing_dossier_dates_or_scope; financial:aerie:earlier:missing_dossier_dates_or_scope; financial:aerie:latest:missing_dossier_dates_or_scope; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:victoria-s-secret-co:oldest:missing_dossier_dates_or_scope; financial:victoria-s-secret-co:earlier:missing_dossier_dates_or_scope; financial:victoria-s-secret-co:latest:missing_verified_consolidated_2025-02-02_2026-01-31; peers:no_assigned_peer_with_comparable_three_quarter_series; social:current_requires_5_usable_posts; social:missing_or_zero_baseline_likes; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `missing_native_quarter_revenue_ending_near_2026-12-31`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/FMI_delivery/02_Brand_reports/victorias_secret/victorias_secret_show_momentum_score.docx`.

### Marc Jacobs

- Identity: Light `LVMHF`; ticker `LVMHF`; shared symbol `LVMHF`; Instagram `marcjacobs`. Required subject/scope: **LVMH consolidated group / consolidated**.
- Requested revenue: oldest: —, 2023-01-01…2023-12-31, exact boundaries; earlier: FY2024 vs. FY2023, 2024-01-01…2024-12-31, exact boundaries; latest: FY2025 vs. FY2024, 2025-01-01…2025-12-31, exact boundaries.
- Selected revenue: oldest: 86,153,000,000 EUR × 1.0, 2023-01-01…2023-12-31; denormalized.finance_specific_investor_relations; [source](https://lvmh-com.cdn.prismic.io/lvmh-com/Z5kVBpbqstJ999KR_Financialdocuments-December31%2C2024.pdf); earlier: 84,683,000,000 EUR × 1.0, 2024-01-01…2024-12-31; denormalized.finance_specific_investor_relations; [source](https://lvmh-com.cdn.prismic.io/lvmh-com/Z5kVBpbqstJ999KR_Financialdocuments-December31%2C2024.pdf); latest: 80,807,000,000 EUR × 1.0, 2025-01-01…2025-12-31; denormalized.finance_specific_investor_relations; [source](https://lvmh-com.cdn.prismic.io/lvmh-com/aXjqHgIvOtkhB_8I_Financialdocuments-December31%2C2025.pdf).
- Data retrieved: **124 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `UTC`; current `2025-07-01/2025-12-31`; baseline `2024-07-01/2024-12-31`. Current/baseline usable scoring posts: **73 / 91**; median likes **2360.00 / 4658.00**. Portfolio members: —.
- Peers used: **Hermès; Moncler Group**; excluded/reasons: —.
- FMI missing reasons: none.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/FMI_delivery/02_Brand_reports/marc_jacobs/marc_jacobs_momentum_score.docx`.

### Tory Burch

- Identity: Light `TORYBURCH`; ticker `—`; shared symbol `TORYBURCH`; Instagram `toryburch`. Required subject/scope: **— / —**.
- Requested revenue: oldest: undefined; earlier: undefined; latest: undefined.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **57 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `America/New_York`; current `2025-01-01/2025-12-31`; baseline `2024-01-01/2024-12-31`. Current/baseline usable scoring posts: **144 / 96**; median likes **3816.50 / 3622.50**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: Michael Kors: financial:michael-kors:missing_dossier_period_definition; missing_comparable_three_quarter_series; Coach: financial:coach:missing_dossier_period_definition; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:tory-burch:missing_dossier_period_definition; peers:no_assigned_peer_with_comparable_three_quarter_series; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/tory_burch_momentum_score Incomplete.docx`.

### Lafayette 148

- Identity: Light `LAFAYET148`; ticker `—`; shared symbol `LAFAYET148`; Instagram `lafayette148ny`. Required subject/scope: **Lafayette 148 / dossier_labelled_company**.
- Requested revenue: oldest: FY2023, 2023-01-01…2023-12-31, exact boundaries; earlier: FY2024, 2024-01-01…2024-12-31, exact boundaries; latest: FY2025, 2025-01-01…2025-12-31, exact boundaries.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **57 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `UTC`; current `2026-01-01/2026-10-28`; baseline `2025-01-01/2025-10-28`. Current/baseline usable scoring posts: **91 / 56**; median likes **44.00 / 57.50**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: ME+EM: financial:me-em:oldest:missing_verified_dossier_labelled_company_2023-01-01_2023-12-31; financial:me-em:earlier:missing_verified_dossier_labelled_company_2024-01-01_2024-12-31; financial:me-em:latest:missing_verified_dossier_labelled_company_2025-01-01_2025-12-31; missing_comparable_three_quarter_series; Lilly Pulitzer: financial:lilly-pulitzer:oldest:missing_verified_dossier_labelled_company_2023-01-01_2023-12-31; financial:lilly-pulitzer:earlier:missing_verified_dossier_labelled_company_2024-01-01_2024-12-31; financial:lilly-pulitzer:latest:missing_verified_dossier_labelled_company_2025-01-01_2025-12-31; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:lafayette-148:oldest:missing_verified_dossier_labelled_company_2023-01-01_2023-12-31; financial:lafayette-148:earlier:missing_verified_dossier_labelled_company_2024-01-01_2024-12-31; financial:lafayette-148:latest:missing_verified_dossier_labelled_company_2025-01-01_2025-12-31; peers:no_assigned_peer_with_comparable_three_quarter_series; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/FMI_delivery/02_Brand_reports/lafayette_148/lafayette_148_annual_momentum.docx`.

### Lilly Pulitzer

- Identity: Light `LILLYPUL`; ticker `—`; shared symbol `LILLYPUL`; Instagram `lillypulitzer`. Required subject/scope: **Lilly Pulitzer / brand_segment**.
- Requested revenue: oldest: —, 2023-01-29…2024-02-03, exact boundaries; earlier: —, 2024-02-04…2025-02-01, exact boundaries; latest: —, 2025-02-02…2026-01-31, exact boundaries.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **57 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `UTC`; current `2025-02-02/2026-01-31`; baseline `2024-02-04/2025-02-01`. Current/baseline usable scoring posts: **230 / 125**; median likes **603.50 / 770.00**. Portfolio members: —.
- Peers used: **Ralph Lauren**; excluded/reasons: J.Jill: financial:j-jill:oldest:missing_verified_consolidated_2023-01-29_2024-02-03; financial:j-jill:earlier:missing_verified_consolidated_2024-02-04_2025-02-01; financial:j-jill:latest:missing_verified_consolidated_2025-02-02_2026-01-31; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:lilly-pulitzer:oldest:missing_verified_brand_segment_2023-01-29_2024-02-03; financial:lilly-pulitzer:earlier:missing_verified_brand_segment_2024-02-04_2025-02-01; financial:lilly-pulitzer:latest:missing_verified_brand_segment_2025-02-02_2026-01-31; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/FMI_delivery/02_Brand_reports/lilly_pulitzer/lilly_pulitzer_fiscal_year_comparison.docx`.

### Christian Dior

- Identity: Light `LVMHF`; ticker `LVMHF`; shared symbol `LVMHF`; Instagram `dior`. Required subject/scope: **LVMH Fashion and Leather Goods / parent_segment**.
- Requested revenue: oldest: FY2023, 2023-01-01…2023-12-31, exact boundaries; earlier: FY2024, 2024-01-01…2024-12-31, exact boundaries; latest: FY2025, 2025-01-01…2025-12-31, exact boundaries.
- Selected revenue: oldest: 42,169,000,000 EUR × 1.0, 2023-01-01…2023-12-31; denormalized.finance_specific_investor_relations; [source](https://lvmh-com.cdn.prismic.io/lvmh-com/Z5kVBpbqstJ999KR_Financialdocuments-December31%2C2024.pdf); earlier: 41,060,000,000 EUR × 1.0, 2024-01-01…2024-12-31; denormalized.finance_specific_investor_relations; [source](https://lvmh-com.cdn.prismic.io/lvmh-com/aXjqHgIvOtkhB_8I_Financialdocuments-December31%2C2025.pdf); latest: 37,770,000,000 EUR × 1.0, 2025-01-01…2025-12-31; denormalized.finance_specific_investor_relations; [source](https://lvmh-com.cdn.prismic.io/lvmh-com/aXjqHgIvOtkhB_8I_Financialdocuments-December31%2C2025.pdf).
- Data retrieved: **122 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `Europe/Paris`; current `2025-01-01/2025-12-31`; baseline `2024-01-01/2024-12-31`. Current/baseline usable scoring posts: **927 / 1127**; median likes **26379.00 / 34883.00**. Portfolio members: —.
- Peers used: **Gucci; Hermès**; excluded/reasons: —.
- FMI missing reasons: none.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/christian_dior_momentum_score F.docx`.

### Valentino

- Identity: Light `VALENTINO`; ticker `—`; shared symbol `VALENTINO`; Instagram `maisonvalentino`. Required subject/scope: **Valentino / standalone**.
- Requested revenue: oldest: FY2023, 2023-01-01…2023-12-31, exact boundaries; earlier: FY2024, 2024-01-01…2024-12-31, exact boundaries; latest: FY2025, 2025-01-01…2025-12-31, exact boundaries.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **54 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `Europe/Paris`; current `2025-01-01/2025-12-31`; baseline `2024-01-01/2024-12-31`. Current/baseline usable scoring posts: **471 / 313**; median likes **7182.00 / 9370.00**. Portfolio members: —.
- Peers used: **Gucci; Saint Laurent**; excluded/reasons: —.
- FMI missing reasons: `financial:valentino:oldest:missing_verified_standalone_2023-01-01_2023-12-31; financial:valentino:earlier:missing_verified_standalone_2024-01-01_2024-12-31; financial:valentino:latest:missing_verified_standalone_2025-01-01_2025-12-31; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/valentino_momentum_score F.docx`.

### Etro

- Identity: Light `ETRO`; ticker `—`; shared symbol `ETRO`; Instagram `etro`. Required subject/scope: **— / —**.
- Requested revenue: oldest: undefined; earlier: undefined; latest: undefined.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **54 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `Europe/Rome`; current `2025-01-01/2025-12-31`; baseline `2024-01-01/2024-12-31`. Current/baseline usable scoring posts: **338 / 174**; median likes **3620.00 / 4151.00**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: Brunello Cucinelli: financial:brunello-cucinelli:missing_dossier_period_definition; missing_comparable_three_quarter_series; Salvatore Ferragamo: financial:salvatore-ferragamo:missing_dossier_period_definition; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:etro:missing_dossier_period_definition; peers:no_assigned_peer_with_comparable_three_quarter_series; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/etro_momentum_score Incomplete.docx`.

### The Row

- Identity: Light `—`; ticker `—`; shared symbol `—`; Instagram `therow`. Required subject/scope: **— / —**.
- Requested revenue: oldest: undefined; earlier: undefined; latest: undefined.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **0 revenue candidates**, **0 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `Europe/Paris`; current `2025-01-01/2025-12-31`; baseline `2024-01-01/2024-12-31`. Current/baseline usable scoring posts: **63 / 79**; median likes **5367.00 / 6475.00**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: Brunello Cucinelli: financial:brunello-cucinelli:missing_dossier_period_definition; missing_comparable_three_quarter_series; Hermès: financial:hermes:missing_dossier_period_definition; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:the-row:missing_dossier_period_definition; peers:no_assigned_peer_with_comparable_three_quarter_series; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `no_financial_rows_for_configured_subject`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/the_row_momentum_score Incomplete.docx`.

### Prada

- Identity: Light `PRDSY`; ticker `PRDSY`; shared symbol `PRDSY`; Instagram `prada`. Required subject/scope: **Prada Group / consolidated**.
- Requested revenue: oldest: FY2023, 2023-01-01…2023-12-31, exact boundaries; earlier: FY2024, 2024-01-01…2024-12-31, exact boundaries; latest: FY2025, 2025-01-01…2025-12-31, exact boundaries.
- Selected revenue: oldest: 4,726,411,000 EUR × 1.0, 2023-01-01…2023-12-31; denormalized.finance_specific_investor_relations; [source](https://www.pradagroup.com/content/dam/pradagroup/documents/investors/FY-2023/e-%20Announcement%20of%20the%20Consolidated%20results%20for%20the%20period%20ended%20December%2031%202023.pdf); earlier: 5,431,557,000 EUR × 1.0, 2024-01-01…2024-12-31; denormalized.finance_specific_investor_relations; [source](https://www.pradagroup.com/content/dam/pradagroup/documents/Shareholderinformation/2025/e-Announcement_of_the_Consolidated_results_for_the_period_ended_December_31_2024.pdf); latest: 5,717,521,000 EUR × 1.0, 2025-01-01…2025-12-31; denormalized.finance_specific_investor_relations; [source](https://www.pradagroup.com/content/dam/pradagroup/documents/investors/FY-2025/e-Announcement-of_the_Consolidated_results_for_the_period_ended_December_31_2025.pdf).
- Data retrieved: **69 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `Europe/Rome`; current `2025-01-01/2025-12-31`; baseline `2024-01-01/2024-12-31`. Current/baseline usable scoring posts: **613 / 611**; median likes **12607.00 / 16859.00**. Portfolio members: —.
- Peers used: **Hermès; Gucci**; excluded/reasons: —.
- FMI missing reasons: none.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/prada_momentum_score F.docx`.

### Chanel

- Identity: Light `CHANEL`; ticker `CHANEL`; shared symbol `CHANEL`; Instagram `chanelofficial`. Required subject/scope: **Chanel / standalone**.
- Requested revenue: oldest: FY2023, 2023-01-01…2023-12-31, exact boundaries; earlier: FY2024, 2024-01-01…2024-12-31, exact boundaries; latest: FY2025, 2025-01-01…2025-12-31, exact boundaries.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **45 revenue candidates**, **15 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `Europe/Paris`; current `2025-01-01/2025-12-31`; baseline `2024-01-01/2024-12-31`. Current/baseline usable scoring posts: **506 / 695**; median likes **22979.50 / 25234.00**. Portfolio members: —.
- Peers used: **Hermès; Prada**; excluded/reasons: —.
- FMI missing reasons: `financial:chanel:oldest:missing_verified_standalone_2023-01-01_2023-12-31; financial:chanel:earlier:missing_verified_standalone_2024-01-01_2024-12-31; financial:chanel:latest:missing_verified_standalone_2025-01-01_2025-12-31; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/chanel_momentum_score F.docx`.

### Kate Spade

- Identity: Light `—`; ticker `—`; shared symbol `—`; Instagram `katespadeny`. Required subject/scope: **Kate Spade / brand_segment**.
- Requested revenue: oldest: FY2024, —…—, native_fiscal_year; earlier: FY2025, 2024-06-30…2025-06-28, native_fiscal_year; latest: FY2026, 2025-06-29…2026-06-27, native_fiscal_year.
- Selected revenue: oldest: 1,334,400,000 USD × 1.0, 2023-07-02…2024-06-29; denormalized.finance_specific_investor_relations; [source](https://tapestry.gcs-web.com/news-releases/news-release-details/tapestry-inc-reports-fourth-quarter-and-full-year-fiscal-2024); earlier: 1,197,100,000 USD × 1.0, 2024-06-30…2025-06-28; denormalized.finance_specific_investor_relations; [source](https://tapestry.gcs-web.com/news-releases/news-release-details/tapestry-inc-reports-fiscal-2025-fourth-quarter-and-full-year); latest: 1,074,900,000 USD × 1.0, 2025-06-29…2026-06-27; denormalized.finance_specific_investor_relations; [source](https://tapestry.gcs-web.com/node/23341/pdf).
- Data retrieved: **6 revenue candidates**, **0 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `UTC`; current `2025-06-29/2026-06-27`; baseline `2024-06-30/2025-06-28`. Current/baseline usable scoring posts: **228 / 275**; median likes **712.00 / 1386.00**. Portfolio members: —.
- Peers used: **Michael Kors; Ralph Lauren**; excluded/reasons: —.
- FMI missing reasons: none.
- Forecast missing reason: `no_financial_rows_for_configured_subject`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/kate_spade_momentum_score F.docx`.

### Rag & Bone

- Identity: Light `—`; ticker `—`; shared symbol `—`; Instagram `ragandbone`. Required subject/scope: **— / —**.
- Requested revenue: oldest: undefined; earlier: undefined; latest: undefined.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **0 revenue candidates**, **0 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `UTC`; current `—`; baseline `—`. Current/baseline usable scoring posts: **— / —**; median likes **— / —**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: Ralph Lauren: financial:ralph-lauren:missing_dossier_period_definition; missing_comparable_three_quarter_series; PVH: financial:pvh:missing_dossier_period_definition; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:rag-bone:missing_dossier_period_definition; peers:no_assigned_peer_with_comparable_three_quarter_series; social:missing_annual_windows; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `no_financial_rows_for_configured_subject`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/rag_and_bone_momentum_score Incomplete.docx`.

### American Eagle

- Identity: Light `AEO`; ticker `AEO`; shared symbol `AEO`; Instagram `americaneagle`. Required subject/scope: **— / —**.
- Requested revenue: oldest: undefined; earlier: undefined; latest: undefined.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **51 revenue candidates**, **16 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `—`; show `—`; timezone `—`; current `—`; baseline `—`. Current/baseline usable scoring posts: **— / —**; median likes **— / —**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: Abercrombie & Fitch: financial:abercrombie-fitch:missing_dossier_period_definition; missing_comparable_three_quarter_series; Gap: financial:gap:missing_dossier_period_definition; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:american-eagle:missing_dossier_period_definition; peers:no_assigned_peer_with_comparable_three_quarter_series; social:analysis_route_required; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `missing_native_quarter_revenue_ending_near_2026-12-31`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `—`.

### Uniqlo

- Identity: Light `—`; ticker `—`; shared symbol `—`; Instagram `uniqlo`. Required subject/scope: **— / —**.
- Requested revenue: oldest: undefined; earlier: undefined; latest: undefined.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **0 revenue candidates**, **0 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `UTC`; current `—`; baseline `—`. Current/baseline usable scoring posts: **— / —**; median likes **— / —**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: Zara: financial:zara:missing_dossier_period_definition; missing_comparable_three_quarter_series; H&M: financial:h-m:missing_dossier_period_definition; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:uniqlo:missing_dossier_period_definition; peers:no_assigned_peer_with_comparable_three_quarter_series; social:missing_annual_windows; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `no_financial_rows_for_configured_subject`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/uniqlo_momentum_score _ Incomplete.docx`.

### Zara

- Identity: Light `—`; ticker `—`; shared symbol `—`; Instagram `zara`. Required subject/scope: **— / —**.
- Requested revenue: oldest: undefined; earlier: undefined; latest: undefined.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **0 revenue candidates**, **0 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `UTC`; current `—`; baseline `—`. Current/baseline usable scoring posts: **— / —**; median likes **— / —**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: H&M: financial:h-m:missing_dossier_period_definition; missing_comparable_three_quarter_series; Uniqlo: financial:uniqlo:missing_dossier_period_definition; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:zara:missing_dossier_period_definition; peers:no_assigned_peer_with_comparable_three_quarter_series; social:missing_annual_windows; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `no_financial_rows_for_configured_subject`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/zara_momentum_score Incomplete.docx`.

### H&M

- Identity: Light `—`; ticker `—`; shared symbol `HM-B.ST`; Instagram `hm`. Required subject/scope: **— / —**.
- Requested revenue: oldest: undefined; earlier: undefined; latest: undefined.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **26 revenue candidates**, **0 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `UTC`; current `—`; baseline `—`. Current/baseline usable scoring posts: **— / —**; median likes **— / —**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: Zara: financial:zara:missing_dossier_period_definition; missing_comparable_three_quarter_series; Uniqlo: financial:uniqlo:missing_dossier_period_definition; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:h-m:missing_dossier_period_definition; peers:no_assigned_peer_with_comparable_three_quarter_series; social:missing_annual_windows; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `missing_native_quarter_revenue_ending_near_2026-12-31`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/hm_momentum_score Incomplete.docx`.

### Mango

- Identity: Light `MANGO`; ticker `—`; shared symbol `MANGO`; Instagram `mango`. Required subject/scope: **— / —**.
- Requested revenue: oldest: undefined; earlier: undefined; latest: undefined.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **54 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `annual`; show `—`; timezone `UTC`; current `—`; baseline `—`. Current/baseline usable scoring posts: **— / —**; median likes **— / —**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: Zara: financial:zara:missing_dossier_period_definition; missing_comparable_three_quarter_series; H&M: financial:h-m:missing_dossier_period_definition; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:mango:missing_dossier_period_definition; peers:no_assigned_peer_with_comparable_three_quarter_series; social:missing_annual_windows; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `handover/New prospects info/mango_momentum_score Incomplete.docx`.

### Levi's

- Identity: Light `LEVI`; ticker `LEVI`; shared symbol `LEVI`; Instagram `levis`. Required subject/scope: **— / —**.
- Requested revenue: oldest: undefined; earlier: undefined; latest: undefined.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **51 revenue candidates**, **16 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `—`; show `—`; timezone `—`; current `—`; baseline `—`. Current/baseline usable scoring posts: **— / —**; median likes **— / —**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: Kontoor Brands: financial:kontoor-brands:missing_dossier_period_definition; missing_comparable_three_quarter_series; PVH: financial:pvh:missing_dossier_period_definition; missing_comparable_three_quarter_series.
- FMI missing reasons: `financial:levi-s:missing_dossier_period_definition; peers:no_assigned_peer_with_comparable_three_quarter_series; social:analysis_route_required; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `unreviewed_parent_or_group_proxy`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `—`.

### Armani

- Identity: Light `ARMANI`; ticker `ARMANI`; shared symbol `ARMANI`; Instagram `giorgioarmani`. Required subject/scope: **— / —**.
- Requested revenue: oldest: undefined; earlier: undefined; latest: undefined.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **51 revenue candidates**, **16 native forecast candidates**; **1** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `—`; show `—`; timezone `—`; current `—`; baseline `—`. Current/baseline usable scoring posts: **— / —**; median likes **— / —**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: —.
- FMI missing reasons: `financial:armani:missing_dossier_period_definition; peers:no_assigned_peer_with_comparable_three_quarter_series; social:analysis_route_required; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `dossier_forecast_scope_not_verified_or_incompatible`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `—`.

### Longchamp

- Identity: Light `—`; ticker `—`; shared symbol `—`; Instagram `longchamp`. Required subject/scope: **— / —**.
- Requested revenue: oldest: undefined; earlier: undefined; latest: undefined.
- Selected revenue: none verified for the requested roles.
- Data retrieved: **0 revenue candidates**, **0 native forecast candidates**; **0** forecast candidates matching the target end date only. See `observed_*` columns for unreviewed native context, not eligible FMI drivers.
- Social: route `—`; show `—`; timezone `—`; current `—`; baseline `—`. Current/baseline usable scoring posts: **— / —**; median likes **— / —**. Portfolio members: —.
- Peers used: **—**; excluded/reasons: —.
- FMI missing reasons: `financial:longchamp:missing_dossier_period_definition; peers:no_assigned_peer_with_comparable_three_quarter_series; social:analysis_route_required; ir:missing_brand_or_peer_quarter_growth; trend:missing_earlier_and_latest_quarter_gaps`.
- Forecast missing reason: `no_financial_rows_for_configured_subject`. A valid score and rate do not authorize a missing/incompatible baseline.
- Parameter source: `—`.

## Other prospects: per-brand regression reason

| Brand | Archived raw | Repaired raw | IR / Social / Trend | Revenue candidates | Reason |
|---|---:|---:|---|---:|---|
| Ralph Lauren | 74.82 | 65.21 | 94.57 / 39.74 / 30.00 | 75 | FMI available; dossier periods/scopes differ from the archived latest-quarter simulation. |
| Christian Louboutin | — | — | — / — / — | 57 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| TOM FORD | 96.00 | — | — / — / — | 54 | Published comparable-growth observations required, not nominal revenue; No assigned peer has a usable three-observation series; Social sample below minimum usable-post count |
| DKNY | — | — | — / 100.00 / — | 66 | Incomplete financial dates or reporting scope; No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| Calvin Klein | 47.46 | 36.00 | 0.00 / 100.00 / 30.00 | 6 | FMI available; dossier periods/scopes differ from the archived latest-quarter simulation. |
| G-III Apparel Group | — | — | — / 70.00 / — | 66 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| PacSun | 46.24 | — | — / 39.27 / — | 57 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| Jacquemus | 67.46 | — | — / 11.54 / — | 45 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| Exemplar Luxury Group | — | — | — / — / — | 57 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| Nordstrom | 25.82 | — | — / 34.81 / 50.00 | 69 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| Amazon Fashion | — | — | — / — / — | 0 | Incomplete financial dates or reporting scope; No assigned peer has a usable three-observation series |
| Bloomingdales | 50.04 | — | — / 24.60 / — | 54 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| Kohl's | — | — | — / — / — | 54 | Incomplete financial dates or reporting scope; No assigned peer has a usable three-observation series |
| Macys | — | — | — / — / — | 54 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series; Social sample below minimum usable-post count; Social baseline missing or zero |
| Belmont Park Village | — | — | — / — / — | 57 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series; Social sample below minimum usable-post count; Social baseline missing or zero |
| Estée Lauder | 89.35 | — | — / 91.72 / — | 60 | Incomplete financial dates or reporting scope; No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| New Balance | 43.58 | — | — / 0.00 / — | 57 | Incomplete financial dates or reporting scope; No assigned peer has a usable three-observation series |
| Ulta Beauty | 40.26 | — | — / 32.57 / — | 54 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| Aman | — | — | — / — / — | 57 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series; Social sample below minimum usable-post count; Social baseline missing or zero |
| David Yurman | 23.88 | — | — / 59.58 / — | 57 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| RIMOWA | 58.08 | 46.31 | 50.41 / 50.36 / 30.00 | 66 | FMI available; dossier periods/scopes differ from the archived latest-quarter simulation. |
| Foot Locker | — | — | — / — / — | 71 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| Rare Beauty | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series; Social annual windows missing |
| Target | — | — | — / — / — | 66 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series; Social sample below minimum usable-post count; Social baseline missing or zero |
| Kith | — | — | — / — / — | 0 | Incomplete financial dates or reporting scope; No assigned peer has a usable three-observation series |
| TikTok | — | — | — / — / — | 51 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Five Below | — | — | — / — / — | 24 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| Diane von Furstenberg | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Caleres | — | — | — / — / — | 54 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series; Social sample below minimum usable-post count; Social baseline missing or zero |
| LAGOS | — | — | — / — / — | 57 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series; Social sample below minimum usable-post count; Social baseline missing or zero |
| Veronica Beard | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Marcolin Eyewear | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| The Center | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| The Bicester Collection | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Santoni spa | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Sanderlak | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Retrofete | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Rachel Zoe Creations | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Proenza Schouler | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| PMC | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Nicole Miller | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Marla Aaron Jewelry | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| LAMARQUE | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| La Double J | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| L'AGENCE | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Karla Otto | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Global Luxury Retail Group DBA Missoni | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series; Analysis route/social windows missing |
| Echo | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Doneger Tobe | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Centric Brands | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Cain International | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Burleigh | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Bomber Ski | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| ASHLYN | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Akris | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| The Jewelry Group | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| The Independents Group | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| The Fragrance Foundation | — | — | — / — / — | 0 | Financial subject/scope/three periods not defined in input; No assigned peer has a usable three-observation series |
| Tommy Hilfiger | 47.46 | 36.00 | 0.00 / 100.00 / 30.00 | 6 | FMI available; dossier periods/scopes differ from the archived latest-quarter simulation. |
| VF Corporation | — | — | — / 33.51 / — | 63 | No verified source amount matching the requested financial scope/period(s); No assigned peer has a usable three-observation series |
| LVMH | 32.57 | 32.55 | 11.54 / 42.61 / 70.00 | 86 | Recovered: current weighted headline. Historical percentile remains a separate frozen reference. |
| Louis Vuitton | 31.48 | 31.47 | 11.54 / 38.99 / 70.00 | 86 | FMI available; dossier periods/scopes differ from the archived latest-quarter simulation. |
| Missoni | 79.86 | — | — / 47.87 / — | 54 | Incomplete financial dates or reporting scope; No assigned peer has a usable three-observation series |

## Remaining work, in priority order

1. **Incomplete dinner parameters:** Abercrombie, Victoria’s Secret, Tory Burch, Etro, The Row, Rag & Bone, American Eagle, Uniqlo, Zara, H&M, Mango, Levi’s, Armani and Longchamp need the missing scope/three financial periods and/or social windows listed above. Obtain those decisions from the business dossier owner; do not default them to current calendar quarters.
2. **Private/segment dinner measurements:** provide source-backed annual observations for J.Crew, ME+EM, Lafayette 148, Lilly Pulitzer/Oxford, Chanel and Valentino in the exact periods/scopes above. Some current tables already contain numerical candidates; the blocker is eligible reporting-level/units/period evidence, not necessarily absence of every number. Publish complete issuer disclosures or explicit structured metadata to make selection reproducible.
3. **Peers:** resolve only enough assigned peers to provide at least one comparable three-observation series. Include the approved financial subject and fiscal boundaries. One missing peer does not need to block an otherwise valid brand.
4. **Forecast baselines:** for the selected financial subject, supply positive Q4 2026 revenue forecast amount, currency, unit multiplier, reporting scope, exact target start/end and fiscal/calendar alignment. Historical replay additionally needs dated forecast and financial vintages. Do not use Tapestry/Capri consolidated forecasts to uplift a brand-segment score without an explicit business-approved proxy method.
5. **Original percentile reproduction (optional):** provide the original reference cohort and normalization parameters if exact historical percentile FMI needs recalculation. This is not required for the current weighted headline, and no original dossier score has been overwritten.

## Files and verification

- Current delivery: `outputs/fmi/weighted-delivery.xlsx` and `.json`, one flat prospect table. Field definitions, types and units come from the existing `src/aily_project/services/fmi/contract.py` dictionary and `flat_delivery.py` context fields. No additional final JSON files were introduced.
- Original dossier: `outputs/fmi/dossier-delivery.xlsx` and `.json`. Only existing `current_*` and `comparison_*` columns were refreshed. All original JSON fields, Excel cells and styles were checked unchanged.
- Before-recovery files preserved under `outputs/fmi/backups/20261102-before-coverage-recovery/`. These are references, never restored into the current calculation.
- The three actual notebooks completed. Offline notebook/service and Excel/JSON parity, stable prospect IDs and field types, original dossier preservation, formula-error scans and visual workbook checks were performed. Isolated tests cover annual versus quarter/parent selection, fiscal labels/53-week sources, missing data and the weighted-versus-reference headline switch.
- Final project checks: **276 tests passed, 2 skipped**; Ruff lint, Ruff formatting and type checks passed.
- This report is a **one-time explanation**, not a new notebook step. Future human changes remain in `inputs/FMI_inputs.json` and the existing policy YAML. No commit or push was performed.
