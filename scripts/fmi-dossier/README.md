# FMI from dossiers

This is independent of `scripts/fashion-momentum-index` and its FMI service.
It has its own inputs, policy, scoring/uplift mathematics and Excel/JSON writer.
Changing either workflow's policy or running it does not change the other.

Detailed references:

- [Future-agent handover skill](skills/fmi-delivery/SKILL.md): workflow separation,
  accepted score/uplift decisions, source mappings, HTML regeneration and regression
  checks. In a new chat, ask the agent to read this file first if the skill is not
  listed automatically. The skill is saved with the repo, not installed globally.
- [Measures and calculations](docs/MEASURES.md): source selection, components,
  normalization, both uplift methods, forecast periods, YoY and ranking rules.
- [Delivery columns and app field contract](docs/DELIVERY_COLUMNS.md): every
  exported column, with recommended primary/detail fields and audit-only context.

## Small Excel for the HTML prototype

After generating the full delivery, run:

```sh
uv run aily-project fmi-dossier-html --previews
```

This reads the completed dossier delivery JSON and creates
`outputs/fmi-dossier-html/html-delivery.xlsx`: one `Delivery` sheet, 50 columns,
plus `html-delivery.json` with exactly the same typed fields and rows.
It never queries AWS, changes dossier inputs, recalculates scores, or overwrites
the full delivery. It copies scores, cards, identities, categories/ranks and social
history unchanged. The presentation-only `Q4 vs Baseline ’24/’25 (%)` headers
contain source **Q4 sales YoY v2**, not same-year forecast-baseline variance.
Missing sales YoY remains blank; there is no fallback to a baseline comparison.
The presentation-only `Q4 vs Baseline ’26 (%)`
header contains **exponential-adjusted forecast / matching PY forecast − 1**,
not the frozen legacy uplift. `Insights Descriptive` is a concise business summary
from available social history, latest historical sales YoY and the new forecast.
`Insights Statistics` retains calculation details; `Revenue methodology` retains
scope/provenance. The HTML shows only the business description, comparison table
and one comparison-basis note, not the audit paragraphs. Missing comparisons remain blank, even when
a legacy projection exists. Forecast amounts, currency/units, target, methodology
and evidence references are included in the same row.

Copy this Excel into `aily-ux-protos/wwd-2026-fashion-index/data/`, then select it
explicitly from `templates/v6-projection-explainer-sheet`:

```sh
python3 generate-data.py ../../data/html-delivery.xlsx
python3 generate-standalone.py
```

The workbook preserves the current importer's headers. Its current category values
are only LUXE, PREMIUM and MASS_MARKET; unlisted brands remain uncategorized.
The v6 importer preserves exact company-code case. Edit `email_domains` in Inputs
to control filenames: first domain gives `domainname.html`, or the stable
company-name slug gives `company-name.html` when no domain is supplied. Each brand
gets one file. Alternate domains remain in the manifest, with no `brand-` copies.
Missing domains and company keys are not guessed. Detailed revenue methodology
remains in Excel/JSON and the projection button uses `Projection label`
("Adjusted forecast vs PY forecast"). Its history
mixes historical 2024/2025 sales YoY with the new 2026 forecast comparison,
so `Historical comparison basis` and `Insights Statistics` state that distinction.
Do not describe these rows as one like-for-like historical growth series.

## Input

Previously published **scored** brands now have explicit `published_raw_fmi`,
`published_display_fmi`, `published_ir_score`, `published_social_score` and
`published_trend_score` input columns. They were copied once from
`weighted-delivery-1300.xlsx`, the source behind the existing v6 HTML. Their
`published_card_values` preserves its card copy, typed KPIs and history;
`published_source_reference` records the original cells. No prototype-repo file
is read on ordinary runs. These values take precedence for those 26 brands and
are not re-normalized when another brand is added. Dossier values remain intact
as alternative audit evidence. Clear `published_raw_fmi` only when deliberately
switching that brand back to dossier scoring. New/unpublished scores continue
through the dossier workflow. Forecasts, exact Light keys and current categories
are not overwritten by the historical snapshot.

Historical social/revenue fields are separate from locked score/card values.
Populated Inputs history takes precedence; published history only fills missing
values. Blank history cells in an older score workbook never erase supplied
history. The newer `handover/weighted-delivery-1606_2810.xlsx` history was
transcribed once into Inputs, with `source_snapshot_reference`, so ordinary runs
do not need that workbook or a cached comparison file to recover it. Genuine
missing years stay blank; zero is a valid supplied comparison, not missing.

