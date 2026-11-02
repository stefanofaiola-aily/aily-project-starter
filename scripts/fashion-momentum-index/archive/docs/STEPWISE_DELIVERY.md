# FMI step-by-step delivery

Current instructions: [SIMPLE_WORKFLOW.md](SIMPLE_WORKFLOW.md). This document
retains the earlier detailed architecture and former folder/review-file layout.

## Seven control points

1. **Inputs:** edit `inputs/FMI_inputs.json`. It contains 94 prospects, including
   all 31 unique mandatory event brands. Michael Kors is duplicated in the raw
   event file and delivered once. Armani and Longchamp extend the earlier 92.
   Categories/invitation flags are preserved. A blank invitation means unknown.
2. **Query:** retrieve Light actuals/forecasts and shared financial/social rows.
   The snapshot records explicit SQL, bind scopes, source IDs and extraction time.
3. **Select/review:** in `FMI_reviews.json`, choose source IDs for three comparable revenues, peer
   revenues, forecast and matching prior-year actual. Review social relevance.
   Reports provide identity/date/scope clues, not production amounts or likes.
4. **Score:** IR uses revenue growth versus the same approved peer median;
   Social uses median Instagram likes lift; Trend uses change in the relative
   growth gap. Weights are 50%, 30%, 20%. Missing inputs stay missing.
5. **Uplift:** deliver the old raw-score threshold/linear method and the new
   display-score exponential method against the same eligible forecast baseline.
6. **Export:** Excel and app JSON use the same result model. Selected drivers,
   optional context, current source candidates and historical references are
   distinct categories. The dictionary describes every column and its unit.
7. **Brand record:** each brand gets Markdown/JSON with settings, selected
   observations, formulas, query/source IDs and specific missing inputs.

## JSON layout and editable choices

The compact `fmi-input-v2` schema has one brand object, one `analysis` object and
a simple `peers` array of stable IDs. Identifiers, `instagram`, dates and optional
`financial_periods`/`forecast` are the everyday settings. Unknown optional fields
are omitted. `peer_entities` holds peer-only identities once; a prospect used as
a peer keeps its identity in `brands`. Do not rename stable IDs.

`policy_file` points to `FMI_policy.yaml`, which contains shared score, rescaling
and both uplift parameters. Live tasks first resolve tenant defaults through Aily
ConfigRepository; YAML overrides are validated and recorded. `query` contains
bounded `first_year`, `last_year` and `row_limit`. Credentials/tenant/environment
remain in shell or `.env`.

`review_file` points to `FMI_reviews.json`: mapping and peer approvals,
comparability decisions, financial source IDs/annotations and post relevance.
It also retains report suggestions and raw-source hashes as evidence, not
production measurements. No amounts, likes or vintage overrides are accepted.
Reviews are bound to the identity/analysis settings they approved. Changes to
identifiers, dates, peer membership/identities, period labels or forecast target
invalidate affected approvals without deleting the old decisions. Event labels
and policy-curve changes do not invalidate measurement reviews.

After changing settings, write a new review proposal, inspect/reapprove the
affected selections, then set `review_file` to its filename:

```sh
uv run aily-project fmi refresh-reviews --inputs scripts/fashion-momentum-index/inputs/FMI_inputs.json --output scripts/fashion-momentum-index/inputs/FMI_reviews.next.json
```

The proposal keeps source choices/relevance and resets stale approvals. Do not
edit binding hashes. Runs save the fully expanded `resolved-inputs.json`, so the
compact display never hides the exact effective parameters. Financial-period
labels alone do not choose observations; source IDs and semantics still require
review. Old v1 JSON and Excel readers remain supported for migration/replay.
See [input file responsibilities](../inputs/README.md) for legacy/raw CSV usage.

### Compact-input migration verification

The main JSON decreased from 22,742 lines / 778,870 bytes to 1,425 lines / 31,574
bytes. It retains 94 prospects, 31 mandatory event brands and 116 peer assignments.
All 818 financial review records were preserved in the companion file. All 94
canonical app/Excel calculation records match the previous inputs against the
fresh authenticated snapshot; a fully reviewed unit example also preserves its
raw FMI and both uplift results. Date-only formatting is normalized, not changed
in meaning. The score CLI successfully generated expanded `resolved-inputs.json`
from the compact bundle without reading any legacy CSV.

The six legacy CSVs were moved byte-for-byte into `inputs/legacy/`, and the old
verbose JSON is retained there. Old notebook paths were updated, not removed.
The 115 project tests, 74 legacy tests, Ruff lint/format and type checks pass.
Existing historical outputs and the review Excel were not overwritten.

Show rules are fixed: current days 0–7; pooled baseline −30…−1 and +8…+37;
cutoff end of local day +37. Show `current_*`/`baseline_*` dates are derived
display information, not editable window overrides. The baseline excludes show
week. Edit show date/timezone to change them. Annual window dates are inputs.
Changing show-window logic requires a method/code version change.

An approval does not establish a missing vintage. Current forecasts and later
likes captures cannot substitute for historical observations. Window-end dates
alone do not establish an annual assessment cutoff or timezone.

## Both uplift methods

