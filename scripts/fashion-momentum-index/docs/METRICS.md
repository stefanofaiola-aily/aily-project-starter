# FMI metrics and methodology

This documents the **implemented version** of [02_score.ipynb](notebooks/02_score.ipynb)
and [fmi.py](fmi.py), based on `FMI_handover_plan_v2.docx`.
Real runs now score one row per configured brand-peer edge. This pairwise
extension was requested after the initial handover implementation. The original
two-peer-median method remains only in the synthetic demo.
It separates the implemented method from the assumptions in the runnable preview.
All worked financial amounts below are synthetic, not company observations.

The descriptions below were checked against both notebooks, `fmi.py`, and the
locally saved schema-discovery CSVs. Schema types describe that saved discovery,
not a fresh database inspection or a guarantee of upstream data completeness.
No live database access is needed to read or reproduce the arithmetic.

### Calculation path at a glance

```text
01_extract.ipynb
  Light actuals/forecasts -> scoped revenue rows -> raw financial CSVs
  Shared Instagram table -> scoped capture rows -> one capture per post -> raw social CSV
02_score.ipynb (offline)
  financial period selection -> entity growth -> brand-minus-peer growth -> IR + trend
  post dates + collection labels -> current/baseline likes -> medians -> social
  IR + social + trend -> weighted FMI -> classification
  FMI + selected forecast -> separate sales-planning scenario
```

Database extraction does not compute medians, collection labels, component scores
or FMI. Those are calculated offline. Section 5 explains the source-table contract
and extraction query; section 6 walks through individual posts becoming a score.

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

## 1. What the score measures

FMI combines three signals on a 0–100 scale:

| Component | Question | Weight |
| --- | --- | --- |
| Commercial / IR | Is revenue growth stronger than the configured peer? | 50% |
| Social | Do collection posts receive more median likes than normal brand posts? | 30% |
| Trend | Is peer-relative revenue performance improving? | 20% |

IR means the commercial/financial component here; it is not a separate
investor-relations sentiment metric. FMI is a heuristic, not a probability,
model confidence, revenue percentage or causal estimate of a collection's impact.

`clip(x)` below means `max(0, min(100, x))`.
Percentages are stored in percentage units: 8 means 8%, not 0.08.
A difference between growth rates is in **percentage points (pp)**:
8% minus 5% = 3 pp.

## 2. Sources and preparation

| Input | Source | Saved file |
| --- | --- | --- |
| Revenue actuals | `light.light_financial_statements_actuals` | `data/raw/revenue_actuals.csv` |
| Revenue forecasts | `ai.light_financial_statements_forecast` | `data/raw/revenue_forecasts.csv` |
| Instagram posts | Shared DB: `denormalized.social_media_bright_data_instagram_posts` | `data/raw/instagram_posts.csv` |

Extraction uses scoped revenue/company/year filters and bounded social
handle/date/capture filters. Scoring reads CSVs offline and does not query databases.

Light's native fields are `company_code, reported_date, year, quarter,
type_filter_code, type_filter_value`. The exporter maps revenue to `metric`
and its value to `amount`; it labels Actual/Forecast according to the source
table. That label does not independently verify upstream financial provenance.

`export_light_revenue` first verifies a read-only session and discovers the six
required columns. It selects only configured company codes, rows with
`type_filter_code = 'revenue'`, and fiscal `year` between the configured bounds
(inclusive). Values are bound parameters, not SQL string interpolation. The
default cap is 10,000 source rows per table: it requests 10,001 and raises if the
cap is exceeded rather than saving a silently truncated extract. It does not
join social data, sum quarters, split half-years or aggregate versions.

The extraction notebook derives company codes and fiscal-year bounds from the
configured scored brands **and their peers** in `inputs/entities.csv`. Preview
then matches one row per `entity, year, quarter, classification` for each period
role. Reviewed mode instead selects explicit `source_row_id` values and applies
row-specific annotations. `reported_date` is retained as a source date; it is not
automatically treated as a verified fiscal boundary or publication timestamp.

`source_row_id` is a truncated SHA-256 hash of the exported row contents.
It identifies evidence; it is not a metric. Exact duplicate rows are removed.
Different values/versions are never added together to make a revenue total.

For reviewed calculations, financial value is:

```text
revenue_value = amount × unit_multiplier
```

For example, 100 in millions with multiplier 1,000,000 becomes 100,000,000.
Preview uses raw `amount` for within-entity ratios and assumes its units and
reporting scope are stable across the three selected periods. It does not invent
currency or convert between currencies.

## 3. Periods, peers and calculation modes

### Period roles

Each brand and each selected peer needs three equivalent actual periods:

- `oldest`: the period two years before the latest period.
- `earlier`: the equivalent period one year before latest.
- `latest`: the selling-period actual used for current commercial performance.

For a show route, use the collection's actual selling season, **not automatically
the quarter after its runway show**. For an annual route, use three equivalent
annual actual periods; the intended fallback is for brands without a relevant
show. Route/season selection remains a human decision.

The current preview uses these explicit source-period proxies:

| Entity | Oldest | Earlier | Latest |
| --- | --- | --- | --- |
| Burberry | FY2024 Q2 | FY2025 Q2 | FY2026 Q2 |
| Ralph Lauren | FY2024 Q2 | FY2025 Q2 | FY2026 Q2 |
| Moncler | 2023 Q3 | 2024 Q3 | 2025 Q3 |

These rows have September-ending source dates in calendar 2023, 2024 and 2025.
Fiscal labels are not calendar years: Burberry FY2026 Q2 ends in 2025.
The selected periods are **assumed selling-season proxies**, not confirmed
collection sales or independently reported quarters. Repeated adjacent
Burberry/Moncler source values may be allocated half-year amounts.

### Peer selection

Ralph Lauren and Moncler are the handover proposal, chosen before scoring and
fixed for both growth comparisons. Each now produces a separate score.
Burberry cannot be its own peer.

Ralph Lauren overlaps in global premium apparel/lifestyle; Moncler in luxury
apparel and outerwear. Product mix, channels, geography, Moncler group mix and
fiscal calendars can limit comparability. There is no automated peer search,
ranking or selection based on which companies make the score look better.
[inputs/peers.csv](inputs/peers.csv) records the proposal and official IR links.

Growth rates, not revenue levels, are compared within each brand-peer pair. There is no
cross-currency revenue sum and no revenue-size weighting.

### Modes

- `preview`: real downloads, explicit source-period selection, caption suggestions.
  No manual financial/coverage attestation is inferred. Output is provisional.
- `reviewed`: explicit source row IDs, reviewed annotations, dates, collection
  labels and financial/coverage attestations. Checks enforce input consistency;
  they do not independently certify that human annotations are correct.
- `demo`: isolated synthetic example. Never mixed with real company data.

## 4. Commercial metrics

For each entity with revenues O (oldest), E (earlier), and L (latest):

```text
earlier_growth_pct = (E / O − 1) × 100
latest_growth_pct  = (L / E − 1) × 100

