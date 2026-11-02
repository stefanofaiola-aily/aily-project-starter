# Fashion Momentum — implementation instructions and remaining inputs

**Current scoring/content reference:** [four-page weighted delivery table](weighted-delivery.md), following Peter's later 50% IR / 30% Social / 20% Trend request. The original source requirements below preserve the earlier attention-method handoff. Reuse routing/style/CTA/QA requirements; obtain weighted-method inputs before populating final components, index or board.

The research and content package is prepared for **Allen's final 25 prospects / 26 environment mappings**. The next deliverable is the Fashion Momentum experience in the WWD ARCEO 2026 event card. This PR contains the brief, content and evidence; application implementation and deployment remain pending.

**Designer starting point:** follow the [step-by-step workflow](designer-workflow.md), using the [delivery table — actual current data, screen states, copy and final gaps](delivery-table.md). It covers every prospect and separates methodology inputs from the dated public snapshot. Harriet's later mapping and retailer-method proposals are recorded there as open decisions; Allen's final mappings remain unchanged.

## Confirmed scope and requirements

| Requirement | Implementation instruction | Source |
| --- | --- | --- |
| Prospect list | Use the exact company, Light Environment and Type mappings in [prospect-inputs.json](prospect-inputs.json). There are 18 unique brands and 7 retailers. Reuse Marc Jacobs content in WHP Global and Marc Jacobs. | Allen's final workbook, confirmed by Peter; [workbook source](https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793068399761549) |
| Placement | Add Fashion Momentum as the first card inside the WWD ARCEO 2026 event card, above the AI quiz, in each mapped environment. | [Main handoff](https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793068013785899) |
| Presentation | Use sleek black Agent Playground styling, dominant score/metric numerals and minimal default text. Keep supporting research accessible through details. Fashion Momentum and the AI-readiness quiz need distinct labels. | Bianca's messages and teaser images supplied by Peter; [setup brief](setup.md) |
| Brand experience | Brand name, eligible index or missing-data state, compact signal values and actual growth, evidence details, brand-board view and a short invitation to contribute internal data. | [Main handoff](https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793068013785899), [method](https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793067741340779) |
| Score calculation | For each usable positive-reference pair: growth = current/reference − 1; raw = 50 × current/reference; bounded = min(75, max(60, raw)). Average usable bounded components equally; round only the final display half-up. Preserve actual growth and source scope. | [Method](https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793067741340779), [later bounds discussion](https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793068484544519) |
| Missing evidence | Two comparisons support a disclosed provisional two-signal calculation; one supports growth only; none means a missing-data state. Never create a baseline, zero score or rank for unavailable data. | [Setup and methodology](setup.md), [score evidence](score-results.md) |
| Retailers | Reuse the same brand board in all 7 retailer environments. Keep their own fashion-show index empty; personalize the internal-data invitation. | [Placement and retailer instructions](https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793068013785899) |
| Public social/media layer | Add the dated public-presence snapshot to every prospect, preserving account scope, selection exceptions, hidden counters, source types and publication dates. Keep related-account posts and Exemplar banners separate. | Peter's request to extend the review to all prospects; [public-presence findings](public-presence-review.md) |
| CTA | Use exactly **Unlock November signal** and record the actual click through the app's existing authenticated analytics integration. Wire a real confirmation/next step. | [Tracked CTA discussion](https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793064007537279) |
| Showroom | Add the WWD event card and the highest-momentum eligible brand's report to Fashion Showroom after comparable scoring and QA. No showroom winner is selected by this package. | [Main handoff](https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793068013785899) |
| Environment QA | Test every mapped environment and the showroom. The original handoff names Jimena López-Barbado Salmerón and Franziska Schlauss for testing, and Peter/Reynaldo for delivery. | [Main handoff](https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793068013785899) |

## Prepared in this PR

