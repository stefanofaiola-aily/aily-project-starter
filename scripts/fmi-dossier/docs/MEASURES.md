# FMI dossier measures and calculations

Methodology reference, 2 November 2026. This describes the independent **dossier delivery**, not the automated Light/shared scoring notebooks. Column definitions and recommended app fields are in [DELIVERY_COLUMNS.md](DELIVERY_COLUMNS.md).

## 1. What the delivery actually does

The workflow is:

1. Read the dossier values transcribed once into `inputs/FMI_dossier_inputs.xlsx`.
2. Preserve explicitly supplied published scores for existing scored brands. Otherwise select the dossier's reported headline, or explicitly recompute from its component scores.
3. Preserve the published normalized scores; normalize only new/unpublished headlines onto 70–98 using the selected-score cohort.
4. Apply both legacy and exponential uplift to the same unadjusted forecast baseline.
5. Export one Excel row and one JSON `rows` record per included prospect with available measurement, score or forecast data.

The input workbook is updated when a dossier is new/changed, or when a missing forecast is supplied. It is not rebuilt from Word on every run. The dossier financial/social values are accepted for this client demo. Live database revenue and social observations do not replace them. A missing forecast can be checked separately in Light.

One brand has **one selected headline FMI**, not one FMI per peer combination. Peer observations explain the comparison. A brand can have component scores without a complete headline, or a headline without a forecast amount. These are different kinds of missingness.

The current Excel contains `Delivery` and `Column guide` sheets. The guide documents every exported column and marks recommended delivery fields. **AW is the new adjusted Q4/selected-target YoY versus PY forecast, AV is before uplift and AX is the increase in percentage points.** AL preserves the historical source projection versus PY sales. Read AM for calendar/fiscal target alignment. The JSON contains `rows` plus policy, cohort, field definitions, calculation traces and delivery-only leaderboards. It is a handover export, not a native app upload payload.

## 2. Where each kind of information comes from

| Information | Source in this workflow | Treatment |
| --- | --- | --- |
| Selected FMI and component scores | Explicit published input snapshot for existing scored brands; dossier/source workbook otherwise | Preserve published scores and card metrics. Keep alternative dossier values separately. |
| Revenue, growth, peers and social measurements | Dossier/source workbook | Keep amounts, definitions, selected windows and limitations. Do not silently replace them with current database observations. |
| Collection/show dates and financial/social periods | Dossier | Keep their actual meaning. Collection date, selling period and forecast period need not coincide. |
| Company identity | Light company registry and supplied mappings | App retrieval key is `light.light_companies.company_code`; ticker/shared symbol remain separate. |
| Dinner membership, expected Light presence and app category | Supplied company list | Routing/coverage metadata, not scoring inputs. Registry presence does not prove that every metric exists. |
| Unadjusted forecast baseline | Accepted source workbook, or a separate Light forecast check | Preserve existing accepted amounts. Missing baselines may be supplemented with a current Q4 scenario. |
| PY forecast | Matching Light forecast observation for the prior fiscal year | Current snapshot of the earlier target period, not necessarily the forecast originally issued that year. |
| Normalization, uplift, rankings and narrative KPIs | Published display/cards or dossier service | Preserve published displays/cards for existing scored brands. Always regenerate forecast narrative from final uplifted values. |
| Historical weighted-delivery reference | Original historical artifact | Comparison only. Does not feed current scoring, normalization or uplift. |

No forecast lookup changes the financial/social periods used in the dossier score. The score may describe an earlier collection or annual period while uplift is applied to a current forecast. This is a labelled business scenario, not proof that the older score predicts the current quarter.

### Published HTML reconciliation: why the values differed

The current v6 HTML is based on `weighted-delivery-1300.xlsx` in the prototype's data archive. The separate handover `weighted-delivery-1606_2810.xlsx` contains some different normalized scores. It is not an exact substitute for the HTML baseline. The previous dossier run selected alternative document methods/revisions and then rescaled every headline using 41 scores with minimum 6.41 and maximum 94. Neither operation was limited to uplift. The category update did not cause the score differences.