earlier_benchmark = configured peer earlier growth
latest_benchmark  = configured peer latest growth

earlier_relative_pp = brand earlier growth − earlier_benchmark
latest_relative_pp  = brand latest growth − latest_benchmark

ir_score = clip(50 + 5 × latest_relative_pp)
```

In real runs the benchmark contains exactly one peer. Adding another peer adds
another score; it does not change existing pair benchmarks. The legacy synthetic
demo uses two peers and their median (equal to their arithmetic mean).

| Field / displayed value | Definition | Unit |
| --- | --- | --- |
| `earlier_growth_pct` | Earlier revenue versus oldest revenue, per entity; explanatory name, calculated internally as `earlier_growth` | % |
| `latest_growth_pct` | Latest revenue versus earlier revenue, per entity; explanatory name, calculated internally as `latest_growth` | % |
| `brand_growth_pct` | Brand latest growth, reviewed output name | % |
| `peer_growth_pct` | This comparison's selected peer latest growth | % |
| `peer_1_growth_pct`, `peer_2_growth_pct` | Legacy aliases: first peer growth; second is missing for pairwise runs | % |
| `peer_median_growth_pct` | Compatibility alias: selected peer growth for pairwise runs; two-peer median only in demo | % |
| `earlier_relative_pp` | Brand-minus-selected-peer earlier growth | pp |
| `latest_relative_pp` | Brand-minus-selected-peer latest growth | pp |
| `ir_score` | Clipped commercial transformation | 0–100 |

Both preview and reviewed score CSVs export `brand_growth_pct`, `peer_growth_pct`,
the legacy peer aliases, and the relative-growth fields when commercial
calculation succeeds. The two per-entity dictionaries (`earlier_growth` and
`latest_growth`) are intermediate calculations, not separate exported columns.
Unavailable comparisons remain in the CSV with gap explanations; failed
calculations do not necessarily populate every intermediate field.

Equal brand/peer growth gives IR50. Outperformance of +3 pp gives IR65.
At +10 pp or more, IR100; at −10 pp or less, IR0. This is a chosen linear
scoring rule, not a fitted relationship.

Reviewed checks require stable metric, scope, currency and period type within
each entity; the same metric across entities; positive growth denominators;
known valid period boundaries; Actual classification; and actual periods ending
by the cutoff. Equivalent periods must have ends 330–400 days apart and duration
differences no greater than 14 days. These checks do **not** automatically verify
cross-company selling-season alignment: comparability still requires review.

## 5. Social data, windows and labels

### Do I have to set a date for the Instagram metric?

Yes. The dates tell the code which posts to compare, and which captured like
counts it is allowed to use. Set them in
[inputs/analyses.csv](inputs/analyses.csv):

| Setting | When to set it | What it controls |
| --- | --- | --- |
| `show_date` | With `route=show` | The local show date. The code automatically derives the collection window and both baseline windows from it. |
| `social_current_start`, `social_current_end` | With `route=fiscal_year` | The inclusive dates of the current social sample. |
| `social_baseline_start`, `social_baseline_end` | With `route=fiscal_year` | The inclusive dates of the previous comparison sample. |
| `timezone` | Both routes | The local timezone used to assign publication timestamps to dates, for example `Europe/London`. |
| `as_of` | Both routes | The latest allowed publication/capture timestamp, including its timezone, for example `2026-10-28T23:59:59Z`. |

For the configured Burberry example, `show_date=2024-09-16` automatically means:

- Collection posts: **16–23 September 2024**.
- Baseline before: **17 August–15 September 2024**.
- Baseline after: **24 September–23 October 2024**.

You do not need to fill the four annual-window fields when using the show route.
Choose an `as_of` that covers the complete post-show baseline. It is a separate
date: **the show date selects the posts; the capture cutoff selects which
observed like counts can be used**. Changing the cutoff can change the likes
even when the publication windows stay the same.

Also check `SOCIAL_START` and `SOCIAL_END` in
[01_extract.ipynb](notebooks/01_extract.ipynb). These control which publication
dates are downloaded, not which dates are ultimately scored. Their current
configured bounds are `2023-01-01` through `2026-10-28`; that does not prove the
source contains every post throughout that range. Make sure the download bounds
cover all your scoring windows. After changing dates, rerun extraction if the
needed posts or eligible captures are not already present, then rerun scoring.
For an earlier historical cutoff, re-extract at that cutoff because the saved
CSV retains only one capture per post.

### See the table and what is retrieved

The code reads this database table:
`denormalized.social_media_bright_data_instagram_posts`.
It has 41 columns, but the query returns only these seven:

| Database column | Returned as | Meaning |
| --- | --- | --- |
| `user_posted` | `handle` | Account that published the post, lowercased |
| `post_id`, falling back to `shortcode` or `url` | `post_key` | Post identifier |
| `date_posted` | `date_posted` | When the post was published |
| `likes` | `likes` | Likes observed when scraped |
| `crawled_at` | `crawled_at` | When the scraper collected the data |
| `url` | `url` | Link to the post |
| `description` | `description` | Post caption |

Here are three actual rows from the saved query results in
[instagram_posts.csv](data/raw/instagram_posts.csv), not synthetic examples or
a fresh database query. Dates are shortened to the minute for readability; all
are UTC. These rows illustrate the retrieved format, not the collection sample
used to score the September 2024 show.

| handle | post_key | date_posted | likes | crawled_at | url | description |
| --- | --- | --- | ---: | --- | --- | --- |
| burberry | 3203989669267147679 | 1 Oct 2023, 13:02 | 5,398 | 20 Oct 2026, 18:41 | [Post](https://www.instagram.com/p/Cx226D0sIuf) | Rose #Burberry |
| burberry | 3204652930941628229 | 2 Oct 2023, 11:00 | 6,793 | 20 Oct 2026, 18:41 | [Post](https://www.instagram.com/p/Cx5NtyZMK9F) | Shield #Burberry |
| burberry | 3206111574246011090 | 4 Oct 2023, 11:21 | 25,517 | 20 Oct 2026, 18:41 | [Reel](https://www.instagram.com/reel/Cx-ZX11M7DS) | Chess #Burberry |

Read the first row as: "Burberry published this post on 1 October 2023. When
it was scraped on 20 October 2026, it had 5,398 likes."

The query retrieves configured accounts' posts within the selected dates. If a
post has several captures, Python keeps the latest one before the cutoff. It
does **not** retrieve individual likes, daily likes or comments. The likes
column is the observed count at capture time, not likes earned during the show
week. The full retrieved table is the linked CSV above.

### What the queried Instagram table contains

The social source is **only Instagram**, accessed through `Dal.shared_db`:
`denormalized.social_media_bright_data_instagram_posts`. There is no TikTok,
Facebook, cross-platform join or peer-account social benchmark in this version.
The source is treated by the code as a flat, denormalized set of scraped post
observations: one record contains a post's identifiers, author, content,
engagement and crawl metadata. Multiple records may refer to the same post at
different captures. A database-enforced unique key or capture-history retention
policy is not established by `information_schema.columns` discovery.

The saved `data/raw/schema_shared.csv` lists 41 columns. The following are the
columns read by `export_social`, with the source types from that discovery:

| Source column | Source type | Export column / treatment | Role in FMI |
| --- | --- | --- | --- |
| `user_posted` | `text` | `lower(user_posted)` becomes `handle` | Select the configured posting account, not posts mentioning/tagging the brand |
| `post_id` | `text` | First choice for `post_key` | Identify a post across capture rows |
| `shortcode` | `text` | Fallback if `post_id` is NULL or `''` | Same identity role; not an additional post |
| `url` | `text` | Last fallback for `post_key`; also exported as `url` | Identity fallback and manual-review link |
| `date_posted` | `text` | Exported unchanged, then parsed as UTC | Publication time determines the social window |
| `likes` | `double precision` | Finite nonnegative values retained; others become NULL | The only engagement measurement used in the score |
| `crawled_at` | `text` | Exported unchanged, then parsed as UTC | Observation time determines cutoff eligibility and capture selection |
| `description` | `text` | Exported as `description`, or SQL NULL if absent | Caption suggestions and manual collection review; not a numeric metric |

The remaining discovered columns are **not selected or used** by this pipeline:

| Group (for navigation, not a verified upstream definition) | Columns and source types |
| --- | --- |
| Other engagement/account counts | `num_comments`, `followers`, `posts_count` (`bigint`); `video_view_count` (`double precision`); `video_play_count`, `engagement_score_view` (`text`) |
| Media/content/context | `hashtags`, `photos`, `videos`, `location`, `latest_comments`, `content_type`, `thumbnail`, `product_type`, `post_content`, `audio`, `videos_duration`, `images`, `alt_text` (`text`); `photos_number` (`bigint`) |
| Other identifiers/discovery fields | `pk`, `content_id`, `discovery_input`, `user_posted_id` (`text`) |
| Profile/collaboration/partnership fields | `has_handshake`, `coauthor_producers`, `tagged_users`, `profile_image_link`, `partnership_details`, `profile_url` (`text`); `is_verified`, `is_paid_partnership` (`boolean`) |
| Crawl-date field | `crawled_date` (`date`); the query uses `crawled_at`, not this field |

For example, having a `followers` column does not mean the score is an engagement
rate. Likewise, `engagement_score_view` is not used as `social_score`. The exporter
does not filter sponsored posts, videos, reels or coauthored posts by these fields.
It uses the same likes-based calculation for every returned eligible post.

### Extraction settings and actual SQL

In `01_extract.ipynb`, `HANDLES` is the distinct lowercased set of scored-brand
handles from configured comparisons; peer handles are not downloaded just
because an entity is a financial peer. `SOCIAL_START` and `SOCIAL_END` are manual
extraction bounds, currently `2023-01-01` and `2026-10-28`. They must cover every
analysis window. `AS_OF` is the **maximum** configured analysis cutoff.

The notebook initializes `AilySettings` before DAL, requests
`default_transaction_read_only=on`, and uses `dal.shared_db`. Before discovery
and extraction, the helper checks `current_setting('transaction_read_only')` is
`on`. Shared credentials are separately resolved by DAL; they are not part of
the CSV. The notebook's shared route uses `dbo`, so these session protections
must not be confused with database-enforced read-only grants.

`discover_columns` reads `information_schema.columns` with a bound schema/table
and `LIMIT 200`; the notebook saves its result to `data/raw/schema_shared.csv`.
The exporter repeats discovery and refuses a missing required column. Caption
`description` is optional; all other source columns in the first table are
required. Discovery checks names, not timestamp validity or data coverage.

With one handle placeholder (more handles add more `%s` placeholders), and
`description` present, the implemented data query is:

```sql
SELECT lower(user_posted) AS handle,
       coalesce(nullif(post_id, ''), nullif(shortcode, ''), nullif(url, ''))
           AS post_key,
       date_posted,
       CASE WHEN likes >= 0 AND likes < 'Infinity'::float8
            THEN likes ELSE NULL END AS likes,
       crawled_at, url, description AS description
