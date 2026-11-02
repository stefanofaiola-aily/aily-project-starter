---
name: fmi-delivery
description: Maintain this project's independent FMI database automation, dossier Excel/JSON delivery, and compact delivery for the WWD HTML prototype. Use for score reconciliation, source/column questions, category or dossier updates, uplift changes, and HTML refreshes; not for app deployment.
---

# FMI delivery handover

Durable operating context for `aily-project-starter` and its WWD prototype.
Read before changing FMI workflows. Paths below are relative to the project root
unless stated otherwise. Locate sibling repositories from the workspace rather
than assuming a particular user's absolute path. This skill is stored with the
project for portability; if it is not in the available-skills catalog, explicitly
read this file as the handover document. It is not installed globally.

## Choose the workflow first

| Workflow | Editable input | Run | Output |
| --- | --- | --- | --- |
| Automated database FMI | `scripts/fashion-momentum-index/inputs/FMI_inputs.json`, its own policy | `01_extract.ipynb` → `02_score.ipynb` → `03_delivery.ipynb` in that folder's `notebooks/` | `outputs/fmi/weighted-delivery.xlsx` and `.json` |
| Independent dossier FMI | `scripts/fmi-dossier/inputs/FMI_dossier_inputs.xlsx`, `scripts/fmi-dossier/policy.yaml` | `uv run aily-project fmi-dossier --previews` | `outputs/fmi-dossier/dossier-calculated-delivery.xlsx` and `.json`, calculation audit |
| Compact HTML delivery | Completed dossier delivery JSON; no new measurements | `uv run aily-project fmi-dossier-html --previews` | `outputs/fmi-dossier-html/html-delivery.xlsx` and `.json` |
| HTML in sibling `aily-ux-protos` | Compact workbook copied into `wwd-2026-fashion-index/data/` | Current v6 generators below | `wwd-2026-fashion-index/html-for-upload/` and `html-for-upload.zip` |

Keep these detached: no shared runtime scoring/policy imports, overwriting one
another's inputs, or automatic comparison refreshes. Do not merge dossier scoring
into the notebooks or replace automated database measurements with document data.
Prefer the existing input → run → output flow. Do not introduce another
architecture, recurring Word parser, complex review-JSON layer or public collection
of intermediate files to solve a presentation issue.

Inspect Git status and applicable AGENTS instructions before editing. Preserve user
changes. Read the relevant maintained reference, not just historical conversation:

- Dossier work: [README](../../README.md), [MEASURES](../../docs/MEASURES.md),
  relevant entries in [DELIVERY_COLUMNS](../../docs/DELIVERY_COLUMNS.md).
- Automated work: [README](../../../fashion-momentum-index/README.md),
  [HOW_IT_WORKS](../../../fashion-momentum-index/docs/HOW_IT_WORKS.md),
  [METRICS](../../../fashion-momentum-index/docs/METRICS.md).
- App/schema questions: [agent handoff](../../fashion-momentum-agent-handoff.md).
- Historical rules: [local roadmap snapshot](../../reference/aily-superagent-roadmap/README.md).
  It includes original FMI skills, methods and builders, for reference only. Do not
  run old builders over current delivery or install the historical sync workflow.
- HTML work: current README/AGENTS and v6 instructions in the sibling prototype.
  The previously discussed saas-app PR is integration context, not permission to
  upload private data or deploy an app.

## Dossier source and score selection

The handover brand reports and new-prospect documents were consolidated into
`scripts/fmi-dossier/dossiers/<brand>/`. Data were transcribed once into the
`Inputs` sheet of `FMI_dossier_inputs.xlsx`. Update the relevant brand when a
document is new/changed or the user deliberately changes an input; do not parse
all Word files on every run. Preserve source references, periods, metric definitions,
method and limitations. Match existing `brand_id` before adding a row: Armani and
Longchamp must not be duplicated.

Dossier revenue/social data are accepted report/demo evidence, not a fresh database
reconstruction or certified actuals. Keep source labels. The separate automation
retains its own review and eligibility rules.

Published scored brands use saved `published_raw_fmi`, `published_display_fmi`,
`published_ir_score`, `published_social_score`, `published_trend_score`,
`published_card_values`, `published_source_reference` first. The accepted snapshot
came from `weighted-delivery-1300.xlsx`, the existing HTML baseline. Do not
re-normalize old displays when a brand is added or silently select another dossier
revision. Clear the published selection only for a deliberate method change.
Alternative dossier components and differences remain diagnostics.

Other brands: `score_method=reported` preserves the supplied headline;
`weighted_components` computes `0.50*IR + 0.30*Social + 0.20*Trend`. All components
are required for the weighted diagnostic; no neutral fill or weight redistribution.
A reported headline can survive incomplete detailed evidence. Do not recompute
source components from rounded context or impose automated windows/Trend rules.

One brand has one selected FMI, not one per peer pair. Dossiers preserve source
peers. For automated partial-peer behavior, inspect the current service/policy:
use comparable usable approved peers, disclose used/missing peers, and never fill
a missing peer's growth with zero.