| Brand | Previous dossier selection / cause | Restored published values |
| --- | --- | --- |
| Fendi | Selected component-percentile headline 47, IR 60, Social 50, Strength 10 instead of the accepted original-method result. Re-normalized to 83.0. | Raw 47.3; IR 50.4; Social 53.6; Strength 30; normalized 81.6. |
| ME+EM | Raw 86 and components were already the same. Fresh cohort scaling replaced the published display override with 95.4. | Normalized 86.2; raw/components unchanged. |
| Marc Jacobs | Selected percentile-method headline 25 and components 10/30/55, instead of published original-method scores. | Raw 20; IR 11.5; Social 0.7; Strength 70; normalized 70.0. |
| Coach | Selected dossier Strength 70; the business-approved published revision used 80. | Raw 70.2; IR 100; Social 13.9; Strength 80; normalized 91.3. |
| New Balance | Selected percentile Strength 55 and Social 10, instead of the published 80 and 0. | Raw 66; IR 100; Social 0; Strength 80; normalized 89.5. |
| Estée Lauder | Selected another dossier calculation: headline 79.3 and components 75.65/91.72/70; changed periods/account selection and new cohort scaling produced 93.3. | Raw 78.3; IR 72.7; Social 86.7; Strength 75; normalized 86.5. |

Correction: the 26 published scored rows were transcribed once into the existing Excel input's five `published_*` score columns, plus `published_card_values` and exact `published_source_reference`. `score_source=published_delivery` selects them. The original `reported_fmi`, source method and financial/social context are retained. Output `dossier_ir_score`, `dossier_social_score`, `dossier_trend_score` and `dossier_reported_fmi_difference` show the alternatives explicitly. Those alternative measurements do **not** claim to reconstruct the published cards. Published KPIs and insights identify their own periods and proxy scope.

This is preservation of an accepted delivered snapshot, not a new validation of its source queries. New/unpublished brands still use their dossier inputs. Old company aliases, categories and ranks are not imported: exact Light keys and the new three-category list remain authoritative. Existing accepted forecast baselines are unchanged. The new exponential uplift is calculated from the **preserved published normalized score**, so Fendi uses 81.6, not 83.0. Adding a new brand cannot silently change that display or its uplift.

Armani's new document is `dossiers/armani/armani_momentum_score.docx`, linked to the existing single input row. It reports approximately EUR 2,190m FY2025 revenue and rounded EUR 2,300m FY2024, but no FY2023 amount, no approved peers and no comparable FY2024/FY2025 Giorgio Armani Instagram history. Its stated 2025 decline of 4.6% is retained instead of recomputing growth from rounded amounts. Emporio Armani's separate account is not substituted. The saved Q4 forecast (USD 578.026m) and PY forecast (USD 558.259m) remain available, with baseline YoY +3.54%; no FMI or adjusted forecast is invented. EUR dossier revenues and USD forecasts are separate contexts, without FX conversion.

## 3. Units and notation

| Quantity | Storage | Example of interpretation |
| --- | --- | --- |
| FMI/component score | Number from 0 to 100 | `70` means 70 score points, not 70%. |
| Growth, social lift, weights and uplift | Fraction | `0.12` displays as 12%; a 50% weight is `0.50`. |
| Peer-growth gap or gap change | Percentage points (`pp`) | 12% own growth minus 9% peer growth is `3`, not `0.03`. |
| Weighted contribution | Score points | A score of 70 with weight 0.5 contributes 35 points. |
| Monetary amount | Number plus currency and unit multiplier | Amount `100`, currency EUR and multiplier `1000000` means EUR 100 million. |
| Post count, peer count or rank | Count | Not a percentage or confidence score. |
| Date | Calendar date | Period boundaries, not automatically publication or capture dates. |
| Extraction timestamp | ISO-8601 timestamp | When the query ran, not when the forecast was issued. |

Financial measurements use `currency` and `unit_multiplier`. Forecast amounts use `baseline_currency` and `baseline_unit_multiplier`. Do not apply the financial multiplier to forecast amounts by assumption. No currency conversion is performed.