Armani's new dossier is linked to its existing row, without duplication. It
explicitly reports missing main-account social history and incomplete revenues,
so its saved Q4 forecast is available but FMI/uplift remain unavailable.

`inputs/FMI_dossier_inputs.xlsx` was populated once from the brand reports and new
prospect documents now consolidated in `scripts/fmi-dossier/dossiers/<brand>/`, with supporting
sales workbooks. There is no separate `New prospects info` group: each report lives
in its brand folder. `source_document` points to its current location; the original
handover path remains in audit history where supplied.
All 94 prospect rows and original values are retained. Update
source cells only when documents are new/changed. No recurring Word parser runs.
Source dossiers and the populated input workbook stay local and are ignored by
Git because they include tenant measurements. Share these and the generated
delivery through the agreed private channel, separately from the source code.

Each row contains identity, report reference, reported FMI and IR/Social/Trend,
revenue observations/growth/peers, social metric/windows/medians/counts and forecast
baseline/target/scope/units. Dates, native amounts and fractions stay typed.
Blank is missing, not zero. Do not use an already adjusted projection as a baseline.
Additional source metrics can be carried through, with types/units declared in
the dossier field dictionary. No database revenue or social data feeds this score.

`score_method=reported` preserves the printed headline and its source qualifications.
`weighted_components` explicitly recomputes IR×50% + Social×30% + Trend×20%.
The weighted diagnostic and its difference from the reported score are always
shown when possible. Percentile/portfolio methods retain their source labels.
Source components are not silently converted into a different method.

## Run

From repository root:

```sh
uv run aily-project fmi-dossier --previews
```

The separate script alias is `uv run python scripts/fmi-dossier/run.py --previews`.
Both use the same dossier task. No AWS access is needed unless explicitly requested:

```sh
uv run aily-project fmi-dossier --query-missing-forecasts --previews \
  --forecast-start 2026-10-01 --forecast-end 2026-12-31
```

That option queries Light's company registry and `ai.light_financial_statements_forecast`
only for included dossier rows with a missing or unreviewed baseline amount.
Previously, any existing amount skipped the query even when review was incomplete;
that prevented Fendi's real forecast from being checked. Approved source baselines
are still preserved and are not refreshed automatically.
It initializes AilySettings once and verifies the tenant `ro` session. AWS tenant
profile/environment remain in `.env` or shell. Shared scanner has no established
forecast relation and is not queried for this fallback.

Candidates retain native period/date, raw amount, company, source row identity and
extraction time. Conflicting amounts, ambiguous identity or nonmatching native
target end do not become baselines. A database baseline needs explicit reviewed
`baseline_subject`, `baseline_scope`, `baseline_currency`,
`baseline_unit_multiplier`, `baseline_kind=unadjusted_forecast`,
`baseline_approved=TRUE` and target start/end. These existing Excel cells refer to
the forecast source's units/perimeter, not automatically the dossier revenue's.
If supplied source metadata conflicts, it remains unavailable. Inspect
`forecast_lookup_status`, `forecast_candidate_revenue` and candidate records;
complete the review cells and rerun. Querying never overwrites the input workbook.
Undated current forecasts remain scenario baselines, not strict historical replay.
Native monetary units are separate: `forecast_native_unit_multiplier` must be
verified when the table does not supply it. Conversion is native amount × native
multiplier ÷ `baseline_unit_multiplier`, so full EUR and EUR millions are not mixed.

Fendi was checked live in the tenant registry and forecast table on 2 November:
`company_code=FENDI`, currency EUR, native 2026/Q4 date 31 December 2026, revenue
517,275,000. This equals source N11's 517.275 million; approved baseline metadata
and calendar Q4 boundaries are now recorded in Inputs. Its FMI still uses the
dossier's LVMH Fashion and Leather Goods proxy; applying it to the brand-keyed
forecast is explicitly a hybrid business scenario, not a standalone prediction.

The workflow is agent-run: new/changed dossier → one-time update of the input
Excel → the CLI calculates and exports. No notebook or intermediate CSV is needed.
The previous dossier notebooks and CSV handoffs are preserved recoverably under
`.work/legacy-notebooks/` and `.work/legacy-data/`, outside the active workflow.
Neither this command nor its inputs read automated FMI JSON/CSV or delivery.

## Check each brand

`outputs/fmi-dossier/calculation-audit.md` has one section per input brand,
including prospects with missing results. It records the source document,
selected revenue/social periods, amounts, medians, peers, component scores,
weights/contributions, printed versus arithmetic FMI, normalization cohort and
both uplift calculations, with baseline/PY evidence and missing-data reasons.
The JSON's `calculation_traces` contains the same audit values; `rows` remains
the flat app delivery. Both come from the final service results, not a second
calculation path. Missing source detail is explicit, not guessed. Component
scores are dossier transcriptions, not independently recalculated observations.

