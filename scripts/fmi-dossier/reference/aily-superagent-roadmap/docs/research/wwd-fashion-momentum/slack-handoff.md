# Slack handoff draft

Destination: [#temp-index-wwd-arceo-2026](https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB). Prepared for review; this file does not indicate that the message was posted.

---

<@U0B3AML7YV8> <@U06GLNMTRKK> — the Fashion Momentum data and repeatable prospect-update workflow are ready for handover in [PR #164](https://github.com/Aily-Labs/aily-superagent-roadmap/pull/164).

Current snapshot: **71 delivery rows, 34 assessed prospects and 22 scoped provisional overall scores** (17 own-unit, 5 parent hybrids). The other 49 totals remain blank; partial/coverage evidence is retained. Allen's final mapping and all 70 CSV company/code/domain pairings are preserved.

**For each new or updated prospect report:**
1. Pull the PR branch `codex/wwd-weighted-delivery-table` while the PR is open; after merge, pull `main`. Open the repository in Codex and use `$update-fashion-momentum` with the exact prospect name and report path.
2. Follow the [step-by-step guide](https://github.com/Aily-Labs/aily-superagent-roadmap/blob/codex/wwd-weighted-delivery-table/docs/research/wwd-fashion-momentum/prospect-update-guide.md): record the report hash/history, reporting periods and comparison, update the source observations and explicitly select the delivered cycle. Keep missing data blank and parent proxies labelled.
3. Maintain one concise insight plus one KPI and label for each Revenue, Social and Trend card. Include the quarter/year/event and what it is compared with. Copy-only corrections must preserve the indices. Keep the documented commercial display corrections, including RIMOWA's manual Stable label with no own-revenue KPI.
4. Run `python3 docs/research/wwd-fashion-momentum/refresh-delivery.py --output-dir outputs/fashion-momentum-review`, review the changed previews, then run the same command with `--check` instead of `--output-dir`. Commit inputs, JSON, Markdown, Excel and the build manifest together. CI checks freshness and consistency.

**Design:** use the tracked [Excel Delivery sheet](https://github.com/Aily-Labs/aily-superagent-roadmap/blob/codex/wwd-weighted-delivery-table/docs/research/wwd-fashion-momentum/weighted-delivery.xlsx) for the card descriptors, concise insights and highlighted KPIs. The original Fashion Momentum Index stays in column C; the separate normalized 70–98 display is in S; KPI values/labels are T:Y. Preserve unavailable states.

**App:** consume [weighted-delivery.json](https://github.com/Aily-Labs/aily-superagent-roadmap/blob/codex/wwd-weighted-delivery-table/docs/research/wwd-fashion-momentum/weighted-delivery.json), especially `records.page2.<component>.cardKpi` for units, precision, qualifiers and periods. Check identity, selected cycle, copy, original/normalized index and blank states against Excel. Internal `momentum` means Trend/IR; internal `strength` means the Revenue card's retained peer-relative strength score. Display descriptors can differ from numeric categories.

**Data next steps:** fill the outstanding own-revenue/peer/baseline gaps, verify primary references and obtain raw social rows/capture details for provisional samples. These results are not a validated cross-company leaderboard.

The **Excel is part of the repo**. Canonical JSON inputs drive the rebuild; direct Excel edits need to be carried back into inputs and rebuilt before committing. Repo changes do not automatically publish the app or enable environments.