The field dictionary's existing generic monetary unit tag is `native_currency_units`. It does **not** mean every number is an unscaled database amount: delivery baselines and adjusted amounts may be in millions. Always use the corresponding multiplier.

## 4. Revenue observations and own growth

`oldest_revenue`, `earlier_revenue` and `latest_revenue` are the source's selected comparable observations, not automatically the last three database rows. They may describe comparable annual periods or the same season/quarter in successive years.

```text
earlier_growth = earlier_revenue / oldest_revenue − 1
latest_growth  = latest_revenue / earlier_revenue − 1
```

The service fills a missing growth only when the two amounts exist, the denominator is positive and the revenue scope/currency/multiplier metadata are present. An existing dossier growth value takes precedence: it may represent organic, constant-currency, comparable-sales or issuer-adjusted growth that cannot be reproduced from headline amounts.

Read the result with `financial_subject`, `scope`, `financial_period_label`, period boundaries and `period_evidence`. Retail/DTC, wholesale, licensed-brand, segment and consolidated-group revenue are not interchangeable. Parent revenue is not automatically standalone brand revenue. Do not sum cumulative periods or invent quarterly revenue by dividing an annual amount.

The current flat export has selected/current and reference financial boundaries, but not a complete independent start/end/label triplet for every oldest/earlier/latest observation. `period_evidence`, dossier references and the calculation audit retain the additional explanation where supplied. Missing boundaries are not reconstructed by guessing a fiscal calendar.

## 5. Peer comparison and IR / Momentum

The common source methodology compares own growth with the median growth of the selected peers:

```text
earlier_gap_pp = 100 × (earlier_growth − earlier_peer_median_growth)
latest_gap_pp  = 100 × (latest_growth  − latest_peer_median_growth)
IR            = clip(50 + 5 × latest_gap_pp, 0, 100)
```

Here `clip(x,0,100)` means `min(100,max(0,x))`. An own/peer growth tie gives IR 50. A +5 pp advantage gives IR 75; a −5 pp disadvantage gives IR 25. Capping compresses very large differences, so display the actual growth gap alongside the score.

A median uses all selected usable peers, not one chosen pair. With two peer growth rates, the median is their arithmetic midpoint. Do not substitute zero growth for a missing peer. A partial peer set must be disclosed using `used_peer_names`, `used_peer_count` and `peer_observations`.

**Current dossier behaviour:** `ir_score` is transcribed, not recalculated from the gap on every run. Peer medians are also accepted source values; this service does not rebuild them from the live databases or silently change the dossier's peer set. It derives a missing gap from supplied own/peer growth when possible. A reported headline remains available even if its detailed peer evidence is absent. In explicit weighted-component mode, a missing IR component prevents the headline.

Do not reconstruct a reported IR from rounded growth and overwrite source precision. Percentile, parent/portfolio and other source methods may not use the above absolute-score formula at all. `dossier_score_basis` distinguishes them.

App naming matters: **Trend / Peer Trajectory** is the IR/Momentum component with **50% weight**. It is not the internal `trend_score` field.

## 6. Social / Show Attention

The common source method compares the median metric in the selected current sample with its baseline:

```text
social_lift_fraction = current_median_metric / baseline_median_metric − 1
Social              = clip(50 + 100 × social_lift_fraction, 0, 100)
```

No change gives Social 50; +20% gives 70; −20% gives 30. +50% or more reaches 100. This is attention measured through the selected metric, not audience-opinion sentiment, engagement rate, revenue or causation.

`social_metric` identifies what the medians measure. Likes, comments and other report-specific metrics must not be relabelled as the same quantity. `social_platform`, handle, current/baseline windows, dates, capture date, post counts and sample notes must accompany the comparison.

The median is a per-post statistic, not total activity. Twice as many posts does not mechanically double the median. Missing metrics are not zero; a recorded zero can be a valid observation. A missing/zero baseline median cannot support ratio lift. Existing reported lift takes precedence over a newly derived ratio.