Longchamp's new dossier fills its existing prospect row, without duplicating it.
Its FY2025 printed FMI is 49.72; components are IR 52.9959, Social 57.41 and
Strength 30, yielding a separate weighted diagnostic of 49.72095. The dossier
labels estimated revenue, suggested peers and fiscal alignment provisional.
Annual likes medians are 1,742 (2024) and 1,871 (2025); post counts are missing.
Its alternative five-month/percentile method is not the selected headline.
No matching Longchamp name/code was found in the configured Light registry on
2 November, consistent with the updated company list's `Aily light info=N`.
Forecast and native app company key remain unavailable; FMI and both policy
rates remain available. The supplied company list explicitly assigns PREMIUM.

### Current client-demo forecasts

The user accepts dossier measurements for scores and current Light forecasts
for this client-demo scenario. `baseline_approved` now records that acceptance,
not independent certification or a historical forecast vintage. Score values,
components, selected financial/social periods and previously accepted baselines
remain unchanged. No additional source-quality review blocks these FMI scores.

The agent reconciled `inputs/FMI index companies_tuesdaydinner.xlsx` once and
carried its Light-presence flags, explicit app categories and dinner flags into
the input Excel. All 23 Y and 9 N flags agree with the live brand registry.
Presence does not guarantee a revenue forecast. Spelling aliases preserve stable
IDs. Current category assignments are read from this workbook on every dossier run,
independently of those saved flags. Historical categories do not override column B.

Selection prefers a native quarter ending within seven days of 31 December 2026,
retaining its real fiscal year/quarter (which may be Q2/Q3). Otherwise an upcoming
native Q4 through 7 February 2027 is a labelled fiscal proxy. Its displayed start
is approximate calendar-month alignment, not a source-provided boundary.
Only three complete comparable monthly observations can support the fallback:
current month plus two, November 2026–January 2027 for this run. Never sum quarters
or invent monthly phasing. Neither Light financial forecast relation publishes
monthly observations; the monthly sales dimensions returned no prospect matches.

Native full currency units are accepted for this demo consistently with the
earlier 31 reconciliations; the table does not publish scale/reporting scope.
New baseline notes record this assumption. Display amounts use millions and
registry currency, with no FX conversion. Current snapshots are not historical
replay. Change the unit/period assumptions in Excel if required.

Previously requested parent fallback applies explicitly to Coach/Kate Spade
(Tapestry), Michael Kors (Capri), Calvin Klein/Tommy Hilfiger (PVH) and DKNY (G-III).
`baseline_is_parent_proxy` labels these group amounts, **not standalone brand
revenue**. `baseline_company_code` is the parent key; a missing brand's own
`company_code` stays blank. Hermès forecasts are stored under its verified registry
ticker `RMS.PA`, not registry company code `HERMES`. Its calendar Q4 2026 forecast
is EUR 8,769.4325894 million and PY Q4 forecast EUR 4,093.75 million, as supplied
by the current database. `forecast_native_company_code` retains the source alias;
the app key and baseline identity remain `HERMES`. Longchamp has no brand record.
Its FMI/rates remain available, but an adjusted amount needs a starting forecast.

`outputs/fmi-dossier/light-coverage.md` summarizes the company-list reconciliation,
forecast periods, parent use and missing results. The calculation audit and JSON
traces retain the detailed selection and source amounts. No app upload is run.

## Metrics and output

Selected scores normalize independently to 70–98 with half-up one-decimal rounding;
equal cohorts map to 84. Missing scores stay blank. `policy.yaml` owns the weights,
display bounds and both uplift parameters. Original/source display scores remain
separate from the newly normalized display score.

- Previous method: raw ≤60 →0; otherwise `0.03 + (raw−60)×0.002`.
- Approved exponential: `0.03 + 0.08 × expm1((rounded_display−60)/40)` above 60;
  otherwise zero. Calibrated on the legacy raw-score scale, but deliberately
  evaluated at the rounded normalized score. At 60+ it starts at 3%, with the
  legacy's initial slope of 0.2 percentage points per score point, then accelerates.
  There is **no 11% cap**: display 70–98 gives about 5.27–15.69%; 100 gives 16.75%.
  The threshold, intercept, scale, score span and exponent are editable in
  `policy.yaml` (policy v3). Missing scores stay missing. FMI scoring is unchanged.