```text
legacy_rate = 0                            if unrounded raw FMI <= 60
              .03 + .002 * (raw FMI - 60) otherwise
new_rate = .11 * expm1(8 * rounded display FMI / 100) / expm1(8)
adjustment = baseline * rate
adjusted_forecast = baseline + adjustment
```

This comparison changes both curve and score basis. The old jump above 60 is
preserved. The 70–98 display range makes new uplift positive for every scored
brand. Changing cohort extrema can change an unchanged brand's uplift. Both are
business scenarios, not calibrated predictive accuracy. Without a baseline,
valid scores/rates survive but adjusted amounts remain null.

## Commands from project root

Prepare without cloud access; output must be new. Refresh with `--existing` and
a new output path to preserve decisions. `--inventory` accepts saved authenticated
discovery; neither flag performs a query or approves proposals.

```sh
uv run aily-project fmi prepare-inputs --raw scripts/fashion-momentum-index/inputs/raw --handover scripts/fashion-momentum-index/handover --output scripts/fashion-momentum-index/inputs/FMI_inputs.json
```

Configure `.env` from `.env.example` and authenticate the approved AWS profile.
Connections remain separate and verified read-only; tenant stays `ro`. No DDL/DML.

The confirmed local environment is `demos/light`, region `eu-central-1`:

```dotenv
AILY_PREFIX=aily
AILY_TENANT=demos
AILY_ENV=light
AILY_CLOUD_PROVIDER=aws
AWS_REGION=eu-central-1
AWS_PROFILE=aws-demos
FMI_SHARED_AWS_PROFILE=aws-shared
```

`AWS_PROFILE` authenticates Light; `FMI_SHARED_AWS_PROFILE` authenticates the
shared scanner's Secrets Manager route. If omitted, shared uses `AWS_PROFILE`.
These are separate profile sessions, not a mid-run environment switch. Settings
initialize once. A small public-method provider adapter keeps secret retrieval
on the injected profile, including cross-region secret ARNs. Credentials remain
inside DAL; never print or commit them. The local `.env` is ignored by Git.

Authenticate both profiles if their sessions have expired, then preflight:

```sh
aws sso login --profile aws-demos
aws sso login --profile aws-shared
uv run aily-project fmi check-connections
```

The preflight reads session metadata only, verifies both read-only settings, and
stops on authentication/connectivity failures before any business-table read.

### Notebook order

Use the project Python kernel and the same `FMI_OUTPUT_DIR` for all three
notebooks. Choose a new output directory for a new extraction. Notebook 1 queries
both databases live and saves `snapshot.json`. Pause to review the input JSON
before notebook 2 scores that snapshot. Notebook 3 recalculates from the reviewed
JSON and the same snapshot, then writes Excel, app JSON and per-brand records.
Notebooks 2/3 do not refresh measurements. `FMI_OFFLINE=true` applies only to
their policy resolution; it never makes notebook 1 use cached data.

Changing mappings/query bounds requires rerunning extraction. Changing peers,
source selections, dates/windows or policy requires rerunning scoring/delivery
and may require extraction if the new scope was not included in the snapshot.
Review is not automatic approval, and a current refresh cannot recover absent
historical financial/social/forecast vintages.

```sh
uv run aily-project fmi inventory --inputs scripts/fashion-momentum-index/inputs/FMI_inputs.json --first-year 2022 --last-year 2026 --output outputs/fmi-run/inventory.json
uv run aily-project fmi collect --inputs scripts/fashion-momentum-index/inputs/FMI_inputs.json --inventory outputs/fmi-run/inventory.json --handover scripts/fashion-momentum-index/handover --first-year 2022 --last-year 2026 --output-dir outputs/fmi-run/collected
```

`collect` writes a compact JSON/policy/review bundle, source workbook and snapshot.
Review the companion review file; proposals are not approvals.
With resolved identifiers, direct extraction reads years/limit from input JSON:

```sh
uv run aily-project fmi extract --inputs scripts/fashion-momentum-index/inputs/FMI_inputs.json --output outputs/fmi-run/snapshot.json
uv run aily-project fmi score --inputs scripts/fashion-momentum-index/inputs/FMI_inputs.json --snapshot outputs/fmi-run/snapshot.json --output outputs/fmi-run/raw-score.json
uv run aily-project fmi deliver --inputs scripts/fashion-momentum-index/inputs/FMI_inputs.json --snapshot outputs/fmi-run/snapshot.json --handover scripts/fashion-momentum-index/handover --output outputs/fmi-run/weighted-delivery.xlsx --previews
```

`deliver --historical PATH` accepts the roadmap `weighted-delivery.json` as audit
reference only. `score`/`deliver --offline` replay authenticated saved data and its
recorded policy, plus explicit JSON settings. No live refresh or relaxed cutoff.
Set `FMI_NODE`/`FMI_NODE_MODULES` to the managed `@oai/artifact-tool` runtime.

## Excel and app contract

`weighted-delivery.xlsx` has one `Delivery` sheet: one row per prospect, headers
in row 1, identifying columns frozen, with both uplift methods. The matching
`weighted-delivery.json` is a plain array of the same row objects, not an envelope.
Example app read: `rows = json.loads(path.read_text())`.