New/unpublished displays use `70 + 28*(raw-min)/(max-min)` over the selected
headline cohort, rounded half-up to one decimal. Equal/single cohorts give 84.0;
missing scores remain null. Published displays stay locked. Cohort membership can
still change an unpublished brand's display/uplift. Categories do not change the
normalization cohort or weights.

## Forecast and uplift: distinguish the bases

The approved dossier policy at this handover is `fmi-dossier-v3`. Read its YAML and
`src/aily_project/services/fmi_dossier/policy.py` before changing it.

```text
new uplift = 0                                      if rounded display FMI <= 60
new uplift = 0.03 + 0.08*expm1((display FMI-60)/40)  otherwise
legacy diagnostic = 0                              if selected raw FMI <= 60
legacy diagnostic = 0.03 + 0.002*(raw FMI-60)        otherwise
adjusted forecast = untreated baseline * (1 + selected uplift)
adjusted vs PY forecast = adjusted forecast / matching PY forecast - 1
FMI increment in pp = 100 * (adjusted/PY YoY - baseline/PY YoY)
```

The exponential is calibrated on the legacy raw-score scale but deliberately
applied to rounded **display** FMI. It is not the superseded capped 11% curve
`0.11*expm1(8*score/100)/expm1(8)`. Source legacy calculations can use original
display FMI; retain them separately from raw-score legacy diagnostics. Never
compound uplift scenarios or uplift an already adjusted projection. These are
commercial scenarios, not calibrated predictive accuracy. The 70–98 range makes
every available score's new uplift positive.

FMI and its policy rate can exist without a baseline. Missing/invalid baseline or
missing matching PY evidence can leave amounts/comparisons unavailable separately.
Keep specific statuses, not invented neutral results.

Separate missing/unreviewed dossier forecast lookup:

```sh
uv run aily-project fmi-dossier --query-missing-forecasts --previews \
  --forecast-start 2026-10-01 --forecast-end 2026-12-31
```

Dates are the original Q4 2026 demo, not rolling targets for future runs. This
returns candidates; it does not automatically overwrite Excel or refresh accepted
baselines. Review/save missing inputs explicitly. It does not replace dossier
revenue/social measurements.

Use `ai.light_financial_statements_forecast` with identity from
`light.light_companies`. `reported_date` is target-period end, not publication
time. Preserve native fiscal year/quarter, currency, multiplier, subject, proxy
scope and selection method. Do not call retail-calendar quarters calendar Q4,
divide quarters into invented months, sum conflicting rows, or infer historical
vintages from extraction timestamps. See MEASURES for native-quarter/proxy/three-
complete-month selection rules.

PY forecast and PY actual are distinct denominators even when amounts coincide.
A current snapshot of an earlier-year target is not the forecast known that year.
Keep `not_verified_historical_replay` where applicable. Parent scenarios must be
labelled; a parent key is not the brand app key and repeated group totals must not
be summed as independent brand revenue.

## Identity, categories, units and database safety

- App `company_code` is the exact case-preserved Light registry retrieval key,
  not ticker, shared symbol, domain or generated slug. Keep these separate.
- Company-list column B assigns only `LUXE`, `PREMIUM`, `MASS_MARKET`.
  Unlisted brands are uncategorized/unranked. Rank is descending rounded display
  FMI with competition ties (1,2,2,4); delivery ranks are not live app ranks.
- Growth, lift, weights and uplift are fractions; gaps are pp; scores are 0–100.
  Amounts need currency/multiplier. Revenue and forecast multipliers can differ.
  Missing is not zero. Do not infer views, followers, engagement rates, histories
  or complete sample denominators when sources do not support them.
- Automation uses separate `demos` tenant and `shared` scanner AWS profiles in
  shell/settings, never hardcoded credentials. Initialize AilySettings once per
  entry point. Preserve tenant `ro`; use `Dal.shared_db` and verified
  `default_transaction_read_only=on` for shared exploration. Discover relations
  first, then bounded SELECTs with explicit columns; no DDL/DML.
- Shared financial view: `normalized.v_finance_financial_statements`, matched by
  symbol to reviewed ticker. Retain source/correction/scope/unit evidence. FMP,
  interpolated and Perplexity underlying rows are not all reported observations.
- Social starts with Instagram post/profile views and verified history relations.
  Strict replay filters capture eligibility before deduplication. Unknown timing
  or later captures cannot supply historical metrics; missing likes are not zero.

## HTML contract: fixes that must survive

Full dossier JSON has `rows` plus policy/cohort/fields/audit metadata; compact JSON
also has `rows` and field definitions. Neither envelope is native per-company app
upload JSON. Compact Excel is one Delivery sheet, 50 columns at this handover;
full Excel has Delivery and Column guide. Use stable keys/dictionary descriptions,
not remembered column letters.

`src/aily_project/services/fmi_dossier/html_delivery.py` selects/remaps completed
values without querying AWS or recalculating FMI/uplift. Legacy headers are kept
for importer compatibility; their actual meaning is:

| Compact field / header | Full source and meaning |
| --- | --- |
| `source_q4_vs_baseline_2024` / Q4 vs Baseline ’24 | `source_q4_sales_yoy_2024`: supplied historical Q4 sales YoY |
| `source_q4_vs_baseline_2025` / Q4 vs Baseline ’25 | `source_q4_sales_yoy_2025`: supplied historical Q4 sales YoY |
| `source_q4_vs_baseline_2026` / Q4 vs Baseline ’26 | `adjusted_forecast_vs_py_forecast_yoy`: new adjusted forecast vs matching PY forecast |
| `source_social_2024/2025/2026` | Supplied source social lifts; preserve source windows |
| `source_insights_descriptive` / Insights Descriptive | Concise business summary generated from final available history and forecast |
| `source_insights_statistics` / Insights Statistics | Calculation explanation retained in Excel/JSON, not appended to visible description |
| `revenue_methodology` | Scope/provenance audit detail retained in Excel/JSON, not appended to visible description |

Never fall back from historical sales YoY to same-year forecast-baseline variance:
that previously produced misleading 0% for Fendi. Missing years stay blank/Pending;
real supplied zeroes remain valid. Input history takes precedence; blank older
published snapshots must not erase it. Newer source history was transcribed once
with `source_snapshot_reference`; ordinary runs do not re-read old workbooks.

The dialog shows descriptive insight, history table and one `Historical comparison
basis` note, not the audit paragraphs. The 2024/25 rows are sales YoY and 2026 a
forecast comparison, not homogeneous actual-sales history. App **Trend / Peer
Trajectory** is IR (50%); internal `trend_score` is **Strength / Commercial Pace**
(20%). Do not swap them by name. Published main-card copy/KPIs stay preserved
separately from regenerated forecast-dialog copy.

## HTML generation without duplicates

Copy the compact workbook into sibling
`aily-ux-protos/wwd-2026-fashion-index/data/html-delivery.xlsx`, not the full
delivery/dictionary. From `templates/v6-projection-explainer-sheet/` there, run:

```sh
python3 generate-data.py ../../data/html-delivery.xlsx
python3 generate-standalone.py
python3 -m unittest test_delivery
```

Saved workbook values feed `tenants.json`, then standalone HTML/manifest/ZIP. The
importer does not calculate Excel formulas. Use typed saved values and the managed
writer; verify cached results if formulas are introduced.

Exactly one page per delivered brand: first supplied `email_domains` gives
`domainname.html`; absent domain gives the stable company-name/brand-ID slug.
Do not create `brand-brandname.html` duplicates or alternate-domain pages. Keep
aliases in `manifest.json`. Do not guess domains or Light keys. Validate filename
safety/collisions before removing obsolete generated pages. ZIP also has separate
coming-soon page and manifest. Read generator requirements and respect permission
boundaries for sibling writes/network. Distribution/app upload is a private-channel
handoff, not an automatic publish step.

## Verification and last accepted checkpoint

For behavior changes add isolated unit-marked tests; run `uv run pytest`,
`uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check`, and
`git diff --check`. Prototype changes also need its isolated tests. Verify
Excel/JSON typed-cell parity, null vs zero, stable row IDs, unchanged unaffected
scores, history/forecast payloads, one page per row, manifest/ZIP inventory,
formula errors, workbook and browser visuals. Check affected and missing-data
brands. Report checks actually performed.

Checkpoint **2 November 2026, not permanent counts**: 59 delivery rows, 41 FMI
scores, 39 adjusted forecasts, 35 adjusted/PY comparisons; 46 domain pages plus
13 company-name pages. Full dossier delivery was unchanged by the final
history/description presentation fix. Project checks passed with 445 tests and
2 skipped; prototype checks passed with 12 tests.

Fendi is a regression example, not a hardcoded override: published raw 47.3,
display 81.6, IR/Social/Strength 50.4/53.6/30; new uplift about 8.728%; historical
revenue comparison −2.92% (2024), −3.43% (2025); new adjusted/PY comparison about
−0.01% (2026). Social history was +38.34%, +3.62%, −41.61%. Source legacy 7.32%
and raw-score legacy diagnostic 0% use different bases. Recheck inputs/results if
the user deliberately changes policy/evidence rather than forcing these values.

Common regressions: selecting percentile/dossier revisions instead of accepted
scores; re-normalizing old displays; erasing history with blank published cells;
showing baseline variance as sales YoY; appending audit text to description;
mixing PY actuals/forecasts; duplicate HTML names; stale outputs when scores are
missing. Diagnose the affected layer before altering other layers.

Keep populated inputs, dossiers, tenant extracts and generated outputs out of Git.
Replication requires their secure transfer, not just a clone. Reuse the existing
guides and generated calculation audit rather than proliferating permanent docs.
This skill grants no permission to commit, push, upload or deploy. Update this
handover when approved decisions change; do not treat checkpoint data as live.
