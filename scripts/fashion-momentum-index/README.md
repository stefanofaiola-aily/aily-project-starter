# Fashion Momentum Index — disposable first version

Two notebooks and one Python helper. Extract small CSVs once, then score them
offline. No scheduler, service framework, training, dashboard or database writes.

The method follows `FMI_handover_plan_v2.docx`; comments at the end of the scoring
notebook explain peer selection, windows, scores, missing inputs and sales rule.

See [Metrics and methodology](METRICS.md) for every metric's inputs, formulas,
units, thresholds, missing-data rules and worked example, including the difference
between the provisional preview and reviewed calculations.

## Configure brands and all their peers

Here "tenant" means the scored brand/financial entity. It does not switch AWS
profiles, `AILY_TENANT`, database environments or credentials.

- `inputs/peers.csv`: keep the existing format. Each row declares one directed
  `brand, financial_entity, peer_entity` comparison. Three rows for Burberry with
  three different peers produce three scores. Only configured edges are scored;
  no global Cartesian product and no peer-group combinations.
- `inputs/analyses.csv`: one settings row per scored financial entity. Configure
  brand name, social handle, route, show date, collection caption strings,
  timezone, social windows, cutoff and review flags. Legacy `peer_1/peer_2`
  columns are ignored in real runs. Only entities listed as brands in peers.csv
  are scored; extra settings rows alone do not create results.
- `inputs/entities.csv`: one row per scored entity **or peer**. Set its Light
  company code and `oldest/earlier/latest_year/quarter`. Configure optional
  `target_year/quarter` and `last_year_target_year/quarter` for a sales scenario.

To add a brand: add its analyses row, entities row and any number of peers.csv
rows. To add a peer: add its entities row and the relevant peers.csv row.
Run extraction again when new company codes or social handles are needed.
Both notebooks read the same CSVs; no notebook code edits are needed for brands,
peers or financial period mappings. Social extraction date limits remain editable
in notebook01 and must cover all configured social windows.

Each result includes `financial_entity, peer_entity, peer_name, comparison_mode`
and per-pair growth, IR, social, trend and FMI. Social is shared within a brand;
IR/trend use **that one peer's growth**, not a median over its entire peer list.
Duplicate edges, self-peers and missing brand settings are rejected explicitly.
Unavailable source data is retained as an unavailable comparison with `gaps`;
it does not erase other valid pairs. Sales scenarios also have one row per pair:
they are alternative comparisons, not additive revenue adjustments.

This is the requested **pairwise extension** of the handover's original
two-peer-median method. Score weights, clipping, bands and uplift rules are unchanged.
`MODE="demo"` intentionally keeps the original median example as a regression check.

## Run

Open `notebooks/01_extract.ipynb` directly in VS Code/Jupyter, choose the starter
repo's `.venv` Python 3.11 kernel, then **Restart Kernel → Run All**.
Profile/runtime setup is inside the first code cell. Light and social downloads
are enabled by default. No `.env`, shell variables or `uv run` launch is needed.

The environment must have been installed once (the notebook group is already
installed in this checkout). Credentials remain in your AWS profile.

Open `notebooks/02_score.ipynb` with the same kernel, **Restart Kernel → Run All**.
It now defaults to `MODE = "preview"`, using the real downloaded CSVs, not demo
data and not the empty financial-selection template.

The supplied entity configuration selects September-ending periods for Burberry/Ralph Lauren
(FY2024–2026 Q2) and Moncler (2023–2025 Q3). It uses the Summer 2025 show on
16 September 2024, evidenced in the downloaded brand captions. Caption suggestions
include Summer 2025 show posts/guests and exclude Winter 2024; existing manual
labels override suggestions. Unknown captions block the social calculation.

Results are **provisional source-period proxies**, not validated collection FMI.
Light lacks scope, units/currency, fiscal boundaries and historical publication
versions; adjacent Burberry/Moncler quarter values repeat and may be allocations.
The selected periods are assumed selling-season proxies, not verified collection
sales. Coverage and engagement-age comparability also require review.

Saved automatically:

- `results/provisional_fmi_scores.csv`: component scores, FMI, band, limitations.
- `results/provisional_sales_scenario.csv`: illustrative forecast adjustment in
  unverified raw Light units; separate from the score. Missing forecast rows do
  not prevent scoring.
- `data/processed/preview_financials.csv`: selected source rows for every configured brand and peer.
- `data/processed/preview_collection_review.csv`: show-week caption suggestions.
- `data/processed/preview_target_financials.csv`: scenario source rows.

The Burberry sales scenario targets **FY2026 Q4 Forecast**, with **FY2025 Q4
Actual** for the year-on-year comparison, as configured in `inputs/entities.csv`.
Each pair's FMI drives the adjustment to that forecast; FMI at or below 60 means
0% uplift. Light labels FY2026 Q4 with reported date 31 March 2026, not calendar
Q4 2026. Rerun notebook 02 after changing the target period.

Your input CSVs and `collection_review.csv` are never overwritten by scoring.
Calculations and editable period choices are visible in the notebook.

For a reviewed result, set `MODE = "reviewed"`, then complete:

1. `inputs/financial_selection.csv`: actual row IDs for three equivalent selling
   periods per company, plus brand target forecast and prior-year target actual.
2. `inputs/financial_annotations.csv`: verified scope, currency, units and fiscal
   boundaries. Use official IR evidence for missing definitions.