Source windows vary: some show reports use day 0 through +7 with a preceding −15 through −1 baseline; others use annual, matching-month, YTD or campaign-portfolio comparisons. **The dossier route preserves these choices.** It does not impose the automated route's −30…−1/+8…+37 baseline or minimum-five-post screen. Portfolio medians of campaign lifts are not the same as pooling every underlying post.

Post counts are whatever sample counts the dossier supplies. The flat dossier file does not prove a census of all posts or expose full included/excluded/usable-denominator counts for every brand. Sample size is not a statistical confidence guarantee. Accumulated likes/comments at different capture ages are not equal-age engagement velocity; publication-window selection does not mean those likes were earned only inside that window.

`social_score` is preserved from the dossier. A displayed median/lift may be context for an alternative source method, rather than sufficient evidence to reproduce that component. The current export does not contain a generic views, follower-growth or comments-history series. Those are not calculated or inferred when absent.

## 7. Strength / Commercial Pace and the Trend-rule differences

The underlying gap-change measurement is:

```text
trend_change_pp = latest_gap_pp − earlier_gap_pp
```

It describes improvement/deterioration in competitive growth position, not own revenue growth itself.

The roadmap's revised peer-relative Strength rule is:

| Condition | Score | Label |
| --- | --- | --- |
| Change >+2 pp and latest gap ≥0 | 80 | Strong |
| Change >+2 pp and latest gap <0 | 70 | Up and coming |
| Change from −2 to +2 pp inclusive | 50 | Neutral |
| Change <−2 pp | 30 | Fallback |

The separate controlled automation reference uses a different rule order: change >+2 →70; change <−2 →30; otherwise both gaps ≥+5 →80; otherwise →50. Some dossiers instead use company-growth, assumed Strength or percentile variants.

**Current dossier delivery does not choose between these rules and rescore every report.** It preserves the selected dossier `trend_score`. The service derives the gap change as context when both gaps exist, but does not replace the component from it. The roadmap rule explains an historical comparison; it is not universally the operative rule for every current row.

The internal `trend_score` is the **20% Strength / Revenue / Commercial Pace** component. Its app KPI is `latest_growth` (own revenue growth), while its numeric source score may reflect peer-relative Strength. Display both definitions honestly; positive own growth can coexist with a low Strength score.

## 8. Selecting the raw headline and weighted diagnostic

Policy weights are IR 0.50, Social 0.30 and Trend 0.20:

```text
ir_contribution      = ir_score × 0.50
social_contribution  = social_score × 0.30
trend_contribution   = trend_score × 0.20
weighted_component_fmi = sum of those three contributions
```

All three components are required for the weighted diagnostic. There is no neutral fill or weight redistribution.

| `score_method` | Selected `raw_fmi` | Consequence |
| --- | --- | --- |
| `reported` | Exactly `reported_fmi` | Preserves the printed report headline. Detailed amounts or components may be missing without erasing that headline. |
| `weighted_components` | `weighted_component_fmi` | Recomputes only the weighting of supplied components. Missing any component leaves the headline blank. |

```text
reported_component_difference = weighted_component_fmi − reported_fmi
```

This difference can be caused by printed rounding, original source precision or a different headline methodology. It does not prove an extraction error. `source_original_fmi` and `source_display_fmi` remain historical context, not automatically the selected current headline. A source document reference is required when a headline exists; scores must be finite and within 0–100.

Component weights change weighted mode and its diagnostic. They do not change a `reported` headline. No changes to context metrics, peer notes or app wording silently change reported FMI.

## 9. Classifications and app wording

`raw_classification`, where applicable, uses the unrounded selected raw score: High ≥70; Medium ≥60; Neutral ≥40; Low <40. It is left null for `component_percentile_normalized` source methods, because an absolute classification is not established for those percentiles.

`overall_sentiment` is a **different presentation label**: Good ≥70; Neutral from 40 to <70; Needs improvement <40. It is calculated from `raw_fmi`, not the 70–98 normalized display. It is not audience opinion. Thus an absolute FMI of 65 is Medium by classification but Neutral by presentation sentiment.