- For each method: adjustment = untreated baseline × rate; adjusted forecast =
  baseline + adjustment. Matching prior-year actuals also support forecast YoY.

The source sales workbook may apply its previous formula to its own normalized
score. Its original display/projected forecast is retained for comparison and is
not a baseline to uplift again. Rates are business scenarios, not calibrated
predictive accuracy. Changing the normalization cohort changes uplift; 70–98
gives every scored brand positive exponential uplift.

Excel A–AL follows the original weighted-delivery's 38-column order and headers.
Column L retains that header but contains the **single verified Light retrieval
key**, not the historical list of brand/parent aliases. AB–AL is the frozen source
sales/social snapshot, including source legacy forecasts and potentially stale
narratives. The **new exponential scenario starts at AM**, followed by context and
audit columns. Do not use the historical AL ratio as the new forecast YoY.
JSON field keys stay stable; `fields` now declares each column's `source_kind`,
`source_reference`, `source_fields`, type/unit and derivation. The detailed
[column guide](docs/DELIVERY_COLUMNS.md) maps old headings to these keys and sources.

### PY forecast comparisons

The input now retains a one-time, read-only Light forecast snapshot for the
previous comparable period. Current native amounts are first reconciled to the
approved dossier baseline in its stated currency/millions. Select the same
`company_code`, native quarter and previous fiscal year within the dossier's
current/prior target windows. Burberry and Ralph Lauren's December observations
are fiscal Q3, not fiscal Q4; their native labels and dates remain visible.
Do not replace dossier scores, periods or baselines with these comparison values.

`prior_year_forecast` is in the same display units as `baseline_revenue`.
`baseline_forecast_vs_py_forecast_yoy`,
`adjusted_forecast_vs_py_forecast_yoy`,
`legacy_adjusted_forecast_vs_py_forecast_yoy` and
`source_legacy_adjusted_forecast_vs_py_forecast_yoy` each calculate
`matching amount / prior_year_forecast - 1`. Rates are fractions.
`fmi_increment_vs_py_forecast_pp` is 100 × (exponential YoY − baseline YoY).
Existing `*_forecast_yoy` columns remain comparisons against PY **actuals**,
now explicitly labelled. A prior-year forecast never substitutes for an actual.

Light supplies current snapshots for prior target periods, not archived
forecasts as originally issued in the prior year. `reported_date` is a target
period end, not a forecast vintage. The comparison inherits the reviewed
brand-keyed baseline scope; underlying model/reporting provenance is not supplied
by Light. Missing/conflicting matches or changes to company, scope, unit,
currency, baseline amount or period leave comparisons blank with a status.
Original FMI and uplift calculations remain unchanged. On 2 November, 31 input
baselines were reconciled; the extraction evidence stays under `.work/`.

### Category rankings

Edit categories in column B of `inputs/FMI index companies_tuesdaydinner.xlsx`.
Every dossier run reads columns A/B (`--categories` selects another file).
Only LUXE, PREMIUM and MASS_MARKET are accepted. These assignments populate both
delivery Category (Z) and `app_category`, with the exact source cell recorded in
`leaderboard_category_source`. The current list names 32 companies, of which 27
are in the 59-brand delivery. The other 32 delivered brands retain all their
scores/forecasts, but have blank category and no rank; their assignment status is
`not_in_current_category_list`. Add their names and a category to this workbook
if they should be ranked. Original input/historical category cells remain audit
references and cannot override the current list. No taxonomy mapping is guessed.

`leaderboard_rank` ranks rounded `display_fmi` descending within the current
delivered category. Ties share competition rank (1, 2, 2, 4). Missing FMI/category
means no rank; missing forecast does not block a rank. Scored/member counts and
provisional status accompany each rank. Parent hybrids retain their qualifications.
These boards cover **this dossier delivery**, not every historical benchmark
brand or the live app. JSON root `leaderboards` contains sorted rows and counts
for the same categories; rows contain the same rank shown in Excel. A stable
`brand_id` is not a native app domain ID. These are handover data, not a directly
publishable ranking payload. The receiving team owns native taxonomy/ID mapping
and any upload. No live rankings are read or changed.

`source_legacy_uplift_fraction` reproduces the previous formula on the original
`source_display_fmi`. `source_legacy_adjusted_forecast` applies that rate to the
untreated baseline; `source_projection_difference` checks it against the cached
source projection. These are diagnostics, distinct from the raw-FMI legacy
scenario and the new exponential scenario. Missing/unchecked baselines stay blank.