3. `inputs/analyses.csv`: confirmed show/selling-season dates and manual
   financial-comparability/coverage attestations. No automatic review flags.
4. `data/processed/collection_review.csv`: collection-related true/false for all
   show-week posts.

Reviewed results remain `results/fmi_scores.csv`; invalid inputs remain unavailable.
For the synthetic handover example, use `MODE = "demo"` (FMI70.5, High,
5.1% uplift). Its outputs stay separate as `results/demo_fmi_scores.csv`.

The extraction notebook uses the explicit `aws-demos` profile, tenant `demos`,
environment `light`; it needs no .env and does not inherit FIN runtime settings.
If login expires, run `aws sso login --profile aws-demos`. Shared access also
requires its secret permissions and network/VPN.

Light's standard read-only connection was verified using `aws-demos`, logical
tenant `demos` and environment `light`, without a `.env`. Both requested
tables are present. Their columns are `company_code, reported_date, year,
quarter, type_filter_code, type_filter_value`; company names, currency and fiscal
period dates are not directly present and still need reviewed reference data.
Native Light columns and source row IDs are retained in the downloaded CSVs.
Instagram exports also retain captions and URLs for manual collection review.
Missing currency, units, scope and fiscal dates never prevent downloading, but
must be annotated before real scores can be calculated.

## Folder

```text
fashion-momentum-index/
├── .env.example
├── fmi.py
├── notebooks/
│   ├── 01_extract.ipynb
│   └── 02_score.ipynb
├── inputs/
│   ├── peers.csv
│   ├── entities.csv
│   ├── analyses.csv
│   ├── financial_selection.csv
│   ├── financial_annotations.csv
│   └── external_financials.csv
├── data/
│   ├── raw/             # SQL exports, metadata, company lookup
│   └── processed/       # selected financial evidence, collection review
├── results/             # demo and real scores kept separate
└── tests/
    └── test_fmi.py
```

Data/results folders are created by either notebook and ignored by Git.
Never commit raw data, collection reviews, credentials or notebook outputs.

## Financial CSV contract

Each financial export retains Light's six native fields, plus normalized aliases:
`entity, company_id, company_name, period_start, period_end, period_type, metric,
scope, currency, amount, unit_multiplier, classification, published_at, version,
source, source_locator, source_row_id`.

- `entity`: keys matching the configured brand/peers, e.g. `burberry`.
- `period_type`: `annual` or `quarter`. Use official reporting dates, not guessed
  calendar dates. Year/quarter-only sources need explicit fiscal-calendar mapping.
- `metric`: one consistent revenue definition for the comparison. Net revenue,
  comparable sales and growth commentary are not interchangeable.
- `scope`: explicit reported group/segment/brand entity; stable across periods.
- `unit_multiplier`: 1 for currency units, 1000 for thousands, 1000000 for millions.
  Empty units/scope block scores until reviewed; amounts are not silently rescaled.
- `classification`: exactly `Actual` or `Forecast`.
- `published_at`: ISO publication/version timestamp. Future versions are rejected;
  unknown dates cannot support point-in-time claims.
- `source_locator`: source URL and report page/table for external figures.
- `source_row_id`: stable export ID or unique externally entered ID. Choose one
  source row for each entity/period role, not a total across rows/versions.

Use `oldest/earlier/latest` for three equivalent prior-year actual periods.
Brand `target` must be a Forecast for the intended fiscal quarter; optional
`last_year_target` is the same fiscal quarter's Actual in the prior year.
The forecast, historical actuals and adjusted result must share scope/metric/currency.
A parent's baseline cannot be applied to standalone brand actuals.

`financial_annotations.csv` supports explicit row-specific review of company
name, scope, currency, units, fiscal period dates/type, publication/version dates
and evidence locator. No equal-split or engagement-share revenue allocation.

## Method in brief

IR = clip(50 + 5 × brand-minus-selected-peer growth in pp), per comparison.
Social = clip(50 + percentage-unit lift in median likes).
Trend uses the ordered +2/-2 pp, sustained +5 pp rules from the handover.
FMI = 50% IR + 30% social + 20% trend. No missing-value substitution or reweighting.

Scores are classified unrounded. FMI ≤60 preserves baseline; above 60 the uplift
is 3% + (FMI−60)/10 × 2%. This jump is intentional. Low FMI never reduces baseline.
This is a sales-planning scenario, not a causal model.

Review flags are manual attestations, not data quality inferred from CSV row counts.
The editable minimum of five usable posts is a screening assumption, not a
validated sample-size threshold. Point-in-time mode requires known social capture
and financial publication dates; otherwise outputs say descriptive/current snapshot.

## Peers and external research

`inputs/peers.csv` keeps the handover's Burberry/Ralph Lauren/Moncler proposal,
rationale, business-mix differences and official IR entry points. No universal
peer list or automatic web scraping. Start with Light. If a series is missing,
read official results/annual reports, then regulatory filings; use other reporting
only as a clearly labeled last resort. Record exact figures and locators yourself;
no official revenue figures have been invented or prefilled.

## Checks

```bash
uv run --locked --group notebook pytest -m unit scripts/fashion-momentum-index/tests
uv run --locked --group notebook ruff check scripts/fashion-momentum-index
uv run --locked --group notebook ruff format --check scripts/fashion-momentum-index
uv run --locked --group notebook ty check scripts/fashion-momentum-index/fmi.py
```