Current component presentation rules are:

| Component | Presentation rule |
| --- | --- |
| IR | High ≥75; Medium >60 and <75; Neutral 40…60 inclusive; Low <40. |
| Social | Positive >60; Neutral 40…60 inclusive; Negative <40. |
| Trend/Strength | Exact score 80 →Strong, 70 →Up and coming, 50 →Neutral, 30 →Fallback; another score →Source assessment. |

These labels describe scores. Source-specific percentile and portfolio semantics still need their method label. For those methods the service also generates the presentation labels, but they must not be interpreted as newly validated absolute performance bands.

Published scored brands preserve their exact published sentiments, descriptors, insights and typed KPIs. For other brands, app KPIs are `ir_kpi = latest_gap_pp`, `social_kpi = social_lift_fraction`, `trend_kpi = latest_growth`, with narratives generated from final selected values. A source component may be available while its underlying KPI is unavailable. A narrative never supplies a missing measurement.

## 10. Normalize the selected headlines

The cohort contains every included row with an available selected raw headline, irrespective of forecast availability, category or dinner membership. Pair diagnostics and missing headlines do not enter it.

For the 26 published scored brands, `display_fmi = published_display_fmi` unchanged. `display_fmi_basis=published_delivery_preserved` identifies this selection; `cohort.published_members` records those IDs. The following rescaling applies only to new/unpublished scores, using all selected headlines for its extrema:

```text
display_fmi = 70 + 28 × (raw_fmi − cohort_min)/(cohort_max − cohort_min)
```

Round **half-up to one decimal** before calculating exponential uplift. The minimum maps to 70.0 and maximum to 98.0. A single/equal-score cohort maps to 84.0; an empty cohort has no display results. Membership/extrema are recorded in JSON `cohort`, with row-level `cohort_min` and `cohort_max`.

This is relative display rescaling, not a new component score or probability. It does not change raw classification. Adding/removing another scored brand can change an unchanged **unpublished** brand's display and uplift; locked published displays are unaffected. All categories share this normalization cohort; ranking is subsequently category-specific. Preserving published overrides is intentional, not recalculation against the new cohort.

## 11. Forecast baseline and period selection

`baseline_revenue` is the **unadjusted starting forecast**, not a social baseline or last year's actual. `baseline_approved` means accepted for this client-demo scenario, not independent certification. A usable baseline must be positive, have kind `unadjusted_forecast`, and carry source, subject, scope, currency, multiplier, target label and start/end. An already uplifted projection must never be used as the starting amount.

The separate live check uses `light.light_companies` for identity and `ai.light_financial_statements_forecast` for revenue candidates. The alternative `light.light_plus_financial_statements_forecast` relation was also checked. Native target date, fiscal year/quarter and source-key evidence remain separate from the registry app key. The forecast table's `reported_date` is treated as its target period end, **not** a publication/vintage timestamp.

For the current Q4 2026 demo, new missing-baseline selections follow:

1. Prefer a single native quarter ending within seven days of 31 December 2026 and not before the scenario's as-of date; preserve its actual Q2/Q3/Q4 fiscal label.
2. Otherwise use an upcoming native fiscal Q4 ending no later than 7 February 2027, explicitly labelled a proxy. Its approximate start is calendar-month alignment, not a source-certified native boundary.
3. Otherwise use three explicit, complete, comparable monthly forecast observations: current month plus two. With the 2 November 2026 as-of date this is November 2026–January 2027. Never split a quarterly amount into invented months.

Equivalent duplicate candidates are not summed; conflicting amounts/periods require a selection rather than arbitrary first-row use. Quarterly rows are never summed merely because they appear quarterly. Previously accepted source baselines are preserved, so not every row was reselected by this current lookup rule. Monthly prospect matches were not established in the current check.

Current-demo native full currency units are an explicit accepted assumption where Light does not publish scale/perimeter; newly selected amounts are displayed in millions of registry currency without FX conversion. Inspect `forecast_source_notes`, `forecast_selection_method` and `forecast_period_start_basis` rather than calling every row calendar Q4.