Both files are service-calculated snapshots. Change inputs/reviews/policy and
rerun notebooks 2/3; editing Excel does not recalculate the app data. Scoring,
rescaling and uplift have one calculation path. No extra workbook tabs are added.

Retrieved counts and `observed_*` columns show source context even when a score
is unavailable. The revenue observation is the latest unique dated actual row
from the consolidated view, without summing quarters, choosing conflicting rows,
assuming units or approving scope. It may be estimated/interpolated. The displayed
social cohort is the latest observed publication month before the extraction
month; it may be older if the archive has gaps. Captures are current, not historical
replay. Likes/comments/views have separate usable denominators. Change uses the
preceding calendar month, not the preceding available month. Unknown stays null.
`observed_context_historical_eligible=false` and statuses distinguish this context
from reviewed historical score drivers. These fields never change FMI or uplift.

`output-dictionary.json` describes every delivery column, type, unit and influence.
Different-grain inputs/diagnostics, policy/cohort and source hashes stay in local
`delivery-audit.json`, `snapshot.json` and per-brand run records, not the manager's
Excel or app array. `--historical` retains old results only in that local audit.
Null means missing, not zero. `dinner-reconciliation.json` verifies every dinner
brand against inputs/delivery, accounting for aliases and duplicate event rows.

## Initial review delivery: 1 November 2026

Before connection configuration, this session had no `AILY_TENANT`, `AILY_ENV`
or `AILY_CLOUD_PROVIDER`, so live discovery failed before creating clients.
The initial review delivery uses the authenticated snapshot
extracted **30 October 2026**, not a 1 November refresh. Newly added identifiers
may be outside its query scope. All 94 prospects are represented, but the output
is a source/coverage review delivery until reviewed inputs and eligible vintages
allow headline scores and adjusted forecasts. No report amounts were substituted.

The connected PostgreSQL tool was also checked independently. It authenticated
to shared production as a privileged role with both transaction read-only settings
off. No source-table reads were made through that connection. Configure the
approved local read-only DAL route to perform a fresh extraction safely.

### Confirmed local connection setup

The user subsequently confirmed `demos/light`. The ignored local `.env` now
configures Light through `aws-demos` and shared through `aws-shared`, plus the
managed spreadsheet runtime. Live preflight succeeded for both profiles: Light
authenticated as `demos_light_ro`, shared as `saasymastermind`, and both session
read-only settings were `on`. Shared's role is not database-enforced read-only;
the verified session constraint remains mandatory. The initial review workbook
has not been overwritten or relabelled as a fresh extraction.

Fresh extraction then succeeded at `2026-11-01T20:13:54.132763+00:00` and is
saved separately at `outputs/fmi-live-20261101/snapshot.json`. It contains 10,360
financial candidates, 96,073 Instagram capture rows, 870 profile rows, 369 registry
rows and 113 correction events from 13 scoped source queries. Of 31 mandatory
event brands, 21 have actual-revenue candidates and 30 have Instagram captures.
These are retrieval counts, not reviewed scope-compatible score inputs.

The inspected Light forecast relation still has no native vintage. Strict
historical uplift requires a dated authenticated forecast export; a live refresh
does not resolve that limitation. Review decisions were not changed. All 100
project tests, Ruff lint/format and type checks pass after profile isolation.

To use this saved extract in notebooks 2/3, set `FMI_OUTPUT_DIR` to that directory
in the kernel environment. To perform another live extraction in notebook 1,
choose a different output directory and keep that same path for notebooks 2/3.

### Saved-file verification

The saved Excel and JSON agree across all 16,920 headline cells (180 fields for
94 prospects). The 361-entry output dictionary covers every exported data column.
All 11,617 mapped financial candidate rows match their snapshot observation IDs
and amounts; repeated entity mappings are not additive. Supporting-sheet row
counts and all 94 brand records reconcile. The workbook contains no Excel error
cells. All sheets were visually checked, including the final changed views.

The 90 project tests and 74 historical regression tests pass. Ruff lint, format
and type checks pass. Workbook formula/service parity and input-change behavior
are covered by isolated tests; native Excel application execution was not tested.
The current delivery has **zero released FMI scores and zero adjusted forecasts**.
Share it as an input/data-coverage review, not a completed ranking.

## Differences from historical reports/roadmap

- Some reports use 15 pre-show days; the controlled score uses the pooled
  pre/post baseline above. These are different social measurements.
- The roadmap awards improving Strength 80 if the latest gap is nonnegative,
  otherwise 70. This service follows the agreed rule: improving 70, declining 30,
  then sustained outperformance 80 if both gaps are at least +5 pp, otherwise 50.
- Retail/DTC, organic growth, total issuer revenue and parent/segment proxies in
  old reports are not interchangeable. Selected database amounts require scope,
  fiscal-period and vintage review before recomputing reported growth.
- Historical reports can use later social captures, post-show selling outcomes
  or partial-weight totals. They are audit references, not historical score inputs.
- Old display values used a different available cohort. Rescaling the new reviewed
  cohort need not reproduce them, even when a raw score happens to agree.
