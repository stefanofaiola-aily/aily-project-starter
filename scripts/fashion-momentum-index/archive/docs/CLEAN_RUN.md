# Clean notebook run

Current instructions: [SIMPLE_WORKFLOW.md](SIMPLE_WORKFLOW.md). The sections below
record the former controlled-folder/review-companion layout. Current output is
only Excel and JSON; previous runs are archived internally.

## What to edit

Use `inputs/FMI_inputs.json` for everyday brand settings: identity, Light code,
ticker, shared symbol, Instagram account, peers, collection/show date, periods
and forecast target. The controlled notebooks do not read the legacy CSVs.

Two companions serve different purposes:

- `FMI_reviews.json`: selected database rows, reporting scope, comparable periods,
  collection-post relevance and release approvals. Changing relevant settings
  invalidates old approvals but preserves their recorded decisions.
- `FMI_policy.yaml`: score weights, thresholds, rescaling and the two uplift curves.

Do not enter source measurements or edit approval binding hashes. A successful
notebook run can generate a coverage report without any released score.

## Execution and outputs

Run the three notebooks in `notebooks/controlled/` with the project Python kernel,
in order. They default to the same `outputs/fmi-controlled/` directory:

1. `01_extract_review.ipynb`: fresh read-only Light and shared extraction.
2. `02_raw_score.ipynb`: raw FMI and approved-peer-median diagnostics.
3. `03_delivery.ipynb`: rescaling, both uplift methods, Excel, app JSON, field
   dictionary and per-brand calculation records.

Local connection settings use `AWS_PROFILE=aws-demos` and
`FMI_SHARED_AWS_PROFILE=aws-shared`, with tenant/environment in ignored `.env`.
No database credentials belong in the brand input file. Extraction always reads
the databases. The later notebooks can replay a snapshot with `FMI_OFFLINE=true`.

The clean execution saves populated notebook copies under
`outputs/fmi-controlled/executed-notebooks/`; source notebooks remain output-free.
`notebook-execution.json` records the kernel, source hashes and execution times.

The shareable outputs are `weighted-delivery.xlsx` and `weighted-delivery.json`.
Excel contains only one `Delivery` sheet with row-1 headers; JSON is a plain array
of the same rows. `observed_*` source context is unreviewed and explicitly not
eligible for historical scoring. Change inputs and rerun to refresh both files.
`output-dictionary.json` explains fields. `coverage.json` states release gaps.
`delivery-audit.json` keeps supporting records outside the shareable table.
`dinner-reconciliation.json` verifies all dinner brands and invitation flags.
Brand calculation documents live under `brand-runs/<run-id>/`.

## Identity audit

The read-only `fmi inventory` command now searches shared company-name/symbol
metadata as well as Light. It discovers shared-only public peers and alternate
listings rather than restricting searches to already-known tickers. All searches
are bound and row-limited. A candidate never becomes a scoring approval.

The current run contains:

- `mapping-inventory-expanded.json`: authenticated registry, shared identity
  candidates, account identifiers and financial-symbol coverage, including query
  scope and extraction time.
- `mapping-audit.json`: exact/current identities and similar-name review candidates
  for all prospects and peer entities. Similarity is not identity proof.
- `mapping-changes.json`: before/after query settings for 44 entities. It preserves
  the distinction between Light code, ticker and shared symbol.

Private companies can have a null ticker and a valid shared private symbol.
Christian Dior maps to Light's fashion-house `DIOR`, not listed holding company
`CDI.PA`. Giorgio Armani posts are queried through `giorgioarmani`; the `armani`
profile has no posts in the inspected archive. Both still require scope/window
review. Source-provider names can disagree with configured names, so metadata
matches alone cannot establish reporting scope.

Parent candidates such as Tapestry for Coach/Kate Spade, Capri for Michael Kors
and Inditex for Zara are not standalone brand measurements. They must not become
unlabelled substitutes. Unresolved brands stay in the delivery with missing-input
statuses.

## Recoverable cleanup

Previous generated FMI runs, legacy `data/` and legacy `results/` were moved to
`outputs/archive/20261101T204524Z/`. Nothing was deleted. The archive manifest
records original and new locations; historical files remain unchanged. The first
mapping pass is retained there too. Raw inputs, handover documents, review files
and the Git notebook backup were preserved.

## Release checks

Use reviewed, comparable revenue periods and all approved peers for one headline
per brand. Review show-post relevance and eligible capture timing. Do not replace
missing components with neutral values. Source availability and score eligibility
are different checks.

Historical uplift also requires a positive compatible forecast baseline with a
verified vintage at/before the analysis cutoff. The inspected Light forecast
relation has no native vintage. Current forecasts and later social captures cannot
replace historical evidence. Until these prerequisites are resolved, the workbook
is a coverage/review report, not a completed FMI leaderboard.