Missing descriptive growth/gap/lift metrics are derived from eligible values in
the Excel where possible; printed values take precedence. These derived context
fields never change a reported headline or invent missing components.

Final files: `outputs/fmi-dossier/dossier-calculated-delivery.xlsx` and `.json`.
Excel has one flat Delivery sheet with scores/uplifts first and a Column guide
sheet documenting every field, its source, calculation, units and delivery use.
Filter the guide's Delivery use column to Recommended delivery. **AW is the new
adjusted Q4/selected-target forecast versus PY forecast; AV is before uplift and
AX is the gain in percentage points. AL remains frozen historical YoY versus sales.**
Read AM for the selected fiscal/calendar target. JSON contains the same
typed `rows`, an independent `fields` dictionary, `policy` and `cohort`. Partial
rows with available dossier/source data remain visible; all identities remain in
the input. Missing forecasts do not erase FMI or uplift rates. Lookup audit and
preview images stay in the output's hidden `.work/` folder.
Excel timestamps are UTC at native spreadsheet millisecond precision; JSON
retains the recorded ISO timestamp. Neither means a verified forecast vintage.

## Weighted reference and app handover

All roadmap FMI documents, prompts, skill/configuration and historical delivery
inputs/builders are saved locally in
[reference/aily-superagent-roadmap](reference/aily-superagent-roadmap/README.md).
This frozen archive is separate from the active dossier logic; the sibling
repository is no longer needed for reproduction or historical comparison.
The archived `update-fashion-momentum` skill and `prospect-update-guide.md`
were consulted. The supplied `weighted-delivery-1606_2810.xlsx` agrees with the
roadmap's weighted JSON on all 74 brands × 38 fields (2,812 cells). The Word
dossiers and roadmap Markdown reports are distinct artifacts: this verifies
delivery values, not byte-identical reports or independently verified data.

Printed dossier headlines/components are preserved,
not replaced with roadmap calculations or historical user revisions. The roadmap
Strength rule can yield 80 where a dossier gives 70; it also contains Estée Lauder
score revisions, the accepted Nordstrom mixed-period proxy, ME+EM's display
override and RIMOWA's manual descriptor. They remain historical reference only.

One-time comparison snapshot (repeat only for a new historical reference):

```sh
uv run python scripts/fmi-dossier/check_weighted_reference.py
```

It reads the archived local weighted workbook and JSON by default, checks all
delivery cells, then saves `outputs/fmi-dossier/.work/weighted-reference.json`.
Use `--workbook` / `--roadmap` only to check a newly supplied historical reference.
Normal CLI delivery runs use that snapshot for comparison only; scoring does
not depend on it. Keep an existing accepted cache unchanged unless explicitly
refreshing it. With an alternative output folder,
run the snapshot command with `--output <folder>/.work/weighted-reference.json`.
When absent, comparison is explicitly marked unchecked/not matched.

For a fresh local output folder, run the comparison check above before
`uv run aily-project fmi-dossier`. Keep the accepted input workbook available;
it and the private dossiers are intentionally git-ignored and must be transferred
securely to a new checkout. The archive removes the sibling-repo dependency,
not the requirement for project dependencies and the spreadsheet runtime.

The same flat Delivery sheet includes core insight, component descriptors,
insights and typed KPI values/labels, historical scores/components/periods,
differences and reasons. Original classifications and numeric source precision
remain separate from app sentiments. `weighted-comparison.md` explains differences.

`company_code` is the verified `light.light_companies.company_code` used to retrieve
the company in Light. It is not the ticker, shared symbol, or a parent revenue
subject. Keys and verification status/source/date are recorded in Inputs and
delivered unchanged. Existing input-code aliases retain the actual Light name;
unresolved brands keep null keys with specific statuses, not invented keys.

Share the Excel and matching typed JSON privately. The receiving team owns app
presentation and upload following `fashion-momentum-agent-handoff.md`. No native
approval/domain/category gates block the delivery, and normal runs no longer
generate `app-upload-plan.json` (the previous file is retained under `.work/`).
The flat JSON is a data handover, not a directly loadable native `content_json`
object. No loader, database/S3 write, live ranking update or deployment runs here.
AWS revenue/social automation and historical reference originals are untouched.

CLI `--inputs`, `--policy` and `--output` select alternative paths. Notebook path
overrides are `FMI_DOSSIER_INPUTS_PATH`, `FMI_DOSSIER_DATA_DIR` and
`FMI_DOSSIER_OUTPUT_DIR`. Only the managed export runtime settings `FMI_NODE` and
`FMI_NODE_MODULES` are shared technical configuration, not business policy.
