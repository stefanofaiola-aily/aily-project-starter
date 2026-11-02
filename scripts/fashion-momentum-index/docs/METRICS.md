# FMI metrics and output contract

## Automated Light/shared score

The top-level notebooks use authenticated database measurements selected by
`FMI_inputs.json`. They retain the dossier-aligned dates, scopes and method
parameters previously stored in that JSON. Internal names such as
`calculation_mode=dossier` describe those parameters, not Word-sourced amounts.
They calculate one headline per brand using available approved comparable peers;
missing peers are listed rather than blocking valid remaining peers.

The controlled policy reference is below. Per-brand JSON can instead specify
published comparable growth, comments, different windows, company-growth or
assumed Trend, and percentile/portfolio methods. The restored notebooks preserve
those choices and label them in the output; this split does not replace them with
the controlled defaults. Original unavailable percentile cohorts are not invented.

```text
growth_fraction = current_revenue / prior_revenue - 1
gap_pp = 100 × (brand_growth_fraction - peer_median_growth_fraction)
IR = clip(50 + 5 × latest_gap_pp, 0, 100)
Social = clip(50 + 100 × (current_median_likes/baseline_median_likes - 1), 0, 100)
trend_change_pp = latest_gap_pp - earlier_gap_pp
raw_fmi = 0.50 × IR + 0.30 × Social + 0.20 × Trend
```

Trend rule order: change >+2 pp →70; change <−2 pp →30; otherwise both
gaps ≥+5 pp →80; otherwise →50. Missing required components prevent the total,
without neutral substitution or weight redistribution. Unrounded raw classification
is High ≥70, Medium ≥60, Neutral ≥40, otherwise Low.

Controlled-policy show social: reviewed collection posts on days 0…+7, baseline pooled
−30…−1 and +8…+37, at least five usable likes observations in each sample.
Annual comparisons require explicit comparable windows, at least 20 usable posts
per year and three common months. Capture filtering precedes deduplication.
Unknown/post-cutoff captures cannot become strict historical metrics. Missing
likes stay missing; comments/views/followers are context, not substitute scores.
Source and reporting-scope evidence governs revenue eligibility. Fiscal labels
are not automatically calendar periods or additive quarters.

Normalization and both policy uplift formulas below also apply to this route,
but its forecast requires a positive, compatible, unadjusted database baseline
and the route's availability/target checks. Strict replay requires a dated eligible
vintage before cutoff. Dossier amounts are never substituted. Automated JSON is
a flat row array; its field definitions live in `services/fmi/contract.py` and
`flat_delivery.py`. Optional context never changes FMI weights.

## Dossier Excel score

The independent `scripts/fmi-dossier` workflow reads its own one-time Excel,
not a live DB query. Source values are refreshed only for new/updated documents.

- reported: raw_fmi equals reported_fmi exactly, including printed precision.
- weighted_components: raw_fmi = IR×0.50 + Social×0.30 + Trend×0.20.
- weighted_component_fmi always shows that diagnostic when all components exist.
- reported_component_difference = diagnostic − reported headline. Rounded printed
  components may not reproduce the report headline exactly.

Some reports use capped components, others component percentiles, portfolio
weights, parent finance, comments or TikTok. Preserve dossier_score_basis,
scope and social_metric. Do not mix component values with another method's
measurements. Do not recompute a percentile score without its original cohort.
A reported portfolio total may exist without separate group component scores.
Percentile headlines receive no invented absolute raw classification.

For weighted absolute scores: High ≥70, Medium ≥60, Neutral ≥40, otherwise Low.
Reported dossier category thresholds can differ; these are not rewritten in the
source documents. Missing measurements remain blank; available components survive.

## Meaning of the underlying measurements

Revenue growth = current/prior − 1 (fraction). Earlier/latest require corresponding
source periods. Latest gap_pp = 100×(brand growth − peer-median growth).
Trend change_pp = latest gap − earlier gap. Peer median uses the dossier-selected
peers; peer_observations retains per-peer figures and source scope. There is one
headline per prospect, not a headline per peer pair.

The source's common capped rules are IR = clip(50+5×gap_pp,0,100) and Social =
clip(50+100×metric_lift_fraction,0,100). Metric lift = current median/baseline median−1.
The source Trend rules and alternatives vary. This route accepts their stated
Trend component rather than silently substituting the roadmap's revised rule.

Social windows are the report's windows: often show day through +7 versus the
preceding 15 days, full-year comparisons, matched months, or a portfolio proxy.
Captured likes/comments are accumulated snapshots, not activity earned only
inside the window. Counts describe samples, not statistical confidence. Units and
platforms remain explicit. New-prospect annual social is not replaced with its
separate runway sample. Fendi/LVMH/Marc Jacobs/New Balance percentile context uses
July, August, September, October and December in 2024/2025.