- [x] Final company/environment mapping with workbook provenance.
- [x] 25 personalized packages and [individual prompts](prompts/), including proposed internal-data fields and invitations.
- [x] Score inputs, calculations, reported versus estimated classifications and explicit gaps.
- [x] Light dossier screening for 24 prospects, pinned source URLs and hashes; official Exemplar company context for the remaining prospect.
- [x] Public review of 27 Instagram profiles and 78 posts, plus 25 verified source texts across 24 prospects. Belmont's media result is a source gap.
- [x] Portable offline rebuild and mapping/content checks.

Current score coverage: **five provisional public indices** (Coach 75, Fendi 69, Ralph Lauren 68, Burberry 64, Calvin Klein 62); a separate **unverified VS team candidate of 69**; **TOM FORD EMV growth only**; and **eleven brand evidence gaps**. The full comparable 18-brand leaderboard and a production-validated score are still unavailable. Current public counters and coverage examples do not fill historical comparison gaps.

## Inputs and decisions needed for implementation

| Needed | Current state | Purpose |
| --- | --- | --- |
| Target application repository or content editor, with its schema and publish path | Unresolved in this package | Implement the card, score/detail view, shared board and showroom in the actual WWD experience. |
| Live IDs for all 26 environment mappings and relevant company/content IDs | Display names only; IDs unverified | Route each brand or retailer package correctly. Repository dossier slugs/role codes do not establish live identity. |
| Existing Agent Playground components and WWD card/quiz locations | Visual direction captured; components not inspected | Apply the requested styling and card order using the target app's conventions. |
| Matched current/reference measurements and provider definitions | Five public drafts still need window/definition validation; remaining brand gaps recorded individually | Support a comparable production board and showroom selection. Peter confirmed no additional provider exports are available. |
| CTA destination and existing analytics event convention | Exact label and tracking requirement confirmed; destination/event name open | Implement and verify the click and confirmation without implying a report, subscription or data connection has already been delivered. |
| Live Light dossier version/identity parity, if used by the app | Repository screening captured; live store not checked | Preserve the prospect's actual brand/parent scope. |
| Deadline timezone | Original “8 am our time” remains unspecified | Resolve delivery timing. The earlier “40” prospect request is superseded by Allen's final list. |

## Proposed choices requiring product review

These are recommendations, separate from the confirmed requirements above:

- Use existing components for horizontal board bars, current-brand highlighting and an information/details control. The original handoff supplies a bar-board reference; exact layout and interaction need review in the target app.
- Allen's Partner Lounge congratulations popup is proposed copy. Confirm the final next step when wiring the CTA; an upload flow or subscription is not specified.
- Use the existing analytics event if it fits. `fashion_momentum_november_signal_clicked` is a suggested event name only; use the target app's conventions and verify the recorded payload.
- A revenue-planning scenario is optional and belongs in supporting details, with supported same-quarter YoY assumptions. Fashion attention does not establish sales growth.

## Implementation and acceptance checklist

- [ ] Resolve target app/content schema and all live environment/company IDs.
- [ ] Implement the card above the quiz, with the requested black metric-led styling and compact copy.
- [ ] Bind brand content to its mapped environment; reuse Marc Jacobs once across its two mappings.
- [ ] Preserve provisional, growth-only and missing-data states and their accessible source details.
- [ ] Keep public social/media snapshots dated and separate from the momentum calculation; preserve null counters and scope exceptions.
- [ ] Validate the comparable measurement set before promoting a full leaderboard or choosing a showroom winner. A five-brand draft must remain labelled partial/provisional.
- [ ] Use the same shared board in all seven retailer environments; keep retailer-specific index empty.
- [ ] Wire the CTA and its confirmation; verify the click in analytics.
- [ ] Add the eligible showroom copy after scoring and environment QA.
- [ ] Have the named testers review all 26 environments and the showroom: correct brand, score state, metrics, board, highlight, source details, CTA and analytics.

Use [review.md](review.md) to review per-prospect copy, [prospect-packages.json](prospect-packages.json) for structured content, [setup.md](setup.md) for the full source brief, and [README.md](README.md) for the offline rebuild.
