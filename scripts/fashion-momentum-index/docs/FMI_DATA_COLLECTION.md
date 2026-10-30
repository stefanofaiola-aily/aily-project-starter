# FMI source data collection

## Downloads do not require score approval

`fmi inventory` and `fmi collect` discover identifiers, read handover reports and
download source observations independently of score-release approval gates.
Reports supply identity, handles, collection dates, scope clues and evidence.
Their amounts, likes, historical scores and adjustments are not imported as
production measurements. Light/shared clients remain separate, injected and
transaction-read-only. Light retains the `ro` role.

The 30 October 2026 collection represents 92 prospects and reads 86 handover
reports. It retains 10,297 financial metric candidates and 97,617 Instagram capture
rows for prospects and peers. Revenue candidates were found for 47 prospects,
Instagram captures for 57, and both for 42. Availability counts do not establish
complete scores, sufficient samples or historical eligibility.

The financial identifier inventory checks consolidated and underlying tables
against Light identifiers and prospect/peer search tokens. It is not an exhaustive
catalogue of every global symbol. No-match means no rows for the candidate
identifiers queried. Further private-alias or scope evidence can warrant another
query. Standalone brand revenue is not replaced with parent revenue automatically.
The Levi Strauss proposal is labelled as a group proxy candidate for Levi's.
Estée Lauder and Macy's use the reports' corporate accounts, not banner accounts.

## Saved outputs

Files are under ignored `outputs/fmi-collected-20261030-final/`:

- `FMI_collected_data.xlsx`: 92 prospect coverage rows, financial observations for
  prospects and peers, descriptive annual Instagram medians and usable-metric
  denominators, report date/scope evidence and query provenance.
- `FMI_inputs.xlsx`: identity/handle proposals and preserved human decisions.
  Financial source IDs, comparable periods and collection relevance are reviewed
  here. Source amount/likes override columns are not provided.
- `snapshot.json`: downloaded financial, post, profile and correction observations,
  including captions and URLs needed for collection-post review.
- `handover-index.json`, `mapping-audit.json`, `collection-coverage.json`: evidence,
  candidate mappings, coverage and specific missing-input tasks.

Original controlled inputs and historical deliveries remain unchanged. Extracts,
review workbooks and notebook outputs stay out of git. Human inputs use Excel;
calculation policy remains versioned YAML resolved through ConfigRepository.

## Refresh commands

Authenticate with the approved cloud profile. Keep runtime configuration in shell
or `.env`, including the managed `FMI_NODE` and `FMI_NODE_MODULES` spreadsheet
runtime. Never put tenant/environment or credentials in source. Use a fresh output
directory; collection refuses to overwrite existing snapshots/review workbooks.

```sh
uv run aily-project fmi inventory --inputs outputs/fmi-controlled/FMI_inputs.xlsx --first-year 2022 --last-year 2026 --output outputs/fmi-NEW/inventory.json
uv run aily-project fmi collect --inputs outputs/fmi-controlled/FMI_inputs.xlsx --inventory outputs/fmi-NEW/inventory.json --handover scripts/fashion-momentum-index/handover --output-dir outputs/fmi-NEW --first-year 2022 --last-year 2026 --previews
```

Rerun only the export after a layout change or interrupted workbook generation:

```sh
uv run aily-project fmi collection-export --inputs outputs/fmi-NEW/FMI_inputs.xlsx --snapshot outputs/fmi-NEW/snapshot.json --audit outputs/fmi-NEW/mapping-audit.json --reports outputs/fmi-NEW/handover-index.json --output outputs/fmi-NEW/FMI_collected_data.xlsx --previews
```

## Remaining score checks

Financial rows retain native Light year/quarter and shared year/period labels,
source IDs, publication/capture metadata, source classification and correction
provenance. Do not add competing sources, cumulative periods or repeated quarters.
Verify fiscal boundaries, reporting scope, currency and unit multipliers before
comparing or aggregating amounts. Source candidates are not released app metrics.

Instagram history is queried for the proposed account set. Missing normalized
accounts fall back to the report-referenced Bright Data archive's actual
`user_posted`/`user_posted_id` fields. Mirrors are not merged for the same handle.
Missing likes/timestamps remain missing; numeric zero is retained.

Annual workbook medians summarize current retained captures. They are descriptive,
not strict historical replay or collection-relevance decisions. Historical show
scoring still requires reviewed collection posts and capture filtering at the
show-date-plus-37-day cutoff before deduplication. Later social captures and
current forecasts cannot prove earlier evidence. A single collected post is not
a sufficient score sample.

Next select comparable financial observations, an explicit analysis/window, peers
and collection relevance. Establish dated financial/forecast versions where
required, then run `fmi score` and `fmi deliver` against this snapshot and reviewed
Excel inputs. These release checks never prevent collection of available data.