FROM denormalized.social_media_bright_data_instagram_posts
WHERE lower(user_posted) IN (%s)
  AND left(date_posted, 10) BETWEEN %s AND %s
  AND (crawled_at IS NULL OR left(crawled_at, 10) <= %s)
  AND coalesce(nullif(post_id, ''), nullif(shortcode, ''), nullif(url, ''))
      IS NOT NULL
ORDER BY date_posted, post_key, crawled_at DESC NULLS LAST
LIMIT %s
```

Bound parameters, in order, are the lowercased handles, `start − 1 day`,
`end + 1 day`, the UTC calendar date of `as_of`, and `limit + 1`. If caption is
absent, `description AS description` becomes `NULL::text AS description`.
The default source-row limit is 25,000; retrieving 25,001 raises an error before
deduplication. Many captures of a few posts can therefore exceed the cap.
There is no `SUM`, `AVG`, `GROUP BY` or collection-caption filter in this SQL.

The day-level SQL comparisons use the first ten characters of **text** fields,
not parsed timestamps. They assume an ISO `YYYY-MM-DD` date prefix and only
coarsely narrow the extract. The extra day on each publication-date edge allows
for local-timezone boundaries. Python then applies the exact capture cutoff;
scoring later applies exact publication timestamps and local-date windows.
Malformed/non-ISO strings can be omitted by SQL before Python sees them.
An unparseable capture is retained as unknown only if its row passes these SQL
filters; SQL NULL captures explicitly pass the capture-date filter.

### From capture rows to the raw CSV

After the query, `export_social`:

1. Parses `crawled_at` with `pd.to_datetime(..., utc=True, errors='coerce',
   format='mixed')`; unparseable captures become missing timestamps.
2. Removes known captures later than the exact `as_of` timestamp **before**
   choosing one row per post. This prevents a later capture on the same UTC day
   from hiding an earlier eligible capture.
3. Sorts captures newest first, unknown timestamps last, and likes descending
   for tied capture times; retains one row per `(handle, post_key)`.
4. Returns exactly `handle, post_key, date_posted, likes, crawled_at, url,
   description`, sorted by publication string and post key. The notebook saves
   these seven columns to `data/raw/instagram_posts.csv`.

The selected likes value is the **observed post-like count at the retained
capture**, not likes earned during the show week. The pipeline neither sums
captures nor subtracts successive captures. Newest capture wins even if its
likes are lower than an earlier capture; if its likes are unusable, scoring
excludes the post rather than falling back to an older usable value.

Synthetic capture example for one post, cutoff `2026-10-28T12:00:00Z`:

| Capture time (UTC) | Likes | Treatment |
| --- | --- | --- |
| 09:00 | 1,200 | Eligible, but superseded by 10:00 |
| 10:00 | 1,300 | Retained observation |
| 18:00 | 9,000 | Removed: after exact cutoff, despite passing the SQL day filter |
| Unknown / SQL NULL | 10,000 | Does not outrank a known eligible capture |

`post_key` is the first non-NULL, non-`''` `post_id`, `shortcode` or `url`.
All three missing means the row is excluded by SQL. Whitespace-only IDs are not
trimmed, URLs are not canonicalized, and the fallback identifiers are not
cross-matched: a post with changing identifier availability can appear under
different keys. The source `pk` is not used as a post identifier. Unlike financial
exports, social exports do not get a hashed `source_row_id`.

The extraction notebook creates `data/processed/collection_review.csv` only if
it does not already exist, with `handle, post_key, date_posted, url, description`
and an empty `collection_related` column. Existing reviews are preserved and
**not automatically extended** with newly downloaded posts; add/review missing
show-week keys yourself. The score join uses handle/post key, not CSV row number.

### Post preparation at scoring time

1. Match the configured brand handle, case-insensitively.
2. Parse publication and capture timestamps in UTC.
3. Reject invalid/future publication timestamps and known captures after `as_of`.
4. Retain one row per handle/post key: latest available capture by cutoff.
   Tied capture timestamps are sorted by likes descending.
5. Convert publication dates into the configured local timezone.
6. Include only finite, nonnegative likes for medians and usable-post counts.
   Zero likes are valid; negative, missing and infinite likes are not.

Scoring repeats capture filtering/deduplication as a safeguard for supplied CSVs,
but it cannot recover capture rows already discarded by extraction. Collection
labels are validated before usable-like filtering: a show-week post with missing
likes still needs a valid true/false label. Captions and URLs are review evidence;
neither is converted to an engagement measurement.

Unknown/unparseable capture timestamps are retained for descriptive mode.
Point-in-time mode excludes them. It does not magically reconstruct older
captures: if the CSV was exported with a later cutoff, rerun extraction for the
desired historical cutoff. Financial historical versions may still be unavailable.

This also matters when different analyses have different cutoffs: notebook 01
exports at their maximum cutoff and keeps only that cutoff's latest capture.
An earlier-cutoff analysis can reject this retained capture but cannot recover
an earlier eligible one from the CSV. Use separately extracted inputs for
different historical cutoffs when necessary. Even point-in-time mode does not
standardize post age (for example, seven days of likes per post) or independently
verify scrape completeness. Preview explicitly forces `point_in_time=False`.

### Show route

Let D be the local show date. Boundaries are inclusive:

| Window | Dates | Inclusion |
| --- | --- | --- |
| Collection sample | D through D+7: 8 local dates | Collection-related brand posts only |
| Baseline before | D−30 through D−1: 30 local dates | All brand posts |
| Baseline after | D+8 through D+37: 30 local dates | All brand posts |

The baseline combines both 30-date windows into **one pool of posts**. Its median
is not an average of the before/after medians, and days with no posts are not
filled with zero likes. A day with more posts contributes more post observations.

Current preview: Burberry Summer 2025, show 16 September 2024,
timezone `Europe/London`. Brand captions announce that date and 4pm BST.

For that show, the actual local-date windows are baseline-before **17 August–15
September 2024**, collection **16–23 September 2024**, and baseline-after **24
September–23 October 2024**. Publication dates assign the windows; a capture
may be much later, provided it does not exceed `as_of`.

Preview caption rules are case-insensitive literal substring matches:

- Caption contains `Summer 2025` only: include, including show guest posts.
- Caption contains `Winter 2024` only: exclude.
- Both strings, neither string, or missing caption: unknown; review needed.
- Existing valid manual true/false labels override suggestions.

This is not image recognition, semantic classification or a coverage audit.
Unknown show-week labels block calculation rather than silently becoming false.
Suggestions are saved separately and never overwrite the user's reviews.
The full post-show baseline must be available by cutoff (at least D+37).

The true/false label is joined by post key within the selected handle. Accepted
label spellings are `true/false`, `yes/no`, and `1/0`, ignoring surrounding spaces
and case. Duplicate review post keys for the selected account block calculation.
The collection filter applies **only to the current show sample**: a baseline
post is not excluded because it mentions another collection or lacks a label.
Caption-preview manual overrides use exact `(handle, post_key)` matching, so
keep review handles in the lowercase form written by extraction.

### Annual route

Use explicit current and previous social date windows, ordered, disjoint and
complete by cutoff. Window lengths may differ by at most one day. Both windows
include all brand posts, without the show-week collection filter. Social and
financial dates are configured separately; equivalent coverage must be reviewed.
Do not compare a partial year with a full prior year.

## 6. Social metrics

`social_component` selects two series of **post-level** likes after the steps in
section 5. For the show route, these are collection-related show-week posts and
the pooled before/after baseline. For `route='fiscal_year'`, they are all usable
posts in the explicit current and previous windows. This is a brand-versus-own-
baseline calculation, not brand-versus-peer social performance.

```text
current_median_likes  = median(usable collection-sample post likes)
baseline_median_likes = median(usable baseline post likes)

