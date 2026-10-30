# Controlled FMI pipeline and operating plan

For full prospect discovery, report-derived metadata and ungated database
collection, see [FMI source data collection](FMI_DATA_COLLECTION.md). Data collection
and score-release approval are separate operations.

## Outcome

The service is `src/aily_project/services/fmi`. Three new notebooks in
`notebooks/controlled` call the existing project's single Click CLI. Legacy
notebooks, legacy functions and historical deliveries are retained unchanged.
No app UI/deployment is included. Generated extracts, reviews and outputs belong
in ignored `outputs/fmi-controlled/`, never in git.

1. `01_extract_review`: create/migrate Excel inputs and extract authenticated data.
2. `02_raw_score`: reviewed components, raw headline FMI and pair diagnostics.
3. `03_delivery`: refresh the same calculation, rescale the selected cohort,
   apply eligible forecasts, write Excel, app JSON, resolved policy and coverage.

Changing reviews requires rerunning steps 2 and 3. Step 3 recomputes from current
inputs rather than trusting a potentially stale score cache. The input, snapshot
and policy hashes identify each deterministic run. Output workbooks are generated
views, not places to edit measurements. Derived headline cells contain formulas;
app records use the same canonical service results. Native Excel application
testing is separate from artifact-engine recalculation.

## Historical reconciliation

The historical delivery pack and roadmap are audit evidence, not production
measurement inputs. Prior financial reports mix consolidated, brand, retail and
DTC scopes. A consolidated database amount cannot be relabelled as a segment.
The roadmap and legacy notebook differ in Trend method and cohort membership;
display scores therefore need not match. Historical sales used a threshold/linear
uplift; the new exponential policy deliberately replaces that scenario.

The historical pack contains formula errors and stale narratives already reported
in the handover audit. These files are not repaired or overwritten. New narratives
are generated from current final values. Reports contribute mappings, scope clues,
show dates and evidence only. Revenue and likes come from authenticated DB data.

## Inputs and responsibilities

`FMI_inputs.xlsx` uses exact stable field keys. Do not rename headers. All empty
decisions remain tasks, not defaults. There are no editable source amounts/likes.

| Sheet | Human decisions | Required evidence |
|---|---|---|
| Entities | Light code, ticker, shared symbol, aliases, financial subject, scope, explicit proxy/label, handle/profile | identity and scope mapping approval |
| Peers | approved set, calendar/scope comparability, rationale/limitations | peer and fiscal alignment review |
| Analyses | show/annual route, windows, show timezone, collection, selected headline, forecast target | date, coverage and target alignment approval |
| Financial review | source row ID per analysis/entity/role/metric, compatible labels/boundaries/units | source-level semantic review, no amount or availability override |
| Post review | stable `profile:post` key, reviewed relevance | caption/collection evidence; baseline and annual posts also require review |

Approved aliases may include exact historical shared symbols (for example a
reviewed ticker transition). They require mapping evidence and are never guessed.
Distinct peer IDs resolving to the same financial subject, or to the subject
being scored, block the headline comparison until the approved set is corrected.

Exactly one selected headline per prospect is needed. Proposed peers can be
rejected; blank peer lists must be resolved. `mapping_approved`, `approved`,
`reviewed` and all comparability controls start false. Source reports do not
constitute these approvals. Refresh merging preserves existing decisions and
intentional blanks. An input refresh keeps a recoverable `.xlsx.bak` and refuses
to overwrite a previous backup. CSV migration runs once during initial seed;
manual CSV configuration is not used by this service afterward.

Financial roles are `oldest`, `earlier`, `latest`, `baseline` (forecast), and
`prior_actual`. Optional `cost_of_revenue`, `gross_profit`, `ebitda` review rows can
be added for each selected actual period. Three discrete comparable annual,
quarter or half-year observations are required for complete growth/Trend. Native
Light fiscal labels remain distinct from shared calendar labels. Cumulative
periods, repeated quarterly-looking estimates and synthetic annual sums are not
automatically accepted. Aggregated series must arrive as a verified DB/export
observation with its explicit aggregation provenance; this v1 does not build
annual revenue by summing raw quarters.

## Strict historical replay and provenance

Show cutoff is the end of local day show+37, including daylight-saving changes.
Annual cutoff is explicit and timezone-qualified. A forecast period must start
after cutoff, align with the stated target, and share scope/currency/units with
the selected revenue. Information from subsequent collection sales is excluded.

Financial candidates retain source relation, content-derived row ID, native
labels, publication/capture metadata, extraction scope, underlying source and
correction events. Consolidated view metadata can belong to a different source
than its revenue; corrections can change revenue without changing publication
metadata. Neither makes a historical version eligible. Current DB financial
candidates start `vintage_verified=false`. Approving a row in Excel does not
override that flag or its timestamps. A dated authenticated export/source audit
must establish the actual version's `available_at` and verification. No current
forecast or report-entered amount is a substitute.

An authenticated snapshot JSON has `financials`, `posts`, `profiles`, `registry`,
`overrides` and `metadata`. Metadata must contain authentication and extraction
time. Eligible financial observations require source relation/row ID, metric,
kind, amount, scope, currency, unit multiplier, period boundaries/type/label,
`available_at`, and `vintage_verified=true`, supported by exporter/audit evidence.
The flag is a provenance attestation from the approved export process, not a
cryptographic authentication claim. Keep original exported files and audit
references. Do not edit JSON measurements to make a score pass.