The agent's one-time check populated missing accepted baselines into Excel. The reusable `--query-missing-forecasts` option still returns candidates and preserves input review; it does not automatically redo that one-time enrichment or overwrite accepted input cells. A plain rerun uses the saved workbook.

Parent fallbacks are explicit group scenarios: `baseline_is_parent_proxy`, `baseline_subject`, `baseline_scope` and `baseline_company_code` identify them. A parent key must not replace a missing brand's app `company_code`. A brand score applied to parent revenue does not yield a standalone brand forecast. Group totals repeated on several brand rows must not be summed as independent revenue.

## 12. Both uplift scenarios

### Exponential, the new headline scenario

```text
uplift_fraction = 0                                      if display_fmi ≤60
uplift_fraction = 0.03 + 0.08 × expm1((display_fmi−60)/40) otherwise
adjustment = baseline_revenue × uplift_fraction
adjusted_forecast = baseline_revenue + adjustment
```

`expm1(x)` means `exp(x) − 1`. Policy **v3** is the user-approved legacy-calibrated exponential. The curve is calibrated on the legacy's **raw 0–100 score scale**, with a threshold of 60, an intercept of 3% immediately above 60 and the same initial slope as legacy: 0.08/40 = 0.002 (0.2 percentage points per score point). Convex growth rewards higher scores more strongly than the linear legacy rule on the same score. It is deliberately **applied to the rounded normalized display FMI**, not the selected raw headline. The current display range 70–98 is entirely above the threshold, so available scores have uplift; missing scores remain null. The 11% ceiling from earlier versions is removed: 100 gives 16.746%, not 11%. The approved 70–98 range gives about 5.27–15.69%.

This is an explicit commercial extension to `handover/FMI_handover_plan_v2 (1).docx`: section 6 says to use raw weighted FMI without rescaling and section 7 defines the linear legacy. This delivery keeps the approved published scores/displays for existing scored brands and dossier scores for new brands, then applies the newly approved exponential. It does not claim to implement the plan's unchanged raw-score sales rule. Roadmap vocabulary and accepted published revisions remain identifiable; alternative dossier calculations do not silently replace them.

General YAML form: `uplift_intercept + uplift_scale × expm1(uplift_exponent × (display_fmi−uplift_threshold)/uplift_score_span)` above the threshold, otherwise zero. Defaults are threshold 60, intercept 0.03, scale 0.08, span 40 and exponent 1. These are not statistically calibrated parameters. Full resolved policy is recorded in JSON and the audit. No already-adjusted forecast is used as baseline. Original source-legacy comparisons remain unchanged.

Policy benchmarks (not prospect observations):

| Rounded normalized display | Exponential uplift |
| --- | --- |
| 70.0 | 5.272% |
| 80.0 | 8.190% |
| 81.6, Fendi's preserved published display | 8.728% |
| 83.0 | 9.217% |
| 84.0 | 9.577% |
| 90.0 | 11.936% |
| 98.0 | 15.686% |
| 100.0, outside current display range | 16.746% |

Fendi preserves published `raw_fmi=47.3`, components 50.4/53.6/30 and `display_fmi=81.6`. Alternative dossier `reported_fmi=47.0` and 60/50/10 remain audit context. Its untreated baseline is EUR 517.275m. New exponential = **8.728%**, adjusted forecast = **EUR 562.423m**. Original source legacy = 7.32%, original/reproduced forecast = EUR 555.140m. The raw-score legacy diagnostic is 0%. These are separate scenarios, never compounded. Original source YoY −1.3085% uses prior-year Q4 **sales** of 562.5m; new forecast-vs-PY-forecast uses the separately checked Light **forecast** of 562.5m and is **−0.0137%** (approximately −0.01%, near flat). Equal amounts do not make these the same source classification. The prior +0.436% result came from the unintended new normalized score 83.0 and is superseded.

### Legacy, the previous code scenario