social_lift_pct = (current_median_likes / baseline_median_likes − 1) × 100
social_score    = clip(50 + social_lift_pct)
```

For the annual route, "current" means the configured current window, not a
collection sample. Median gives each usable post equal weight; an even-sized
sample uses the average of the two middle observations.

| Field | Definition | Unit |
| --- | --- | --- |
| `current_post_count` | Usable posts in the included sample | Posts |
| `baseline_post_count` | Usable posts in the baseline pool | Posts |
| `current_median_likes` | Median sample likes | Likes/post |
| `baseline_median_likes` | Median baseline likes | Likes/post |
| `social_lift_pct` | Sample median uplift versus baseline median | % |
| `social_score` | Clipped transformation of median-like uplift | 0–100 |
| `unknown_capture_count` | Unknown capture dates in filtered/deduplicated brand data | Posts |

`unknown_capture_count` counts all retained brand posts before sample-window and
usable-like filtering, not just posts used in the two medians. In point-in-time
mode those unknown captures have already been removed, so this count is zero.

No lift gives social 50; +30% lift gives social 80; +50% or more gives social 100;
−50% or worse gives social 0. A score 100 therefore does not mean every post
performed perfectly.

Both samples require at least `min_posts` usable posts (default 5).
This is an editable screening assumption, not a statistical confidence threshold
or a sample-size rule specified by the handover. A zero baseline median makes
lift undefined; insufficient usable samples make social unavailable.

Likes are not normalized by followers, reach, paid spend, format or time since
posting. No sentiment, comment, share or purchase-intent metric is calculated.
Engagement-age comparability and completeness require manual review.

### Worked post-level example (synthetic)

Assume five labeled collection posts have usable likes `[1000, 1200, 1300, 1400,
9000]`. Two baseline-before posts have `[800, 900]`; three baseline-after posts
have `[1000, 1100, 1200]`. All dates/captures are eligible and `min_posts=5`.

```text
current likes, sorted  = [1000, 1200, 1300, 1400, 9000]
baseline likes, pooled = [800, 900, 1000, 1100, 1200]
current_post_count = 5; baseline_post_count = 5
current_median_likes = 1300; baseline_median_likes = 1000
social_lift_pct = (1300 / 1000 − 1) × 100 = 30%
social_score = clip(50 + 30) = 80
weighted social contribution to FMI = 0.30 × 80 = 24 score points
```

The baseline is 1,000, not `(median([800,900]) + median([1000,1100,1200])) / 2
= 975`. The 9,000-like current post is one observation, not extra weight.
A show-week post labeled false is excluded from the current sample, even if
it has many likes; an unlabeled show-week post blocks the calculation. Missing
likes do not become zeros. Neither posting frequency nor total likes is an
additional score component. The same social 80 contributes 24 points to each
configured financial-peer comparison for this brand.

### Tracing a social result or an unavailable component

1. Check `schema_shared.csv` for the discovered source names/types and
   `instagram_posts.csv` for the retained capture, likes and publication time.
2. Check `inputs/analyses.csv` for handle, route, timezone, windows, `as_of`,
   `min_posts`, `point_in_time` and `coverage_reviewed`.
3. Check `collection_review.csv` for manual decisions; in preview, also inspect
   `preview_collection_review.csv` for show-week suggestions and `label_source`.
4. Reapply publication/capture filters, convert publication timestamps into the
   configured timezone, select the two windows and discard unusable likes.
   Compare the resulting counts/medians/lift with the result CSV fields above.

The raw CSV is already capture-deduplicated; it is not a full history of queried
observations. There is currently no saved per-post inclusion/exclusion audit or
automatic coverage reconciliation. If a required review, label, sample-size or
median check fails, `score_analysis` records the error in `gaps`, leaves social
unavailable, and does not compute a full FMI. A missing extracted row is not
evidence that the account had no post on that date.

## 7. Trend metrics

```text
trend_change_pp = latest_relative_pp − earlier_relative_pp
```

Apply these rules **in order**; first match wins:

| Order | Condition | `trend_score` | `trend_label` |
| --- | --- | --- | --- |
| 1 | Change >+2 pp | 70 | Up and coming |
| 2 | Change <−2 pp | 30 | Fallback / weakening |
| 3 | Otherwise, latest and earlier relative performance both ≥+5 pp | 80 | Strong / sustained outperformance |
| 4 | Otherwise | 50 | Neutral / no clear change |

Exactly +2/−2 pp goes to rules 3/4. Code uses a small floating-point tolerance
around boundaries (1e−9). This is not a social trend or a time-series regression:
it compares two consecutive year-on-year peer-relative revenue comparisons.

A brand can be "Up and coming" while still underperforming peers: it may have
moved from −20 pp to −8 pp. Improvement is not the same as leadership.
A strongly outperforming brand that deteriorates by more than 2 pp gets 30,
because the weakening rule comes before sustained-outperformance.

## 8. Combined FMI and classification

```text
fmi = 0.50 × ir_score + 0.30 × social_score + 0.20 × trend_score
```

| Unrounded FMI | `classification` |
| --- | --- |
| 70–100 | High |
| 60 to <70 | Medium |
| 40 to <60 | Neutral |
| 0 to <40 | Low |
| Missing, nonfinite, or outside 0–100 | Unavailable |

Round only for display, never before classifying.
Do not replace unavailable components with zero or 50, and do not redistribute
weights. A missing required component means no full FMI. A valid score 0 is
different from missing data.

The weights, clipping and band boundaries are handover heuristics. They are not
calibrated against historical sales outcomes in this project.

## 9. Forecast scenario metrics

This step is separate from constructing the score. It requires a current forecast
baseline, not last year's actual revenue.

```text
if fmi <= 60:
    uplift_fraction = 0