Instagram uses the capture-history table when the posts view lacks historical
timestamps or is absent. Filter eligible captures before deduplication, then
retain the latest eligible observation by stable profile/post identity. Conflicting
same-time captures are excluded. Unknown capture timing is ineligible, including
timestamps without a verified timezone. Early Prada captures in this export are
timezone-naive; they must not be silently interpreted as UTC. Missing
likes stay null; zero is usable, but a zero median baseline cannot define lift.

Show current sample: days 0–7, reviewed collection relevance. Baseline: pooled
days −30 to −1 and +8 to +37. Each needs five usable posts. Annual: explicit,
equivalent windows in successive years, 20 usable posts per year and three common
months. Coverage and all retained-window relevance decisions require review.
Thresholds are screening rules, not statistical confidence guarantees.

## Policy and app contract

Python defaults are validated through published Aily ConfigRepository. Audited
reference YAML lives beside the service policy module; tenant overrides use
`<tenant>[_<env>]__fashion_momentum__score.yaml`. The entire resolved policy is
saved for each delivery. Tenant/environment are never embedded in code.

Growth rates are fractions in the app contract. Scoring converts these to percent:
IR = clip(50 + 5 × latest peer-relative gap in pp). Social = clip(50 + 100 × median
likes lift). Trend first checks change >+2 →70, change <−2 →30, then both gaps ≥5
→80, otherwise50. Raw score = .5IR + .3Social + .2Trend. No missing-component
imputation or weight redistribution. Classification uses unrounded raw score.

Same approved peers are used in both comparisons. Pair results are diagnostic
only. Available reviewed components remain displayable even when headline FMI
is unavailable. Unverified or late app measurements remain null.

The reviewed selected headline cohort maps min/max to70/98, half-up one decimal;
equal/single cohorts map84. Empty cohorts remain empty. Classification stays raw.
Uplift = .11 × expm1(8 × rounded display /100) / expm1(8). Missing baseline keeps
the valid score and policy rate but adjusted revenue remains blank.

Limitations: changing cohort membership/extrema can change an unchanged brand's
uplift; the70–98 range gives every scored brand positive uplift. The scenario is
not calibrated predictive accuracy. No validation claim should be inferred.

`weighted-delivery.xlsx` and matching JSON come from the same result objects.
Delivery has one row per prospect and headline columns first. Supporting sheets
have distinct grains: selected Financial periods, analysis-peer diagnostics,
retained Social posts, Evidence, and Fields. Fields is the versioned app handover
dictionary: types, units, derivations and influence flags. Rates are fractions,
gaps pp, scores0–100, money carries explicit currency and unit multiplier.

Optional comments/views include usable denominators; format and paid-status
counts include unknown/other. Followers need eligible timestamped captures of the
same reviewed profile. Context never replaces likes or changes FMI. No inferred
engagement rates. Financial context requires its own scope-compatible selection.

## Running

Authenticate using the approved cloud profile and fill project `.env` (never
commit it). Set `AILY_TENANT`, `AILY_ENV`, `AILY_CLOUD_PROVIDER`, region and prefix
as required by published Aily libraries. Set `FMI_NODE` to a managed Node runtime
and `FMI_NODE_MODULES` to its managed module directory containing
`@oai/artifact-tool`. Do not install spreadsheet dependencies into the repo.

```sh
uv run aily-project fmi seed --prospects 'scripts/fashion-momentum-index/handover/brand_peers_dinner prospects.xlsx' --legacy scripts/fashion-momentum-index/inputs --output outputs/fmi-controlled/FMI_inputs.xlsx
uv run aily-project fmi extract --inputs outputs/fmi-controlled/FMI_inputs.xlsx --output outputs/fmi-controlled/snapshot.json --first-year 2022 --last-year 2026
uv run aily-project fmi score --inputs outputs/fmi-controlled/FMI_inputs.xlsx --snapshot outputs/fmi-controlled/snapshot.json --output outputs/fmi-controlled/raw-score.json
uv run aily-project fmi deliver --inputs outputs/fmi-controlled/FMI_inputs.xlsx --snapshot outputs/fmi-controlled/snapshot.json --output outputs/fmi-controlled/weighted-delivery.xlsx --previews
```

Light/shared clients are separate and injected. Settings initialize once per task
before ConfigRepository/DAL. Tenant uses `ro`; shared credentials resolve through
DAL. Both transaction read-only settings are checked before schema discovery.
Explicit-column SELECTs are bounded and recorded. No DDL/DML. The shared secret
may use `dbo`; session read-only is not database-enforced read-only grants.

## Refreshing review tasks

`propose-mappings` writes a new workbook, filling only empty candidate IDs and
adding eligible post-review tasks. It never approves them. Existing decisions
and original inputs remain unchanged. The delivered input workbook already
contains these proposals; ambiguous aliases and missing peers remain tasks.

## Acceptance and remaining human work

Represent all92 prospects, never drop an unresolved identity. Candidate mappings
are not entity approvals. Review all source IDs, scope/units, fiscal boundaries,
peer set, social windows and collection relevance. Establish dated financial and
forecast evidence where missing; otherwise strict historical outputs remain
unavailable. Review `coverage.json` and Delivery quality columns for exact tasks.

Verification includes isolated synthetic positive/missing-data tests, legacy
regressions, app field/join checks, required pytest/Ruff/format/type checks,
artifact-engine recalculation/error scan and visual review of every workbook
sheet. Generated data and notebooks' executed outputs remain out of git.