## Display normalization

Separately within each workflow's included, available selected headlines:

```text
display = 70 + 28 × (raw − cohort minimum)/(cohort maximum − cohort minimum)
```

Round half-up to one decimal. Equal/single-score cohorts map to 84; empty cohorts
stay empty. JSON records membership and extrema. Source originals and historical
source display indices remain separate. Current normalization can therefore differ
from an older weighted-delivery workbook.

## Both uplift scenarios

New method, using the rounded display score:

```text
new rate = 0.11 × expm1(8×display/100)/expm1(8)
```

Existing code's legacy method, using the selected raw score:

```text
legacy rate = 0                         when raw ≤60
legacy rate = 0.03 + (raw−60)×0.002      otherwise
adjustment = baseline × rate
adjusted forecast = baseline + adjustment
```

The supplied Sales & Social workbook instead applies its legacy formula to its
own normalized source FMI. Keep source_display_fmi and source_projected_forecast
for that exact historical comparison; neither feeds the new calculation.
Sales Baseline ’26 (column N) is the untreated baseline. Sales Q4 ’26 (column M)
is already projected: applying uplift to M would double-adjust it.

A dossier baseline needs positive amount, unadjusted_forecast kind, source/subject/scope,
currency/multiplier, target dates and baseline_approved. Undated dossier forecast
snapshots are allowed for this requested scenario, explicitly not strict replay.
An unavailable baseline leaves the score/rates populated but adjusted amounts blank.
Rates are business scenarios, not calibrated predictive accuracy. Dynamic cohort
rescaling changes uplift for an otherwise unchanged brand. The 70–98 range gives
every available display score positive new uplift.

Forecast YoY = forecast/prior-year actual − 1 only when prior_year_actual_status
is comparable. Native fiscal/retail Q4 is not automatically calendar Oct–Dec.

## App field dictionary

The dossier JSON fields array is the full machine-readable output dictionary; rows uses
those exact field keys. Excel uses the same ordering/types with human labels.
Groups: FMI, Forecast, Social, Revenue and peers, Identity and evidence.

Important keys:

| Key/group | Meaning and unit |
|---|---|
| raw_fmi, display_fmi | Selected source score and current display, 0–100 |
| IR/Social/Trend score, weights, contributions | Report components; weights are fractions |
| reported_fmi, source_original_fmi, source_display_fmi | Immutable source context unless you edit the input |
| weighted_component_fmi, reported_component_difference | Weighted arithmetic check, score points |
| oldest/earlier/latest_revenue | Source amounts × unit_multiplier = full currency units |
| earlier/latest_growth, peer-median growth | Fraction growth, not percentage-point values |
| earlier/latest_gap_pp, trend_change_pp | Percentage points |
| used_peer_names, peer_observations | Report-selected benchmark and individual figures |
| current/baseline_median_metric and posts | Captured per-post metric medians and usable counts |
| social_lift_fraction, source_social_2024/2025/2026 | Source lift fractions; windows may differ |
| baseline_revenue and adjusted forecasts | Native amounts, baseline_currency and baseline_unit_multiplier |
| uplift_fraction, legacy_uplift_fraction | Fractions, e.g. 0.04 means 4% |
| source_projected_forecast | Already adjusted source comparison, never fresh baseline |
| source_sales_2023/2024/2025 | Supplemental period amounts, source fiscal/calendar labels |
| forecast_target_label/start/end | Native selected target; proxy boundaries labelled in notes |
| baseline/adjusted_forecast_yoy | Fraction growth versus verified comparable prior actual |
| source_document, score/period evidence, limitations | Traceable report/workbook references |
| component/FMI/forecast statuses and missing_reasons | Why a value is blank |
| historical_eligibility | Dossier snapshot, not verified point-in-time replay |

Context values do not alter the headline in reported mode. To change the headline,
edit reported_fmi, or deliberately select weighted_components and edit components.
No engagement rate, substitute metric, fabricated revenue or missing forecast is
invented. Additional columns added to the input are carried through; add their
unit/type to `services/fmi_dossier/excel.py`'s field definitions if they are new
numeric metrics. Neither workflow modifies the other's input or calculated output.

The dossier policy and calculation functions are independent, not imports of
automated FMI code. Its optional database lookup fills only missing reviewed
forecast baselines, never score measurements. Full instructions are in
[the standalone dossier README](../../fmi-dossier/README.md).