else:
    uplift_fraction = 0.03 + ((fmi − 60) / 10) × 0.02

uplift_pct        = uplift_fraction × 100
adjusted_forecast = baseline × (1 + uplift_fraction)
absolute_adjustment = adjusted_forecast − baseline

forecast_yoy_pct = (adjusted_forecast / last_year_target_actual − 1) × 100
```

| Field | Meaning | Unit |
| --- | --- | --- |
| `baseline` | Selected Light target-period forecast before adjustment | Revenue units |
| `uplift_pct` | Percentage increase versus that baseline | % |
| `adjusted_forecast` | Baseline after the planning multiplier | Revenue units |
| `absolute_adjustment` | Added revenue versus baseline | Revenue units |
| `forecast_yoy_pct` | Adjusted forecast versus equivalent prior-year actual | % |

At 60, uplift 0%; at 70, uplift 5%; at 80, uplift 7%; at 100, uplift 11%.
There is an intentional jump just above 60 to just above 3%. Low FMI never reduces
the baseline. These rules are planning assumptions, not a fitted sales model.

The configured Burberry preview now selects **FY2026 Q4** as the target forecast
and **FY2025 Q4** as the prior-year actual, as requested. In the saved Light
extract these rows have reported dates 31 March 2026 and 31 March 2025,
respectively. Fiscal `2026 Q4` is not calendar Q4 2026. Forecast values are a
current snapshot, not a forecast version historically frozen at the show date.

The scenario reads the FMI from each configured Burberry-peer comparison and
applies the uplift rule above to the selected FY2026 Q4 forecast. An FMI at or
below 60 yields 0% uplift and leaves the baseline unchanged. The resulting
adjusted value can therefore
equal the source forecast even though the FMI-driven scenario ran. Scores above
60 produce the nonzero uplift specified by the formula; this configuration
change does not alter that rule.

Reviewed mode requires target/actual metric, scope and currency to match and
an explicit quarter baseline. Prior-year target must match period type and
equivalent fiscal dates (within 14 days of a one-year shift). A valid baseline
must be finite and positive. Missing prior-year actual prevents forecast YoY,
but need not prevent an adjustment when the baseline and score are available.

Preview money-like outputs remain in **unverified raw Light units**, without a
guessed currency label. Missing/ambiguous target rows leave the already computed
score intact and write an unavailable scenario status.

## 10. Original two-peer demo and pairwise examples

The unchanged `MODE="demo"` exercises the original handover median method.
Suppose latest brand growth 8%, peer growth 4% and 6%; earlier brand growth 4%,
peer growth 5% and 5%. Sample median likes 13,000; baseline median 10,000.

```text
latest peer median = (4 + 6) / 2 = 5%
latest_relative_pp = 8 − 5 = +3 pp
earlier_relative_pp = 4 − 5 = −1 pp