```text
legacy_uplift_fraction = 0                              if raw_fmi ≤60
legacy_uplift_fraction = 0.03 + (raw_fmi − 60) × 0.002   otherwise
legacy_adjustment = baseline_revenue × legacy_uplift_fraction
legacy_adjusted_forecast = baseline_revenue + legacy_adjustment
```

The input is selected **raw FMI**, retaining source precision. A raw score of exactly 60 gives zero; just above 60 the formula starts at about 3%. This threshold discontinuity is preserved, not silently smoothed. Both methods use the same untreated baseline; they are alternatives, never compounded.

Legacy benchmarks: raw 60 gives 0%; raw 65 gives 4%; raw 70 gives 5%; raw 100 gives 11%. Compare the two methods only after applying each to its own correct score basis.

### Reproduce the historical source workbook separately

`source_legacy_uplift_fraction` applies the legacy function to `source_display_fmi`, when supplied. `source_legacy_adjusted_forecast` applies that rate to the accepted baseline. `source_projection_difference` is reproduced amount minus `source_projected_forecast`.

These are comparison columns, not a third headline recommendation. The historical workbook used its own display rather than the current raw score. An already projected source amount is not uplifted again. The original historical artifact is unchanged.

An available FMI and policy rate survive a missing baseline; monetary adjustments stay null. A baseline without FMI can be displayed, but neither adjusted forecast is manufactured. None of these rates is calibrated predictive accuracy or a promise of revenue.

## 13. Forecast YoY and incremental growth

Comparisons against matching **PY actuals** are:

```text
baseline_forecast_yoy = baseline_revenue/prior_year_actual − 1
adjusted_forecast_yoy = adjusted_forecast/prior_year_actual − 1
legacy_adjusted_forecast_yoy = legacy_adjusted_forecast/prior_year_actual − 1
```

The PY actual must be positive and have `prior_year_actual_status=comparable`. A PY forecast must never substitute for it.

Comparisons against **PY forecasts** are:

```text
baseline_forecast_vs_py_forecast_yoy = baseline_revenue/prior_year_forecast − 1
adjusted_forecast_vs_py_forecast_yoy = adjusted_forecast/prior_year_forecast − 1
legacy_adjusted_forecast_vs_py_forecast_yoy = legacy_adjusted_forecast/prior_year_forecast − 1
source_legacy_adjusted_forecast_vs_py_forecast_yoy = source_legacy_adjusted_forecast/prior_year_forecast − 1
fmi_increment_vs_py_forecast_pp = 100 × (adjusted_forecast_vs_py_forecast_yoy − baseline_forecast_vs_py_forecast_yoy)
```

PY forecast matching checks company identity, positive amount, accepted current baseline, subject/scope/currency/multiplier, unchanged baseline amount/target, same native quarter and previous native fiscal year, source dates within matching windows. A changed baseline or conflicting period leaves the comparison unavailable. `prior_year_forecast_comparison_status` explains why.

`prior_year_forecast_target_start/end` are the **current target-window anchors used to validate the pair**, not the prior observation's actual dates. The validation checks the PY reported date against those anchors shifted back one year. The dictionary highlights this potentially confusing name.

A current stored observation for a prior target year is not necessarily the forecast known then. `prior_year_forecast_vintage` and `forecast_vintage` can be blank. All current dossier results are labelled `not_verified_historical_replay`; current extraction timestamps do not cure missing historical vintages.

## 14. Rankings and app interpretation

Provisional ranking uses rounded `display_fmi`, descending within `leaderboard_category`. Every dossier run reads the current company-list columns A/B. Only LUXE, PREMIUM and MASS_MARKET are accepted; column B overrides older input assignments. Unlisted brands keep their scores/forecasts but have blank category and no rank, with `not_in_current_category_list` status. The current list names 32 brands; 27 appear in the 59-brand delivery. Historical categories remain audit references, not fallback assignments. `leaderboard_category_source` records the exact source cell. Rank is `1 + number of strictly higher displayed scores`; ties share rank (1, 2, 2, 4). Missing FMI/category gives no rank. Missing forecast does not block a rank. Category changes do not affect the normalization cohort, FMI or uplift.

`leaderboard_scored_count` counts ranked rows; `leaderboard_member_count` includes delivered category rows without a headline. These ranks describe this delivery cohort, not all brands or the live app.

`app_category` and delivery Category use the same current column-B value: LUXE/PREMIUM/MASS_MARKET. Unlisted brands have both fields blank; no historical-category conversion is inferred. Native app rankings still require separate preparation and approval by the receiving team. Per-company native content must not contain stored `rank`/`brands`/`rankings`/`boardStatus`; the app composes them from its shared category table.

## 15. Worked example, illustrative only

The following values teach the arithmetic. They are not observations for any prospect.

Revenue 800 →900 →990 gives earlier growth 12.5% and latest growth 10%. Peer-median growth 17.5% →12% gives gaps −5 pp →−2 pp and improvement +3 pp. The common capped IR is 40; a social median change 1,000 →2,000 gives +100% lift and capped Social 100. Under the roadmap recovery rule, latest gap remains negative, so Strength is 70.

```text
weighted FMI = 0.50×40 + 0.30×100 + 0.20×70 = 64
with illustrative cohort minimum 40 and maximum 80:
display FMI = 70 + 28×(64−40)/(80−40) = 86.8
legacy rate = 0.03 + (64−60)×0.002 = 0.038 = 3.8%
new rate = 0.03 + 0.08×expm1((86.8−60)/40) ≈ 10.634%
```

With an illustrative untreated forecast of 100 million, raw-score legacy adjustment is 3.8 million and legacy adjusted forecast is 103.8 million. The exponential amount is approximately 110.634 million. The larger difference combines a changed curve **and a different score input**, so it is not a pure formula comparison. To compare formulas fairly, evaluate both at 86.8: linear legacy gives 8.36%, exponential gives 10.634%. Both use the baseline's currency/unit. If PY forecast is 90 million, baseline YoY is 11.111%; calculate adjusted YoY against that same 90, not prior actuals or the already adjusted amount.

If a dossier explicitly supplies the headline, reported mode uses that headline instead of this illustrative weighted result. If its Social component is missing, weighted mode has no headline. If only forecast is missing, FMI/display/rates survive but the amount does not.

## 16. What to change and how to reproduce

Edit source selections, accepted values and metadata in the dossier input Excel. Choose `score_method` explicitly. Edit weights, display bounds and uplift parameters in `policy.yaml`; record a new policy version when business policy changes. Then run from repository root:

```sh
uv run aily-project fmi-dossier --previews
```

Generated Excel/JSON, `calculation-audit.md` and comparison/coverage reports remain local. The audit documents every input prospect, including unavailable/excluded rows; JSON `rows` is the delivered subset. The current schema is enumerated in [DELIVERY_COLUMNS.md](DELIVERY_COLUMNS.md). Do not upload the envelope directly as per-company native JSON.

## 17. Implementation and historical references

- Current selection, context derivations and forecast arithmetic: `src/aily_project/services/fmi_dossier/excel.py`.
- Policy mathematics: `src/aily_project/services/fmi_dossier/policy.py` and `scripts/fmi-dossier/policy.yaml`.
- Current-demo period selector and optional lookup: `src/aily_project/services/fmi_dossier/forecast.py`.
- Card wording, comparison and ranking: `src/aily_project/services/fmi_dossier/presentation.py`.
- Upload handover: [fashion-momentum-agent-handoff.md](../fashion-momentum-agent-handoff.md).
- Separate automation and its controlled reference: [METRICS.md](../../fashion-momentum-index/docs/METRICS.md).
- [Roadmap historical rules](../reference/aily-superagent-roadmap/docs/research/wwd-fashion-momentum/weighted-delivery.md), sections Normalized component sentiments and Scoring rules and necessary detail. Saved locally; these explain historic differences, not a recurring source of current dossier measurements. [Snapshot contents and reproduction](../reference/aily-superagent-roadmap/README.md).