IR = clip(50 + 5×3) = 65
social lift = (13,000 / 10,000 − 1) × 100 = 30%
social score = clip(50 + 30) = 80
trend change = 3 − (−1) = +4 pp → trend score 70

FMI = 0.5×65 + 0.3×80 + 0.2×70 = 70.5 → High
uplift = 3% + ((70.5−60)/10)×2% = 5.1%
baseline 100m → adjusted 105.1m; absolute adjustment 5.1m
prior-year actual 102m → forecast YoY ≈3.04%
```

Different denominators explain why a 5.1% uplift versus baseline is not the same
as 3.04% growth versus last year. The notebook's `MODE="demo"` reproduces this
example. An IR0/social 100/trend70 combination would instead give FMI 44, Neutral:
a saturated social score cannot erase weak commercial performance.

For the same synthetic inputs, real pairwise mode instead produces:

| Comparison | Latest brand growth | Peer growth | Relative | IR | Social | Trend | FMI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Brand vs peer1 | 8% | 4% | +4 pp | 70 | 80 | 70 | 73 (High) |
| Brand vs peer2 | 8% | 6% | +2 pp | 60 | 80 | 70 | 68 (Medium) |

Both earlier peer growth rates are 5%, so earlier relative performance is −1 pp.
The brand social 80 is unchanged across the two pairs. A third configured peer
adds a third calculation using that peer's actual growth history.

## 11. Status fields, gaps and limitations

Analysis settings are carried into reviewed output rows; they are not measured
scores:

| Setting | Meaning |
| --- | --- |
| `brand`, `handle` | Display brand and Instagram account to score |
| `financial_entity` | Revenue entity selected for the brand, including an explicitly labeled proxy |
| `peer_entity`, `peer_name` | Selected comparison entity and display name, sourced from peers.csv |
| `comparison_mode` | `single-peer` for real CSV runs |
| `peer_rationale`, `peer_limitations` | Peer selection notes copied from peers.csv |
| `peer_1`, `peer_2` | Legacy demo settings; ignored by real CSV pair expansion |
| `route` | `show` or `fiscal_year`; determines social windows and financial requirements |
| `show_date`, `timezone` | Show's local calendar date and timezone for post assignment |
| `social_current_start`, `social_current_end` | Inclusive current social window for the annual route |
| `social_baseline_start`, `social_baseline_end` | Inclusive prior social window for the annual route |
| `min_posts` | Minimum usable posts required in each social sample |
| `comparability_reviewed` | Manual attestation of peer/scope/period comparability |
| `coverage_reviewed` | Manual attestation of coverage, engagement ages and collection review |
| `proxy_label` | Required nonempty explanation when reviewed financial inputs use a proxy |

| Field | Meaning |
| --- | --- |
| `as_of` | Explicit observation cutoff with timezone; not proof of historical availability |
| `point_in_time` / `input_mode` | Historical-cutoff restrictions versus descriptive current snapshot |
| `status` | Preview/scenario provisional label or unavailable scenario state |
| `validated_collection_fmi` | False for preview; no automatic certification |
| `financial_proxy` / `score_scope` | Entity-proxy flag and scope description; preview additionally carries source-period-proxy status |
| `limitations` | Preview's assumptions and unresolved evidence gaps |
| `gaps` | Reviewed component/scenario validation failures |
| `source_units` / `scenario_currency` | Unverified preview units versus reviewed currency metadata |
| `target_fiscal_year`, `target_quarter`, `target_reported_date` | Preview target source labels |
| `target_period_start`, `target_period_end` | Reviewed target fiscal boundaries |
| `interpretation` | Reminder that planning uplift is not causal |

Missing a forecast scenario does not erase a valid FMI; therefore a reviewed row
can contain both a score and scenario-related `gaps`. Read which step failed.

Preview selection checks one finite positive revenue row per requested
entity/year/quarter/classification and rejects future actual source dates.
It does not prove metadata, fiscal equivalence, source provenance or coverage.
Reviewed mode adds consistency checks and manual attestations, but historical
forecast versions remain unavailable unless independently supplied with evidence.
A later current snapshot must not be presented as a forecast known at show time.

No bootstrap intervals, hypothesis tests, trained weights, outlier model,
FX adjustment, inflation adjustment, seasonality model, follower normalization or
causal attribution is implemented.

## 12. Where to inspect or change the calculation

- Notebook mode: `MODE`; brand/cutoff/social settings in `inputs/analyses.csv`,
  peer edges in `inputs/peers.csv`, entity codes and source periods in `inputs/entities.csv`.
- Notebook commercial cells: configured source-row choices and one result per pair.
- `fmi.py`: `social_component`, `trend_score`, `band`, `sales_scenario`;
  reviewed financial validation in `commercial_components` and `score_analysis`.
- Manual inputs: `inputs/analyses.csv, financial_selection.csv,
  financial_annotations.csv, external_financials.csv, peers.csv, entities.csv`.
- Manual social review: `data/processed/collection_review.csv`; both modes use it,
  but preview does not turn any coverage review flag on.
- Evidence: `data/processed/preview_financials.csv,
  preview_collection_review.csv, preview_target_financials.csv`, or
  `selected_financials.csv` in reviewed mode.
- Results: `results/provisional_fmi_scores.csv, provisional_sales_scenario.csv`,
  `fmi_scores.csv` (reviewed), `demo_fmi_scores.csv` (synthetic).

Review actual values in the local CSVs/notebook. Do not commit extracted data,
business results, credentials or notebook outputs.
