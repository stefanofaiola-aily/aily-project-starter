import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [inputFile, outputDir] = process.argv.slice(2);
if (!inputFile || !outputDir) throw new Error('Usage: node build-weighted-workbook.mjs weighted-delivery.json output-directory');
const publishedData = JSON.parse(await fs.readFile(inputFile, 'utf8'));
// Exercise the unchanged report calculations first; apply explicit score revisions afterward.
const data = structuredClone(publishedData);
data.records = data.records.map(r => r.scoreRevision ? r.scoreRevision.previousCalculatedRecord : r);
data.deliveryRows = data.deliveryRows.map(r => {
  const record = publishedData.records.find(record => record.prospectName === r.prospect);
  return record?.scoreRevision ? record.scoreRevision.previousCalculatedDeliveryRow : r;
});
// The calculation regression phase uses the exact pre-revision normalization.
// The final Delivery formulas below use the delivered cohort after revisions.
const calculatedDisplayIndices = data.overallDisplayNormalization.calculatedBaseline?.displayIndices;
if (calculatedDisplayIndices) {
  data.deliveryRows.forEach((row, index) => {
    row.normalizedFashionMomentumIndex = calculatedDisplayIndices[row.prospect];
    data.records[index].page1.normalizedFashionMomentumIndex = row.normalizedFashionMomentumIndex;
  });
}
const workbook = Workbook.create();
const delivery = workbook.worksheets.add('Delivery');
const details = workbook.worksheets.add('Details');
const cycles = workbook.worksheets.add('Cycles');
const peers = workbook.worksheets.add('Peers');
const campaigns = workbook.worksheets.add('Campaigns');
const method = workbook.worksheets.add('Method');
const enablement = workbook.worksheets.add('Enablement');
const brandSocial = workbook.worksheets.add('Brand social');
const revenueProxies = workbook.worksheets.add('Revenue proxies');
const contentEnd = 6 + data.records.length;
const newReportCompanies = new Set(['Moncler', 'Coach', 'Estée Lauder', "Victoria's Secret & Co.", 'GAP Inc', 'Lilly Pulitzer', 'Target', "Kohl's", 'Ulta Beauty', 'Amazon Fashion', 'PacSun', 'Calvin Klein', 'Tommy Hilfiger', 'VF Corporation', 'Foot Locker', 'RIMOWA', 'Bloomingdales', 'G-III Apparel Group', 'ME+EM', 'David Yurman', 'NORDSTROM', 'Fendi', 'Belmont Park Village', 'Christian Louboutin', 'New Balance', 'Marc Jacobs', 'DKNY', 'J.Crew', 'Jacquemus', 'Lafayette 148', 'Exemplar Luxury Group', 'LVMH', 'Louis Vuitton', 'Missoni', 'Five Below']);
const font = 'Arial';
const navy = '#183328';
const amber = '#FFF2CE';
const green = '#E6F0E9';
function col(n) { let out = ''; while (n) { n--; out = String.fromCharCode(65 + n % 26) + out; n = Math.floor(n / 26); } return out; }
function init(sheet, title, lastCol, lastRow) {
  sheet.showGridLines = false;
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.font = { name: font, size: 10, color: '#222222' };
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.verticalAlignment = 'center';
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.rowHeight = 25;
  sheet.getRange(`A1:${lastCol}${lastRow}`).format.columnWidth = 18;
  sheet.getRange('A2').values = [[title]];
  sheet.getRange('A2').format.font = { name: font, size: 15, bold: true };
  sheet.getRange(`A3:${lastCol}3`).format.borders = { bottom: { style: 'thin', color: '#AEBAB1' } };
}
function table(sheet, row, headers, values, name) {
  const end = row + values.length;
  const last = col(headers.length);
  sheet.getRange(`A${row}:${last}${row}`).values = [headers];
  sheet.getRange(`A${row + 1}:${last}${end}`).values = values;
  const t = sheet.tables.add(`A${row}:${last}${end}`, true, name);
  t.showFilterButton = true;
  sheet.getRange(`A${row}:${last}${row}`).format = {
    fill: navy, font: { name: font, size: 10, bold: true, color: '#FFFFFF' },
    wrapText: true, horizontalAlignment: 'center', verticalAlignment: 'center', rowHeight: 55,
    borders: { insideVertical: { style: 'thin', color: '#FFFFFF' } },
  };
  sheet.freezePanes.freezeRows(row);
  sheet.freezePanes.freezeColumns(2);
  return end;
}
const date = value => value ? new Date(`${value}T00:00:00Z`) : null;
const sentimentFormula = ref => `IF(ISNUMBER(${ref}),IF(${ref}>=70,"Good",IF(${ref}>=40,"Neutral","Needs improvement")),"")`;
const momentumLabel = ref => `IF(ISNUMBER(${ref}),IF(${ref}>=75,"High",IF(${ref}>60,"Medium",IF(${ref}>=40,"Neutral","Low"))),"")`;
const socialLabel = ref => `IF(ISNUMBER(${ref}),IF(${ref}>60,"Positive",IF(${ref}<40,"Negative","Neutral")),"")`;
const strengthLabel = (change, gap) => `IF(AND(ISNUMBER(${change}),ISNUMBER(${gap})),IF(${change}>2,IF(${gap}>=0,"Strong","Up and coming"),IF(${change}<-2,"Fallback","Neutral")),"")`;

init(method, 'Scoring method and source definitions', 'J', 257);
const commercialCorrections = Object.entries(data.sourceContext.commercialStrengthCorrections.companies);
const commercialGrowthRows = new Map(commercialCorrections.map(([name], i) => [name, 213 + 2 * i]));
method.getRange('A212:B212').values = [['Commercial-strength growth inputs', data.sourceContext.commercialStrengthCorrections.authority]];
commercialCorrections.forEach(([name, c]) => {
  const row = commercialGrowthRows.get(name);
  method.getRange(`A${row}:B${row + 1}`).values = [
    [`${name} ${c.currentPeriod} growth`, c.currentGrowth],
    [`${name} ${c.referencePeriod} growth`, c.referenceGrowth],
  ];
});
method.getRange('A212:B218').format.wrapText = true;
method.getRange('A212:B218').format.rowHeight = 55;
method.getRange('B213:B218').setNumberFormat('0.0000%');
method.getRange('B213:B218').format.fill = amber;
method.getRange('B213:B218').format.horizontalAlignment = 'right';
method.getRange('A219:B221').values = [
  ['Commercial display basis', 'Own growth-rate change = (current growth − reference growth) × 100 pp. Source precision supplied by the user; original financial inputs retained.'],
  ['Corrected descriptors', 'TOM FORD Stable (+1.0 pp); Victoria’s Secret Up and coming (+4.41 pp); Bloomingdale’s Up and coming (+4.9 pp).'],
  ['Separate scoring basis', 'Commercial descriptors/KPIs change; the peer-relative numerical Strength score/category and both Fashion Momentum Index columns remain unchanged.'],
];
method.getRange('A219:B221').format.wrapText = true;
method.getRange('A219:B221').format.rowHeight = 55;
method.getRange('A223:B224').values = [
  ['RIMOWA commercial descriptor', 'Stable is a user-directed display override. Supporting standalone strength data was not supplied; the revenue KPI remains blank and the undisclosed-revenue insight is retained.'],
  ['Override scoring treatment', 'The manual descriptor does not change the numerical peer-relative Strength score/category or either Fashion Momentum Index column.'],
];
method.getRange('A223:B224').format.wrapText = true;
method.getRange('A223:B224').format.rowHeight = 55;
method.getRange('A5:B13').values = [
  ['Momentum weight', data.weights.ir], ['Social weight', data.weights.social], ['Strength weight', data.weights.trend],
  ['Momentum intercept', 50], ['Momentum multiplier per pp', 5], ['Social intercept', 50], ['Score minimum', 0], ['Score maximum', 100], ['Final display decimals', 1],
];
method.getRange('D4:E8').values = [
  ['Strength category (agreed rule)', 'Score'],
  ...['Strong', 'Up and coming', 'Neutral', 'Fallback'].map(category => [category, data.trendScoreMapping[category]]),
];
method.getRange('G4:I7').values = [
  ['Overall sentiment', 'Minimum', 'Upper bound'], ['Good', 70, '100 inclusive'], ['Neutral', 40, '<70'], ['Needs improvement', 0, '<40'],
];
for (const range of ['D4:E4', 'G4:I4']) method.getRange(range).format = { fill: navy, font: { name: font, bold: true, color: '#FFFFFF' } };
method.getRange('A5:A13').format.columnWidth = 29;
method.getRange('B5:B7').setNumberFormat('0%');
method.getRange('B5:B13').format.fill = amber;
method.getRange('D5:D8').format.columnWidth = 28;
method.getRange('G4:I8').format.columnWidth = 20;
method.getRange('A16:B24').values = [
  ['IR performance', 'Own matched-quarter or annual YoY growth minus agreed peer median (pp). Preserve retail/DTC, brand or consolidated scope and growth basis.'],
  ['Momentum score', 'Former IR score. Clamp 50 + 5 × peer-relative gap in pp between 0 and 100.'],
  ['Social lift', 'Comparison / baseline median metric − 1. Likes by default; G-III uses three selected-brand comment lifts. Runway -15/-1 and 0/+7; annual/matched proxies retain their own windows.'],
  ['Social subscore', 'Clamp 50 + social lift in percent between 0 and 100.'],
  ['Strength classification', 'Agreed rule: change >+2 pp and current gap ≥0 Strong; >+2 and gap <0 Up and coming; −2 to +2 inclusive Neutral; <−2 Fallback.'],
  ['Overall and sentiment', `${data.weights.ir * 100}% Momentum + ${data.weights.social * 100}% Social + ${data.weights.trend * 100}% Strength. Sentiment: <40 Needs improvement; 40–<70 Neutral; ≥70 Good.`],
  ['Missing inputs', 'Blank is unavailable, never zero. Weights are not redistributed. Domain is only filled from Allen.'],
  ['Leaderboard', 'Provisional category boards rank by displayed normalized Delivery S. IR peer rank is separate. See the category method below.'],
  ['Adding a cycle/peer set', 'Update structured inputs and rebuild. Peer growth is matched by cycle + peer key; sorting Peers retains each benchmark.'],
];
method.getRange('A25:B25').values = [['Copy refresh', 'Insights and saved worked examples are authored snapshot copy. Review them when inputs change; score formulas do not rewrite prose.']];
method.getRange('A25:B25').format.wrapText = true;
method.getRange('A25:B25').format.rowHeight = 55;
method.getRange('A27:B32').values = [
  ['Attendee source', 'Fashion Momentum Attendees.xlsx, Sheet2, Slack file F0CCF1PK8L9'],
  ['Attendee source link', 'https://ailylabsworkspace.slack.com/archives/C0CC6BBHJMB/p1793068399761549'],
  ['Domains', 'Allen has no website-domain column. Email domains and company codes now come from the ARCEO CSV.'],
  ['Scoring source', [...new Set(Object.values(data.sourceDocuments).map(s => s.fileName))].join('; ')],
  ['Source precision', 'Reported IR 34.49 gives 61.245 → 61.2. Rounded growth inputs derive IR 34.50; precision review pending.'],
  ['Evidence', 'Supplied URLs/references, counts and windows retained. Independent checks, full sampled archives and capture timing remain open.'],
];
method.getRange('A33:B33').values = [['Ralph Lauren precision', 'Spring 2026: 0.5 × 100 + 0.3 × 39.74 + 0.2 × 30 = 67.922 → 67.9.']];
method.getRange('A34:B36').values = [
  ['Enablement source', data.enablementSource.fileName],
  ['Expanded coverage', `${data.enablementRows.length} CSV companies; ${data.records.length} content rows (25 Allen + 43 CSV additions + 6 report additions).`],
  ['CSV mapping', 'Exact company/environment matches; explicit G-III alias. Code/domain pairings retained; added scopes/environments pending.'],
];
method.getRange('A37:B40').values = [
  ['Tom Ford calculation', 'Autumn/Winter 2026: 0.5 × 57.5 + 0.3 × 100 + 0.2 × 30 = 64.75 → 64.8. Same-season change −6.5 pp → Fallback.'],
  ['Tom Ford financial scope', 'Fashion total-brand organic/comparable adjusted growth includes wholesale and excludes Beauty. Related Zegna benchmark; issuer definitions differ.'],
  ['Tom Ford social scope', 'Fashion-filtered tomford posts; Europe/Paris. Latest sample: 5 baseline / 4 show posts. Capture ages and archive unavailable.'],
  ['Tom Ford selling window', 'Completed Jul–Sep 2026 quarter is a proxy; Autumn/Winter 2026 selling continues into Q4. No validated cross-brand rank.'],
];
method.getRange('A41:B49').values = [
  ['Coach normalization', 'Source Strength 70 / Up and coming becomes agreed Strong / 80: improving +4.87 pp and current lead +18.55 pp. Overall 68.2 → 70.2.'],
  ['ELC earlier calculation', 'Group Strength 70 / Up and coming becomes agreed Strong / 80: improving about +14.30 pp with current lead +5.129 pp. Earlier overall 79.3 → 81.3; current supplied revision is on Score revisions.'],
  ['Moncler selected cycle', 'FW2025 = 49.8, Momentum 27.54 / Low, Social 100 / Positive, Strength 30 / Fallback. FW2026 social only; financial outcome pending.'],
  ['Financial periods', 'Coach, ELC and Victoria’s Secret use annual financial proxies. Preserve own/peer dates separately; no inferred dates where the source omits them.'],
  ['ELC social scope', 'Corporate @esteelaudercompanies: FY2026 versus FY2025 median likes, not runway-window lift or all owned-brand account reach.'],
  ['ELC identity', 'Group candidate on CSV Estée Lauder row. Company-code/group identity and Light environment remain pending; no brand score or board rank implied.'],
  ['Missing references', 'ELC/Victoria’s Secret name financial documents without URLs. Full sampled archives/capture ages remain unavailable; Coach supplies selected show posts.'],
  ['Source score bands', 'ELC/Victoria’s Secret source bands use 50/70. Delivery uses the agreed overall 40/70 bands; source categories/totals remain provenance.'],
  ['Reported precision', 'ELC arithmetic uses Momentum 75.65 (display 75.7), while its table says 75.6. VS change −2.234 pp from available precision differs from reported −2.24.'],
];
method.getRange('A50:B54').values = [
  ['Gap portfolio result', 'FY2025: 0.5 × reported Momentum 32.9747 + 0.3 × Social 100 + 0.2 × Strength 70 = 60.48735 → 60.5 / Neutral.'],
  ['Gap campaign aggregation', 'Median of eligible brand campaign lifts, minimum 3 posts in each window. Gap / Old Navy / Banana Republic eligible; Athleta excluded. No pooled group likes.'],
  ['Gap financial precision', 'Supplied USD billions derive gap −3.392 pp, Momentum 33.0397 and improvement +3.723 pp; source says −3.41 / 32.9747 / +3.71. Rounded gaps give +3.70. Both totals round to 60.5.'],
  ['Gap scope and timing', 'Annual consolidated group revenue, not campaign sales; FY2023 53 weeks, later years 52. Old Navy announcement 22 Oct / available 28 Oct; Q3/Q4 context only.'],
  ['Gap evidence and CTA', 'Archive retained 20 Oct 2026 is not capture timing. Links/archive/likes ages unverified. GAP Inc routing and Gap-brand invitation retained; group-versus-brand CTA needs review.'],
];
method.getRange('B16:B49').format.columnWidth = 112;
method.getRange('B16:B49').format.wrapText = false;
method.getRange('B30').format.wrapText = true;
method.getRange('A30:B30').format.rowHeight = 140;
method.getRange('B18').format.wrapText = true;
method.getRange('A18:B18').format.rowHeight = 42;
method.getRange('B38:B40').format.wrapText = true;
method.getRange('A38:B40').format.rowHeight = 42;
method.getRange('B41:B49').format.wrapText = true;
method.getRange('A41:B49').format.rowHeight = 42;
method.getRange('B50:B54').format.columnWidth = 112;
method.getRange('B50:B54').format.wrapText = true;
method.getRange('A50:B54').format.rowHeight = 55;
method.getRange('A55:B60').values = [
  ['Lilly Pulitzer FY2025', '42.9 / Neutral: Momentum 40.70, Social 28.38, Strength 70. Segment sales, not Oxford group; prior peer growth/reference revenues absent. Source financial-only 49.1 remains separate.'],
  ['Lilly annual social sample', 'Instagram median 770 / 125 posts → 603.5 / 230 posts (−21.6%). Missing months and unequal coverage; matched Apr 26–Oct 22 instead rises 4.1%. Captured 20 Oct 2026.'],
  ['Target financial-only', 'Momentum 40.5 / Neutral and Strength 30 / Fallback. Social and weighted overall unavailable. Source 37.5 rescales 50/20 weights; it is not the 50/30/20 delivery total.'],
  ['Target identity and scope', 'CSV Target type/environment remain unknown. Consolidated operating revenue includes ancillary income. Kohl’s total-revenue benchmark must not use its standalone merchandise-only inputs.'],
  ['Kohl’s FY2025', '48.9 / Neutral under agreed 40/70 bands; source says Needs improvement using 50/70. Momentum 35.5849, Social 70.4819, Strength 50. Retailer candidate stays outside brand board.'],
  ['Kohl’s TikTok coverage', '8 final-month FY2024 posts versus 180 FY2025 posts; accumulated likes and unequal season/content mix. January lift 45% is unused sensitivity. Snapshot label 2026-10-27T09:50:52.084760, timezone unspecified; raw records/SQL not supplied.'],
];
method.getRange('B55:B60').format.columnWidth = 112;
method.getRange('B55:B60').format.wrapText = true;
method.getRange('A55:B60').format.rowHeight = 55;
method.getRange('A61:B64').values = [
  ['Superseded Ulta partial result', 'Social 32.57 / Negative (display 32.6), from Instagram medians 1,285 / 268 posts → 1,061 / 667. Own sales grow 9.71%, but Momentum, Strength and overall stay blank.'],
  ['Superseded Ulta benchmark gate', 'Two comparable peers and two growth observations required. Douglas has two eligible annual revenue values and September dates; Sephora standalone series is missing. LVMH mixed group is rejected. Keep benchmark Incomplete until validated.'],
  ['Amazon Fashion social proxy', 'Same Sep 27–Oct 26 windows: 43 / 62 posts → 14 / 27 posts (−67.44%), Social 0 / Negative. This is a real capped component zero; Momentum, Strength, overall and ranks remain blank. No standalone Fashion revenue series.'],
  ['Amazon scope and post ages', 'Matching 30-day dates, not full-year history. 2025 posts have an extra year to accrue likes. Available annual medians 39/37 are unused context; short Instagram history is excluded. No demand/sentiment inference or Amazon/GMV revenue substitution.'],
];
method.getRange('B61:B64').format.columnWidth = 112;
method.getRange('B61:B64').format.wrapText = true;
method.getRange('A61:B64').format.rowHeight = 55;
method.getRange('A65:B67').values = [
  ['Superseded PacSun social', 'Social 42.2 / Neutral: medians 643 → 593 (−7.78%), Jan 1–Oct 6 in 2025/2026. Calendar proxy, not verified PacSun fiscal years. Momentum, Strength, rank, overall and overall sentiment stay blank.'],
  ['PacSun missing likes', '179 numeric-like posts / 265 total (86 missing, 32.5%) versus 61 / 104 (43 missing, 41.3%). Recorded zeros enter medians; missing likes never become zero. Sparse 2024 annual sample and short TikTok history are unused.'],
  ['PacSun scope and evidence', 'Own revenue series/fiscal dates unverified; A&F/Urban Outfitters annual sales are context only. Preserve Allen Brand classification/environment and both domains. Capture 2026-10-20T18:41:26Z; older post ages and selective missingness limit interpretation. Source SQL/raw 369 rows unverified.'],
];
method.getRange('B65:B67').format.columnWidth = 112;
method.getRange('B65:B67').format.wrapText = true;
method.getRange('A65:B67').format.rowHeight = 55;
method.getRange('A68:B72').values = [
  ['Calvin Klein separate result', 'Collection Spring 2026: 38.5 / Needs improvement. Momentum 5.075 (display 5.1/Low), Social 100 / Positive, Strength 30 / Fallback. Growth −6.81% vs rounded peer median +2.175%; source total 38.5438 retained, recomputed 38.5375. Not the PVH 47.3 portfolio score.'],
  ['Tommy Hilfiger separate result', 'Spring 2026 campaign: 54.7/Neutral. Momentum 37.325 (display 37.3/Low), Social 100 / Positive, Strength 30 / Fallback. Growth −0.36%; source total 54.6568 retained, recomputed 54.6625. Campaign anchor does not verify launch timing.'],
  ['PVH Strength and comparison', 'Prior-year same-season financial positions extend the method beyond two comparable runway collections. Calvin Klein rounded change −9.92 pp vs source −9.93. Tommy −2.03 pp is only 0.03 below Fallback; Spring 2025 runway and Spring 2026 campaign social lifts are not controlled comparisons.'],
  ['PVH evidence and precision', 'Brand revenue includes retail, wholesale/licensing. Ralph Lauren is earlier seasonal proxy; G-III partly licenses PVH. Rounded growth and medians feed scores; hidden component precision is not backsolved. Source Tommy prior Momentum 47.4 vs derived 47.45/display 47.5. Raw pairs, exact peer dates and social archives/capture ages are missing. Future cycles are partial; Tommy Spring 2027 has one event post.'],
  ['PVH identity and portfolio', 'Calvin Klein retains PVH routing, pvh.com/pvh and invitation. Tommy is a user-requested report addition: no Allen/CSV environment/domain/code/invitation; parent PVH is context only. Portfolio 47.3 is unused. Source FY 2025 annual revenues CK 3964.0/TH 4770.9 USDm, weights 45.38%/54.62%, exclude Heritage; these are not quarterly growth inputs.'],
];
method.getRange('B68:B72').format.columnWidth = 112;
method.getRange('B68:B72').format.wrapText = true;
method.getRange('A68:B72').format.rowHeight = 65;
method.getRange('A73:B78').values = [
  ['VF annual portfolio result', 'FY 2026: 38.4 / Needs improvement; Momentum 28.7482/Low, Social 33.5085176/Negative, Strength 70/Up and coming. Reported gap −10.58→−4.25 improves 6.33 pp. Continuing operations exclude Supreme retrospectively; latest Dickies revenue ends12 Nov 2025.'],
  ['VF portfolio social inputs', 'Brand social contains The North Face, Vans and Timberland fiscal medians/counts. Each included brand contributes one lift; median −16.49%, no pooled/revenue-weighted likes. North Face earlier first quarter uncovered; Timberland 7/9 missing-like rows excluded. Missing included inputs block the group; zero likes remain numeric.'],
  ['VF precision and sensitivity', 'Source Momentum 28.7482 is preserved; rounded USD-billion own/peer revenues derive28.8144 and alternate total 38.5. Social source 33.5085 agrees with derived 33.5085176. Columbia calendar ends are about 3 months earlier. Excluding North Face gives unused source 39.5 sensitivity.1127 raw rows/SQL and original precision unverified.'],
  ['Foot Locker full-year proxy', 'FY 2025:36.0/Needs improvement, Momentum 0/Low, Social 100/Positive, Strength 30/Fallback. Revenue proxies calculates unaudited21.786502−14.108943=7.677559 USD bn; score baseline is reported 7.988. FY 2024 residual 7.988334 is a cross-check only,0.334 million above reported sales.'],
  ['Foot Locker scope and social', 'Acquired8 Sep 2025; post-acquisition segment3.106 bn is partial, not annual numerator. Missing FY 2023 sales not backsolved;53-week base, acquisition/intercompany assumptions and JD GBP/Academy USD growth require review. January TikTok284/3 posts→457.5/10(+61.09%) is a tiny year-end proxy; later YTD −44.1% and recent Instagram unused.'],
  ['VF / Foot Locker identity', 'VF is a report addition with unknown audience type, blank domain/code/environment/CTA. Foot Locker retains CSV footlocker.com/footlocker and unknown type/environment/invitation. No Dick’s group score or routing is substituted. Source50/70 bands are superseded by agreed40/70; both totals remain Needs improvement. Capture labels/raw archives are unverified.'],
];
method.getRange('B73:B78').format.columnWidth = 112;
method.getRange('B73:B78').format.wrapText = true;
method.getRange('A73:B78').format.rowHeight = 65;
method.getRange('A79:B87').values = [
  ['RIMOWA parent hybrid', 'FY2025: 46.3 / Neutral. Momentum 50.4084 and Strength 30 measure LVMH Fashion and Leather Goods versus Gucci/Hermès; Social 50.3650 measures RIMOWA. Standalone RIMOWA annual sales and overall remain unavailable. Preserve rimowa.com/rimowa; no parent routing.'],
  ['RIMOWA peer-gap sensitivity', 'Agreed parent gap 2.1374→0.0817 gives −2.0557 pp, only 0.0557 below Fallback. Neutral Strength 50 gives 50.3. Both 46.3 and 50.3 are Neutral under agreed 40/70 bands; source Needs improvement used a 50-point cutoff.'],
  ['RIMOWA social coverage', 'Instagram 2,740 / 269 posts → 2,750 / 176 (+0.365%). All 445 comparison posts have numeric likes and all 12 months are represented. Accumulated captures 20 Oct 2026, UTC grouping; monthly presence is not a census or equal post ages. FY2023 one-post social sample excluded.'],
  ['Bloomingdales parent hybrid', 'FY2025: 37.1 / Needs improvement. Momentum 47.5246 and Strength 30 measure Macy’s Inc. merchandise sales; Social 24.6019 measures Bloomingdale’s. Parent gap +2.17→−0.50 gives −2.67 pp. Other/credit-card/construction revenue excluded; earlier fiscal base has 53 weeks.'],
  ['Bloomingdale’s own sales', 'Own comparable sales grew 7.4% on an owned/licensed/marketplace basis, retained unused in the Momentum calculation. The parent hybrid does not establish declining Bloomingdale’s sales. Preserve Allen Retailer classification, Bloomingdales environment, invitation and bloomingdales.com/bloomingdales.'],
  ['Bloomingdales social sample', 'Instagram 628 / 23 posts → 468.5 / 202 (−25.4%). Earlier sample begins 16 Apr 2024, covers 9 months and misses Feb/Mar/Aug; latest covers 12 months with 3 recorded zeros. Matched-month sensitivity 37.2 unused. Capture 20 Oct 2026, America/New_York fiscal grouping; raw archives/SQL unsupplied.'],
  ['Ulta alternate method', 'Earlier report supplies company-only 73.1 / Good using absolute own sales growth and acceleration. This separate method is unused for standard Delivery and ranks. Standard Momentum, Strength, overall and rank stay blank under the Incomplete peer benchmark gate; Social stays 32.6 / Negative.'],
  ['Source history', `${data.sourceReportCount} active unique reports, ${data.receivedSourceReportCount} received files and ${Object.keys(data.selectedCycles).length} assessments. Superseded Ulta, Belmont and Louboutin reports/hashes remain in source history. Belmont/Louboutin replacements have identical content.`],
  ['Scoped result coverage', 'Thirty provisional formula/supplied totals: 24 own-unit/WWD proxies plus 6 parent hybrids. Six standard partials, two coverage-only; accepted Nordstrom adds a 31st delivered total. Hybrids keep standalone-brand overall null. All 74 identities, 26 mappings and 70 CSV pairings remain; G-III retains its separate group row with no inferred routing.'],
];
method.getRange('B79:B87').format.wrapText = true;
method.getRange('A79:B87').format.rowHeight = 65;
method.getRange('A107:B116').values = [
  ['G-III company assessment', 'FY2026 33.3 / Needs improvement: Momentum 12.6235/Low, Social 70/Positive comment activity, Strength 30/Fallback. Reported gap +7.47→−7.48 deteriorates 14.95 pp. Consolidated annual sales, not DKNY standalone/campaign sales; licence wind-down/mix/calendars limit peers.'],
  ['G-III comment portfolio', 'Brand social adds DKNY 8/113 posts→17/93, Donna Karan 13/53→9.5/54 and Karl Lagerfeld 37.5/46→45/87. Equal median lifts +112.5%, −26.92%, +20% give +20%; Aug–Dec 2024/2025, all five months and numeric comments. Metric in AA; no pooled or revenue-weighted comments.'],
  ['G-III metric limits', 'DKNY/Donna Karan likes cannot support a common likes comparison. Karl Lagerfeld likes fell 43.6% despite rising comments. Comments may include complaints/spam/replies; Positive means comment activity only. Snapshot October 2026; exact date/time, source table/timezone and raw records not supplied.'],
  ['G-III identity / sensitivity', 'A separate consolidated-group report row has unknown type and no inferred environment/domain/code/invitation. DKNY and its existing g-iii.com/giiiapparelgroup mapping are unchanged. Social 0–100 gives overall 12.3–42.3; under agreed 40/70 the upper end is Neutral, correcting the source <50 sensitivity claim.'],
  ['ME+EM latest filed year', 'FY2025 ended 26 Jan 2025: 86.0 / Good, Momentum 100 / High, Social 100 / Positive, Strength 30 / Fallback. Filed turnover 81.977→119.511→147.945 GBPm; Reiss parent/restated base and J.Jill restated USD revenue retained. FY2026 filed turnover absent at cutoff; no forecast/relabel.'],
  ['ME+EM tiny social baseline', 'Matched Oct–Dec 2023/2024: 523 median/2 posts→1335.5/6(+155.35%). Earlier Nov uncovered; latest covers all three months. Full available2/22-post proxy also caps Social100. Holding financials fixed, overall 56–86: Good depends on this provisional two-post baseline. Capture 20 Oct 2026; Europe/London publication dates.'],
  ['Superseded David Yurman partial', 'Social 65.19 / Positive (display 65.2) from 1086 / 106 posts→1251/95 in Jul/Aug/Sep/Nov/Dec 2024/2025. October excluded, sparse May/June excluded; non-contiguous months, not continuous Jul–Dec or verified fiscal years. Own revenue/fiscal dates, Momentum, Strength, rank and overall remain unavailable.'],
  ['David Yurman sensitivity', 'Wider May24–Dec31 gives 8.02% / Neutral, medians 1103 / 135 posts→1191.5/126; unused sensitivity. Signet/Richemont 3-year figures are candidate context with misaligned January/March years and scope, not an approved calendar benchmark. All 201 main posts numeric, UTC grouping/capture 20 Oct 2026; archive 500 posts/SQL unverified.'],
  ['Nordstrom current partial', 'FY2025 Social 34.8101 / Negative (display 34.8): 750.5 / 50 posts→636.5/198. Current FY2025 revenue after 20 May 2025 acquisition unverified, so standard Momentum, observed Strength, rank and overall stay blank. Retain Allen NORDSTROM retailer identity/environment, nordstrom.com/nordstrom and invitation.'],
  ['Nordstrom source proxy', 'Source 60.7 / Neutral mixes FY2024 group Momentum 80.6079 / High with FY2025 nameplate Social 34.8101 and assumed Neutral Strength 50. It remains separate supporting context. Historical Momentum/rank 1 of 3 are FY2024 only; group includes Rack. Assumed 50 is never an observed Neutral component. Parent/partial sales substitution rejected.'],
];
method.getRange('B107:B116').format.wrapText = true;
method.getRange('A107:B116').format.rowHeight = 65;
method.getRange('G10:J21').values = [
  ['Component', 'Sentiment', 'Normalized score', 'Classification rule'],
  ['Momentum', 'Low', '<40', 'Gap <−2 pp'], ['Momentum', 'Neutral', '40–60 inclusive', 'Gap −2 to +2 pp'],
  ['Momentum', 'Medium', '>60 and <75', 'Gap >+2 and <+5 pp'], ['Momentum', 'High', '≥75', 'Gap ≥+5 pp'],
  ['Social', 'Negative', '<40', 'Lift <−10%'], ['Social', 'Neutral', '40–60 inclusive', 'Lift −10% to +10%'],
  ['Social', 'Positive', '>60', 'Lift >+10%'],
  ['Strength', 'Strong', 80, 'Change >+2 pp; latest gap ≥0'],
  ['Strength', 'Up and coming', 70, 'Change >+2 pp; latest gap <0'],
  ['Strength', 'Neutral', 50, 'Change −2 to +2 pp inclusive'],
  ['Strength', 'Fallback', 30, 'Change <−2 pp'],
];
method.getRange('G10:J10').format = { fill: navy, font: { name: font, bold: true, color: '#FFFFFF' } };
method.getRange('G10:J21').format.columnWidth = 29;
method.getRange('G23').values = [['Agreed 27 Oct 2026: Burberry +7.80 pp improvement and −3.10 pp current gap → Up and coming / 70; overall 61.2.']];

// Keep each supplied CSV company, code and domain together, including parent mappings.
init(enablement, 'ARCEO company codes and email domains', 'G', 6 + data.enablementRows.length);
enablement.getRange('A4').values = [[`${data.enablementSource.fileName}: 70 source companies. Additional company scopes and Light environments remain pending.`]];
const enablementEnd = table(enablement, 6,
  ['CSV company', 'Email domain(s)', 'Company code', 'Linked content prospect', 'Allen Light environment(s)', 'Mapping state', 'CSV source row'],
  data.enablementRows.map(r => [r.company, r.emailDomainRaw, r.companyCode, r.linkedProspects.join(' / '),
    r.lightEnvironments.join(' / '), r.status, r.sourceRow]), 'ARCEOEnablement');
enablement.freezePanes.freezeColumns(1);
enablement.getRange(`A1:A${enablementEnd}`).format.columnWidth = 50;
enablement.getRange(`B1:B${enablementEnd}`).format.columnWidth = 68;
enablement.getRange(`C1:C${enablementEnd}`).format.columnWidth = 42;
enablement.getRange(`D1:E${enablementEnd}`).format.columnWidth = 35;
enablement.getRange(`F1:F${enablementEnd}`).format.columnWidth = 50;
enablement.getRange(`G1:G${enablementEnd}`).format.columnWidth = 18;
enablement.getRange(`A7:C${enablementEnd}`).format.fill = amber;
enablement.getRange(`G7:G${enablementEnd}`).format.fill = amber;

const cycleRows = data.cycles.map(c => ({ ...c }));
for (const r of data.records.filter(r => !r.selectedCycleKey)) {
  cycleRows.push({ cycleKey: `${r.prospectId}-pending-cycle`, company: r.prospectName });
}
const cycleRowByKey = new Map(cycleRows.map((c, i) => [c.cycleKey, i + 7]));
const cycleKeyByProspect = new Map(data.records.map(r => [r.prospectId, r.selectedCycleKey || `${r.prospectId}-pending-cycle`]));

init(peers, 'Peer observations', 'P', 6 + data.peerObservations.length);
peers.getRange('A4').values = [['Reported growth is preserved; benchmark lookups use cycle + peer keys, so Peers may be sorted.']];
const peerValues = data.peerObservations.map(p => [p.cycleKey, p.prospect, p.peer, date(p.financialPeriodStart), date(p.financialPeriodEnd),
  p.reportedGrowth, p.revenueCurrent, p.revenueReference, null, p.currency, p.revenueScope, p.sourceDocument,
  p.sourceUrl || p.sourceReferences.join('; '), p.evidenceStatus, null, null]);
assert.equal(new Set(data.peerObservations.map(p => `${p.cycleKey} | ${p.peer}`)).size, data.peerObservations.length, 'Duplicate cycle + peer keys');
const peerEnd = table(peers, 6, ['Cycle key', 'Prospect', 'Peer', 'Financial period start', 'Financial period end', 'Reported YoY growth', 'Current revenue (scope units)', 'Reference revenue (scope units)', 'Growth used', 'Currency', 'Revenue scope', 'Source document', 'Source URL / reference', 'Review state', 'Observation key', 'Growth available'], peerValues, 'PeerObservations');
for (let row = 7; row <= peerEnd; row++) {
  peers.getRange(`I${row}`).formulas = [[`=IF(COUNT(G${row}:H${row})=2,IF(H${row}>0,G${row}/H${row}-1,""),IF(ISNUMBER(F${row}),F${row},""))`]];
  peers.getRange(`O${row}`).formulas = [[`=A${row}&" | "&C${row}`]];
  peers.getRange(`P${row}`).formulas = [[`=IF(ISNUMBER(I${row}),1,0)`]];
}
peers.getRange(`D7:E${peerEnd}`).setNumberFormat('dd mmm yyyy');
peers.getRange(`F7:F${peerEnd}`).setNumberFormat('0.00%');
peers.getRange(`I7:I${peerEnd}`).setNumberFormat('0.00%');
peers.getRange(`G7:H${peerEnd}`).setNumberFormat('#,##0.000');
peers.getRange(`F7:H${peerEnd}`).format.fill = amber;
peers.getRange(`J7:N${peerEnd}`).format.fill = amber;
peers.getRange(`I7:I${peerEnd}`).format.fill = green;
peers.getRange(`A1:C${peerEnd}`).format.columnWidth = 27;
peers.getRange(`K1:N${peerEnd}`).format.columnWidth = 48;
data.peerObservations.forEach((p, index) => {
  if (p.prospect === 'TOM FORD' || newReportCompanies.has(p.prospect)) {
    const row = index + 7;
    peers.getRange(`K${row}:N${row}`).format.wrapText = true;
    peers.getRange(`A${row}:N${row}`).format.rowHeight = 82;
  }
});
peers.getRange(`O1:O${peerEnd}`).format.columnWidth = 70;
peers.getRange(`O7:O${peerEnd}`).format.fill = green;
peers.getRange(`P7:P${peerEnd}`).format.fill = green;
const peerNamesByCycle = new Map();
data.peerObservations.forEach(p => {
  const names = peerNamesByCycle.get(p.cycleKey) || [];
  names.push(p.peer); peerNamesByCycle.set(p.cycleKey, names);
});
const peerSlots = Math.max(1, ...Array.from(peerNamesByCycle.values(), names => names.length));
const peerGrowthLastColumn = col(63 + peerSlots);

// Portfolio children preserve brand medians/counts; only eligible lifts enter the median.
const campaignRows = data.campaignObservations || [];
init(campaigns, 'Brand campaign inputs for portfolio social attention', 'Y', 6 + campaignRows.length);
campaigns.getRange('A4').values = [['Gap Inc: three eligible campaigns; Athleta excluded. Windows derive from anchors and -15/-1, 0/+7 rules. Retention is separate from capture timing.']];
const campaignEnd = table(campaigns, 6,
  ['Campaign key', 'Parent cycle', 'Brand', 'Campaign', 'Social anchor', 'Baseline start', 'Baseline end', 'Event start', 'Event end',
    'Baseline median likes', 'Event median likes', 'Baseline posts', 'Event posts', 'Minimum posts / window', 'Derived lift', 'Eligible for median',
    'Reported lift', 'Attention signal', 'Anchor URL', 'Caption terms (case insensitive; flexible whitespace)', 'Selling-quarter context',
    'Archive retained', 'Likes capture date', 'Source / review', 'Exclusion reason'],
  campaignRows.map(c => [c.campaignKey, c.cycleKey, c.brand, c.campaign, date(c.anchorDate), date(c.baselineWindowStart), date(c.baselineWindowEnd),
    date(c.eventWindowStart), date(c.eventWindowEnd), c.baselineMedianLikes, c.eventMedianLikes, c.baselinePostCount, c.eventPostCount,
    c.minimumPostsPerWindow, null, null, c.reportedLiftPercent === null ? null : c.reportedLiftPercent / 100, null, c.sourceUrl,
    c.captionTerms.join('; '), c.sellingQuarterContext, date(c.archiveRetentionDate), date(c.captureDate), `${c.sourceDocument}; ${c.evidenceStatus}`, null]),
  'PortfolioCampaigns');
const campaignRanges = new Map();
campaignRows.forEach((c, index) => {
  const row = index + 7;
  campaigns.getRange(`P${row}`).formulas = [[`=IF(AND(COUNT(J${row}:K${row})=2,J${row}>0,COUNT(L${row}:N${row})=3,N${row}>=3,L${row}>=N${row},M${row}>=N${row}),"Yes","No")`]];
  campaigns.getRange(`O${row}`).formulas = [[`=IF(P${row}="Yes",K${row}/J${row}-1,"")`]];
  campaigns.getRange(`R${row}`).formulas = [[`=${socialLabel(`IF(ISNUMBER(O${row}),50+O${row}*100,"")`)}`]];
  campaigns.getRange(`Y${row}`).formulas = [[`=IF(P${row}="Yes","","Missing baseline or fewer than minimum posts in either window")`]];
  const rows = campaignRanges.get(c.cycleKey) || [];
  rows.push(row); campaignRanges.set(c.cycleKey, rows);
});
campaigns.freezePanes.freezeColumns(3);
campaigns.getRange(`E7:I${campaignEnd}`).setNumberFormat('dd mmm yyyy');
campaigns.getRange(`V7:W${campaignEnd}`).setNumberFormat('dd mmm yyyy');
campaigns.getRange(`J7:K${campaignEnd}`).setNumberFormat('#,##0.0');
campaigns.getRange(`O7:O${campaignEnd}`).setNumberFormat('+0.0%;-0.0%;0.0%');
campaigns.getRange(`Q7:Q${campaignEnd}`).setNumberFormat('+0.0%;-0.0%;0.0%');
campaigns.getRange(`J7:N${campaignEnd}`).format.fill = amber;
campaigns.getRange(`Q7:Q${campaignEnd}`).format.fill = amber;
for (const column of ['O', 'P', 'R', 'Y']) campaigns.getRange(`${column}7:${column}${campaignEnd}`).format.fill = green;
campaigns.getRange(`A1:D${campaignEnd}`).format.columnWidth = 30;
campaigns.getRange(`S1:Y${campaignEnd}`).format.columnWidth = 40;
campaigns.getRange(`D7:D${campaignEnd}`).format.wrapText = true;
campaigns.getRange(`S7:Y${campaignEnd}`).format.wrapText = true;
campaigns.getRange(`A7:Y${campaignEnd}`).format.rowHeight = 84;

const socialChildren = data.portfolioSocialObservations || [];
init(brandSocial, 'Selected-brand and banner social inputs', 'AA', 6 + socialChildren.length);
brandSocial.getRange('A4').values = [['One equal lift per included brand/banner: VF likes, G-III comments, Exemplar historical banner likes. Metric in AA. Missing included inputs block the parent; zeros stay numeric.']];
const brandSocialEnd = table(brandSocial, 6,
  ['Social key', 'Parent cycle', 'Brand', 'Account', 'Baseline start', 'Baseline end', 'Comparison start', 'Comparison end',
   'Baseline median metric', 'Comparison median metric', 'Baseline numeric posts', 'Comparison numeric posts', 'Baseline total posts', 'Comparison total posts',
   'Baseline missing metric', 'Comparison missing metric', 'Include in main median', 'Derived lift', 'Activity signal', 'Reported lift', 'Source account / reference', 'Capture label / timezone', 'Publication timezone', 'Coverage limits', 'Selection rule', 'Source report', 'Metric'],
  socialChildren.map(r => [r.socialKey, r.cycleKey, r.brand, r.account, date(r.baselineWindowStart), date(r.baselineWindowEnd), date(r.comparisonWindowStart), date(r.comparisonWindowEnd),
    r.baselineMedianMetricValue ?? r.baselineMedianLikes, r.comparisonMedianMetricValue ?? r.comparisonMedianLikes, r.baselineNumericPostCount, r.comparisonNumericPostCount, r.baselineTotalPostCount, r.comparisonTotalPostCount,
    null, null, r.includedInMainScore ? 'Yes' : 'No', null, null, r.reportedLiftPercent/100, r.sourceUrl || r.sourceReferences?.join('; ') || null,
    r.captureTimezone ? `${r.captureTimestamp} (${r.captureTimezone})` : r.captureTimestamp, r.publicationTimezone, r.sampleLimits, r.selectionRule, r.sourceDocument, r.socialMetric || 'Likes']), 'FiscalBrandSocial');
const portfolioRanges = new Map();
socialChildren.forEach((r, i) => {
  const row = i+7;
  brandSocial.getRange(`O${row}`).formulas = [[`=IF(AND(ISNUMBER(M${row}),ISNUMBER(K${row})),M${row}-K${row},"")`]];
  brandSocial.getRange(`P${row}`).formulas = [[`=IF(AND(ISNUMBER(N${row}),ISNUMBER(L${row})),N${row}-L${row},"")`]];
  brandSocial.getRange(`R${row}`).formulas = [[`=IF(AND(Q${row}="Yes",COUNT(I${row}:L${row})=4,I${row}>0,K${row}>0,L${row}>0),J${row}/I${row}-1,"")`]];
  brandSocial.getRange(`S${row}`).formulas = [[`=${socialLabel(`IF(ISNUMBER(R${row}),50+R${row}*100,"")`)}`]];
  const rows = portfolioRanges.get(r.cycleKey) || []; rows.push(row); portfolioRanges.set(r.cycleKey, rows);
});
brandSocial.getRange(`E7:H${brandSocialEnd}`).setNumberFormat('dd mmm yyyy');
brandSocial.getRange(`I7:J${brandSocialEnd}`).setNumberFormat('#,##0.0');
brandSocial.getRange(`K7:P${brandSocialEnd}`).setNumberFormat('#,##0');
brandSocial.getRange(`R7:R${brandSocialEnd}`).setNumberFormat('+0.00%;-0.00%;0.00%');
brandSocial.getRange(`T7:T${brandSocialEnd}`).setNumberFormat('+0.00%;-0.00%;0.00%');
brandSocial.getRange(`E7:N${brandSocialEnd}`).format.fill = amber;
brandSocial.getRange(`Q7:Q${brandSocialEnd}`).format.fill = amber;
brandSocial.getRange(`Q7:Q${brandSocialEnd}`).dataValidation = { rule: { type: 'list', values: ['Yes', 'No'] } };
for (const range of [`O7:P${brandSocialEnd}`, `R7:S${brandSocialEnd}`]) brandSocial.getRange(range).format.fill = green;
brandSocial.getRange(`A1:B${brandSocialEnd}`).format.columnWidth = 35;
brandSocial.getRange(`C1:D${brandSocialEnd}`).format.columnWidth = 25;
brandSocial.getRange(`I1:T${brandSocialEnd}`).format.columnWidth = 23;
brandSocial.getRange(`U1:Z${brandSocialEnd}`).format.columnWidth = 50;
brandSocial.getRange(`AA1:AA${brandSocialEnd}`).format.columnWidth = 20;
brandSocial.getRange(`U7:AA${brandSocialEnd}`).format.wrapText = true;
brandSocial.getRange(`A7:AA${brandSocialEnd}`).format.rowHeight = 80;

const proxyInputs = data.revenueProxyObservations || [];
init(revenueProxies, 'Foot Locker annual revenue proxy inputs', 'P', 6 + proxyInputs.length);
revenueProxies.getRange('A4').values = [['USD billions. Unaudited combined pro forma less legacy Dick’s; FY2024 residual is a cross-check, FY2025 is scored.']];
const proxyEnd = table(revenueProxies, 6,
  ['Proxy key', 'Business', 'Period', 'Period start', 'Period end', 'Combined pro forma sales', 'Legacy Dick’s sales', 'Derived Foot Locker residual',
   'Reported standalone sales', 'Residual less reported', 'Used for scored revenue', 'Currency / units', 'Financial source', 'Limitations', 'Source report', 'Reported proxy'],
  proxyInputs.map(r => [r.proxyKey, r.company, r.periodLabel, date(r.periodStart), date(r.periodEnd), r.combinedProFormaRevenue, r.legacyDicksRevenue, null,
    r.reportedFootLockerRevenue, null, r.usedForScoredRevenue ? 'Yes' : 'No', `${r.currency} / ${r.revenueUnit}`, r.sourceUrl, r.limitations, r.sourceDocument, r.reportedDerivedProxy]), 'AnnualRevenueProxies');
const proxyRowByKey = new Map();
proxyInputs.forEach((r, i) => {
  const row = i+7; proxyRowByKey.set(r.proxyKey, row);
  revenueProxies.getRange(`H${row}`).formulas = [[`=IF(COUNT(F${row}:G${row})=2,F${row}-G${row},"")`]];
  revenueProxies.getRange(`J${row}`).formulas = [[`=IF(AND(ISNUMBER(H${row}),ISNUMBER(I${row})),H${row}-I${row},"")`]];
});
revenueProxies.getRange(`D7:E${proxyEnd}`).setNumberFormat('dd mmm yyyy');
for (const range of [`F7:J${proxyEnd}`, `P7:P${proxyEnd}`]) revenueProxies.getRange(range).setNumberFormat('#,##0.000000');
for (const range of [`F7:G${proxyEnd}`, `I7:I${proxyEnd}`, `P7:P${proxyEnd}`]) revenueProxies.getRange(range).format.fill = amber;
for (const column of ['H','J']) revenueProxies.getRange(`${column}7:${column}${proxyEnd}`).format.fill = green;
revenueProxies.getRange(`A1:A${proxyEnd}`).format.columnWidth = 37;
revenueProxies.getRange(`C1:C${proxyEnd}`).format.columnWidth = 43;
revenueProxies.getRange(`F1:J${proxyEnd}`).format.columnWidth = 27;
revenueProxies.getRange(`L1:O${proxyEnd}`).format.columnWidth = 52;
revenueProxies.getRange(`C7:C${proxyEnd}`).format.wrapText = true;
revenueProxies.getRange(`L7:O${proxyEnd}`).format.wrapText = true;
revenueProxies.getRange(`A7:P${proxyEnd}`).format.rowHeight = 80;

init(cycles, 'Seasonal and annual inputs and component calculations', peerGrowthLastColumn, 6 + cycleRows.length);
cycles.getRange('A4').values = [['Amber = source inputs. Green = calculated. Momentum/Social retain reported precision; Strength derives from the agreed rule. Source review remains open.']];
const cycleValues = cycleRows.map(c => [c.cycleKey, c.company, c.collection || null, date(c.showDate), date(c.financialPeriodStart), date(c.financialPeriodEnd),
  c.reportedBrandGrowth ?? null, null, null, c.reportedIrSubscore ?? null, null, null,
  c.baselineMedianMetricValue ?? c.baselineMedianLikes ?? null, c.comparisonMedianMetricValue ?? c.showMedianLikes ?? null, null, c.reportedSocialSubscore ?? null, null, null,
  c.priorCycleKey || null, null, null, c.trendComparison || null, c.reportedStrengthCategory || null, null, null, null, null, null, null, null,
  c.brandRevenueCurrent ?? null, c.brandRevenueReference ?? null, c.currency || null, c.revenueScope || null, date(c.socialCaptureDate), c.baselinePostCount ?? null, c.showPostCount ?? null,
  c.sourceDocument || null, c.socialArchiveReference || c.sourceDocument || null,
  c.sourceNotes || (c.sourceDocument ? 'Reported components seed the example. Primary sources, snapshot counts/timing and precision need review.' : null),
  c.reportedRelativeMomentumPp ?? null, null, null, null, c.reportedStrengthSubscore ?? null, c.reportedOverall ?? null, null,
  null, c.financialPeriodType || null, c.financialPeriodLabel || null, c.socialComparisonType || null,
  c.baselineWindow || null, c.showWindow || null, c.measurementSubject || null, c.reportedStrengthChangePp ?? null, null, null,
  c.reportedFinancialOnlyScore ?? null, c.reportedFinancialOnlySentiment || null, c.socialSampleNotes || null,
  c.socialCaptureTimestamp ? c.socialCaptureTimezone ? `${c.socialCaptureTimestamp} (${c.socialCaptureTimezone})` : c.socialCaptureTimestamp : null,
  c.reportedOverallSentiment || null, c.financialBenchmarkStatus || null]);
cycleValues.forEach(row => row.push(...Array(peerSlots).fill(null)));
const cycleEnd = table(cycles, 6, ['Cycle key', 'Prospect', 'Collection / campaign', 'Show date', 'Financial period start', 'Financial period end',
  'Own reported YoY growth', 'Peer median growth', 'IR gap (pp)', 'Reported Momentum score', 'Derived Momentum score', 'Momentum score used',
  'Baseline median metric', 'Comparison median metric', 'Social lift', 'Reported social score', 'Derived social score', 'Social score used',
  'Earlier cycle key', 'Earlier IR gap (pp)', 'Trend change (pp)', 'Comparison type', 'Reported strength category', 'Strength score',
  'Overall unrounded', 'Overall display', 'Overall sentiment', 'Data state', 'IR peer rank', 'Peer count incl. brand',
  'Current revenue (scope units)', 'Reference revenue (scope units)', 'Currency', 'Revenue scope', 'Social capture date', 'Baseline post count', 'Comparison post count',
  'IR source', 'Social source', 'Source notes', 'Reported IR gap (pp)', 'Momentum sentiment', 'Social sentiment',
  'Strength category (agreed rule)', 'Reported Strength score', 'Reported overall', 'Reported Strength score agrees',
  'Own growth used', 'Financial period type', 'Financial period label', 'Social comparison type', 'Baseline window label', 'Comparison window label',
  'Measurement subject', 'Reported Strength change (pp)', 'Strength source handling', 'Revenue-derived Strength change (pp)',
  'Source financial-only total (separate method)', 'Source financial-only sentiment', 'Social sample/window limits', 'Source capture label (timezone if known)', 'Source overall sentiment', 'Financial benchmark status',
  ...Array.from({ length: peerSlots }, (_, index) => `Peer ${index + 1} growth (key lookup)`) ], cycleValues, 'SeasonalCycles');
for (let row = 7; row <= cycleEnd; row++) {
  const c = cycleRows[row - 7];
  if (c.company === 'TOM FORD') {
    cycles.getRange(`AH${row}:AN${row}`).format.wrapText = true;
    cycles.getRange(`A${row}:AU${row}`).format.rowHeight = 60;
  }
  if (newReportCompanies.has(c.company)) {
    cycles.getRange(`AH${row}:AN${row}`).format.wrapText = true;
    cycles.getRange(`A${row}:BK${row}`).format.rowHeight = 80;
  }
  if (['Fendi', 'Belmont Park Village', 'Christian Louboutin'].includes(c.company)) cycles.getRange(`V${row}`).format.wrapText = true;
  const peerNames = peerNamesByCycle.get(c.cycleKey);
  const f = {};
  if (c.brandRevenueCurrentProxyKey) {
    const proxy = `'Revenue proxies'!H${proxyRowByKey.get(c.brandRevenueCurrentProxyKey)}`;
    f.AE = `=IF(ISNUMBER(${proxy}),${proxy},"")`;
  }
  if (peerNames) {
    peerNames.forEach((name, index) => {
      const key = `$A${row}&" | ${name.replaceAll('"', '""')}"`;
      const keys = `'Peers'!$O$7:$O$${peerEnd}`;
      const values = `'Peers'!$I$7:$I$${peerEnd}`;
      const available = `'Peers'!$P$7:$P$${peerEnd}`;
      f[col(64 + index)] = `=IF(AND(COUNTIF(${keys},${key})=1,COUNTIFS(${keys},${key},${available},1)=1),SUMIF(${keys},${key},${values}),"")`;
    });
    const range = `BL${row}:${col(63 + peerNames.length)}${row}`;
    f.H = `=IF(BK${row}="Incomplete","",IF(COUNT(${range})=${peerNames.length},MEDIAN(${range}),""))`;
    f.AC = `=IF(AND(ISNUMBER(AV${row}),ISNUMBER(H${row})),1+COUNTIF(${range},">"&AV${row}),"")`;
    f.AD = `=IF(ISNUMBER(H${row}),COUNT(${range})+1,"")`;
  }
  f.AV = c.brandRevenueCurrentProxyKey
    ? `=IF(COUNT(AE${row}:AF${row})=2,IF(AF${row}>0,AE${row}/AF${row}-1,""),"")`
    : `=IF(COUNT(AE${row}:AF${row})=2,IF(AF${row}>0,AE${row}/AF${row}-1,""),IF(ISNUMBER(G${row}),G${row},""))`;
  f.I = `=IF(AND(ISNUMBER(AV${row}),ISNUMBER(H${row})),(AV${row}-H${row})*100,"")`;
  f.K = `=IF(ISNUMBER(I${row}),MIN('Method'!$B$12,MAX('Method'!$B$11,'Method'!$B$8+'Method'!$B$9*I${row})),"")`;
  f.L = `=IF(BK${row}="Incomplete","",IF(ISNUMBER(J${row}),J${row},IF(ISNUMBER(K${row}),K${row},"")))`;
  if (c.brandRevenueCurrentProxyKey) f.L = `=IF(AND(BK${row}<>"Incomplete",ISNUMBER(AV${row}),ISNUMBER(H${row})),IF(ISNUMBER(J${row}),J${row},K${row}),"")`;
  if (c.socialAggregation === 'median-eligible-campaign-lifts') {
    const rows = campaignRanges.get(c.cycleKey);
    const refs = rows.map(r => `'Campaigns'!O${r}`).join(',');
    f.O = `=IF(COUNT(${refs})>0,MEDIAN(${refs}),"")`;
  } else if (['median-selected-brand-fiscal-lifts', 'median-selected-brand-matched-comment-lifts', 'median-selected-banner-retail-year-lifts'].includes(c.socialAggregation)) {
    const rows = portfolioRanges.get(c.cycleKey);
    const lifts = rows.map(r => `'Brand social'!R${r}`).join(',');
    const included = `COUNTIF('Brand social'!Q${rows[0]}:Q${rows.at(-1)},"Yes")`;
    f.O = `=IF(AND(${included}>0,COUNT(${lifts})=${included}),MEDIAN(${lifts}),"")`;
  } else {
    const annualEligibility = c.socialMinimumValidPosts == null ? '' : `,AJ${row}>=${c.socialMinimumValidPosts},AK${row}>=${c.socialMinimumValidPosts},${c.socialIncludedCalendarMonths.length}>=${c.socialMinimumCommonMonths}`;
    f.O = `=IF(AND(COUNT(M${row}:N${row})=2,M${row}>0${annualEligibility}),N${row}/M${row}-1,"")`;
  }
  f.Q = `=IF(ISNUMBER(O${row}),MIN('Method'!$B$12,MAX('Method'!$B$11,'Method'!$B$10+O${row}*100)),"")`;
  f.R = c.socialMinimumValidPosts == null
    ? `=IF(ISNUMBER(P${row}),P${row},IF(ISNUMBER(Q${row}),Q${row},""))`
    : `=IF(AND(AJ${row}>=${c.socialMinimumValidPosts},AK${row}>=${c.socialMinimumValidPosts},${c.socialIncludedCalendarMonths.length}>=${c.socialMinimumCommonMonths}),IF(ISNUMBER(P${row}),P${row},IF(ISNUMBER(Q${row}),Q${row},"")),"")`;
  f.T = `=IF(S${row}="","",IF(ISNUMBER(INDEX($AO$7:$AO$${cycleEnd},MATCH(S${row},$A$7:$A$${cycleEnd},0))),INDEX($AO$7:$AO$${cycleEnd},MATCH(S${row},$A$7:$A$${cycleEnd},0)),IF(ISNUMBER(INDEX($I$7:$I$${cycleEnd},MATCH(S${row},$A$7:$A$${cycleEnd},0))),INDEX($I$7:$I$${cycleEnd},MATCH(S${row},$A$7:$A$${cycleEnd},0)),"")))`;
  f.U = `=IF(BK${row}="Incomplete","",IF(ISNUMBER(T${row}),IF(ISNUMBER(AO${row}),AO${row}-T${row},IF(ISNUMBER(I${row}),I${row}-T${row},"")),""))`;
  if (c.brandRevenueCurrentProxyKey) f.U = `=IF(AND(ISNUMBER(AV${row}),ISNUMBER(H${row})),${f.U.slice(1)},"")`;
  const derivedPriorGap = `INDEX($I$7:$I$${cycleEnd},MATCH(S${row},$A$7:$A$${cycleEnd},0))`;
  f.BE = `=IF(S${row}="","",IF(AND(ISNUMBER(I${row}),ISNUMBER(${derivedPriorGap})),I${row}-${derivedPriorGap},""))`;
  f.X = `=IF(AR${row}="","",VLOOKUP(AR${row},'Method'!$D$5:$E$8,2,FALSE))`;
  f.Y = `=IF(AND(ISNUMBER(L${row}),ISNUMBER(R${row}),ISNUMBER(X${row})),L${row}*'Method'!$B$5+R${row}*'Method'!$B$6+X${row}*'Method'!$B$7,"")`;
  f.Z = `=IF(ISNUMBER(Y${row}),ROUND(Y${row},'Method'!$B$13),"")`;
  f.AA = `=${sentimentFormula(`Z${row}`)}`;
  f.AB = `=IF(ISNUMBER(Z${row}),IF(AND(ISNUMBER(AS${row}),AS${row}<>X${row}),"Provisional · agreed Strength override","Provisional · source review"),"Missing component inputs")`;
  f.AP = `=${momentumLabel(`L${row}`)}`;
  f.AQ = `=${socialLabel(`R${row}`)}`;
  f.AR = `=${strengthLabel(`U${row}`, `IF(ISNUMBER(AO${row}),AO${row},I${row})`)}`;
  f.AU = `=IF(AND(ISNUMBER(X${row}),ISNUMBER(AS${row})),X${row}=AS${row},"")`;
  f.BD = `=IF(AR${row}="","Missing Strength inputs",IF(AND(ISNUMBER(AS${row}),AS${row}<>X${row}),"Agreed rule supersedes source","Agreed rule; source retained"))`;
  for (const [column, formula] of Object.entries(f)) cycles.getRange(`${column}${row}`).formulas = [[formula]];
}
cycles.getRange(`D7:F${cycleEnd}`).setNumberFormat('dd mmm yyyy');
cycles.getRange(`AI7:AI${cycleEnd}`).setNumberFormat('dd mmm yyyy');
cycles.getRange(`G7:H${cycleEnd}`).setNumberFormat('0.00%');
cycles.getRange(`O7:O${cycleEnd}`).setNumberFormat('+0.0%;-0.0%;0.0%');
for (const c of ['I', 'T', 'U', 'AO']) cycles.getRange(`${c}7:${c}${cycleEnd}`).setNumberFormat('+0.00;-0.00;0.00');
for (const c of ['J', 'K', 'L', 'P', 'Q', 'R', 'X', 'Z']) cycles.getRange(`${c}7:${c}${cycleEnd}`).setNumberFormat('0.0');
cycles.getRange(`Y7:Y${cycleEnd}`).setNumberFormat('0.000');
cycles.getRange(`AE7:AF${cycleEnd}`).setNumberFormat('#,##0.000');
for (const c of ['M', 'N', 'AJ', 'AK']) cycles.getRange(`${c}7:${c}${cycleEnd}`).setNumberFormat('#,##0');
for (const range of [`C7:G${cycleEnd}`, `J7:J${cycleEnd}`, `M7:N${cycleEnd}`, `P7:P${cycleEnd}`, `S7:S${cycleEnd}`, `V7:W${cycleEnd}`, `AE7:AO${cycleEnd}`]) cycles.getRange(range).format.fill = amber;
for (const range of [`H7:I${cycleEnd}`, `K7:L${cycleEnd}`, `O7:O${cycleEnd}`, `Q7:R${cycleEnd}`, `T7:U${cycleEnd}`, `X7:AD${cycleEnd}`]) cycles.getRange(range).format.fill = green;
cycles.getRange(`AP7:AU${cycleEnd}`).format.fill = green;
cycles.getRange(`AS7:AT${cycleEnd}`).format.fill = amber;
cycles.getRange(`AP1:AU${cycleEnd}`).format.columnWidth = 32;
cycles.getRange(`AS7:AT${cycleEnd}`).setNumberFormat('0.0');
cycles.getRange(`AV7:AV${cycleEnd}`).setNumberFormat('0.00%');
cycles.getRange(`BC7:BC${cycleEnd}`).setNumberFormat('+0.00;-0.00;0.00');
cycles.getRange(`AV7:AV${cycleEnd}`).format.fill = green;
cycles.getRange(`BD7:BD${cycleEnd}`).format.fill = green;
cycles.getRange(`BE7:BE${cycleEnd}`).format.fill = green;
cycles.getRange(`BE7:BE${cycleEnd}`).setNumberFormat('+0.000;-0.000;0.000');
cycles.getRange(`AW7:BC${cycleEnd}`).format.fill = amber;
cycles.getRange(`AV1:BD${cycleEnd}`).format.columnWidth = 32;
cycles.getRange(`AW7:BD${cycleEnd}`).format.wrapText = true;
cycles.getRange(`BE1:BE${cycleEnd}`).format.columnWidth = 32;
cycles.getRange(`BF7:BJ${cycleEnd}`).format.fill = amber;
cycles.getRange(`BF7:BF${cycleEnd}`).setNumberFormat('0.0');
cycles.getRange(`BF1:BG${cycleEnd}`).format.columnWidth = 32;
cycles.getRange(`BH1:BH${cycleEnd}`).format.columnWidth = 100;
cycles.getRange(`BI1:BJ${cycleEnd}`).format.columnWidth = 40;
cycles.getRange(`BH7:BJ${cycleEnd}`).format.wrapText = true;
cycles.getRange(`BK7:BK${cycleEnd}`).format.fill = amber;
cycles.getRange(`BK1:BK${cycleEnd}`).format.columnWidth = 32;
cycles.getRange(`BK7:BK${cycleEnd}`).dataValidation = { rule: { type: 'list', values: ['Incomplete', 'Complete'] } };
cycles.getRange(`A1:C${cycleEnd}`).format.columnWidth = 27;
cycles.getRange(`S1:S${cycleEnd}`).format.columnWidth = 30;
cycles.getRange(`W1:W${cycleEnd}`).format.columnWidth = 25;
cycles.getRange(`AB1:AB${cycleEnd}`).format.columnWidth = 31;
cycles.getRange(`AH1:AN${cycleEnd}`).format.columnWidth = 46;
cycles.getRange(`AN1:AN${cycleEnd}`).format.columnWidth = 100;
cycles.getRange(`BL7:${peerGrowthLastColumn}${cycleEnd}`).format.fill = green;
cycles.getRange(`BL7:${peerGrowthLastColumn}${cycleEnd}`).setNumberFormat('0.00%');
cycles.getRange(`BL1:${peerGrowthLastColumn}${cycleEnd}`).format.columnWidth = 27;
cycles.getRange(`J1:J${cycleEnd}`).format.columnWidth = 23;
cycles.getRange('J7').setNumberFormat('0.00');
cycles.getRange('J9:L9').setNumberFormat('0.00');
for (let row = 7; row <= cycleEnd; row++) {
  const c = cycleRows[row - 7];
  if (Number.isFinite(c.baselineMedianLikes) && !Number.isInteger(c.baselineMedianLikes)) cycles.getRange(`M${row}`).setNumberFormat('#,##0.0');
  if (Number.isFinite(c.showMedianLikes) && !Number.isInteger(c.showMedianLikes)) cycles.getRange(`N${row}`).setNumberFormat('#,##0.0');
  if (Number.isFinite(c.reportedSocialSubscore) && Math.round(c.reportedSocialSubscore * 10) !== c.reportedSocialSubscore * 10) {
    cycles.getRange(`P${row}`).setNumberFormat('0.00');
    cycles.getRange(`R${row}`).setNumberFormat('0.00');
  }
}
cycles.getRange(`W7:W${cycleEnd}`).dataValidation = { rule: { type: 'list', values: ['Strong', 'Up and coming', 'Neutral', 'Fallback'] } };
cycles.getRange(`V7:V${cycleEnd}`).dataValidation = { rule: { type: 'list', values: ['Same-season', 'Cross-season', 'Annual comparison'] } };
cycles.getRange(`Z7:Z${cycleEnd}`).conditionalFormats.addCustom(`=AND(ISNUMBER(Z7),Z7>=70)`, { fill: '#DCEBDD' });

// Retain the previous routing, period, CTA and evidence fields for implementation.
{
const delivery = details;
init(delivery, 'Fashion Momentum supporting details', 'AJ', contentEnd);
delivery.tabColor = navy;
delivery.getRange('A4').values = [[`${data.records.length} rows: 25 Allen /26 mappings +43 CSV +6 report additions (Tommy/VF/G-III/LVMH/LV/Missoni). Group data never replaces brand identity; Enablement retains 70 pairings.`]];
const deliveryValues = data.records.map(r => [r.prospectId, r.prospectName, r.lightEnvironments.join(' / '), r.audienceType, r.domain,
  cycleKeyByProspect.get(r.prospectId), null, null, null, null, null, null, null, r.page1.coreInsight,
  null, null, null, null, null, null, null, null,
  publishedData.records.find(record => record.prospectName === r.prospectName).page3.leaderboardId, null,
  publishedData.records.find(record => record.prospectName === r.prospectName).page3.state,
  r.page4.invitation, r.page4.ctaLabel, r.page4.ctaDestination, r.page4.confirmationCopy,
  r.evidence.reviewStatus, r.evidence.gaps.join('; '), null, null,
  r.enablementCompanies.map(m => m.company).join(' / '), r.deliveryScope,
  r.enablementCompanies.map(m => m.csvSourceRow).join(' / ')]);
const deliveryEnd = table(delivery, 6, ['Prospect ID', 'Prospect', 'Light environment(s)', 'Type', 'Domain from Allen',
  'Selected cycle key', 'Collection / campaign', 'Show date', 'Financial period proxy', 'Overall / 100', 'Overall sentiment', 'Data state', 'Sentiment label', 'Core insight',
  'Momentum score (50%)', 'Social score (30%)', 'Strength score (20%)', 'IR gap (pp)', 'Social lift', 'Trend change (pp)', 'IR peer rank', 'IR peer count',
  'Board ID', 'Overall rank', 'Board state', 'Invitation', 'CTA label', 'CTA destination', 'Confirmation copy', 'Evidence review', 'Data gaps',
  'Email domain(s)', 'Company code(s)', 'CSV source company(s)', 'Delivery scope', 'CSV source row(s)'], deliveryValues, 'ProspectDetails');
const groups = [['A5:E5', 'Identity'], ['F5:N5', 'Page 1: Overall score'], ['O5:V5', 'Page 2: Components'], ['W5:Y5', 'Page 3: Leaderboard'], ['Z5:AC5', 'Page 4: CTA'], ['AD5:AE5', 'Evidence'], ['AF5:AJ5', 'CSV enablement']];
for (const [range, label] of groups) {
  delivery.getRange(range).format.fill = '#DDE8E0';
  delivery.getRange(range.split(':')[0]).values = [[label]];
  delivery.getRange(range).format.font = { name: font, bold: true, color: navy };
}
for (let row = 7; row <= deliveryEnd; row++) {
  const record = data.records[row - 7];
  const lookup = column => `INDEX('Cycles'!$${column}$7:$${column}$${cycleEnd},MATCH(F${row},'Cycles'!$A$7:$A$${cycleEnd},0))`;
  const numeric = column => `=IF(ISNUMBER(${lookup(column)}),${lookup(column)},"")`;
  const text = column => `=IF(${lookup(column)}="","",${lookup(column)})`;
  const formulas = { G: text('C'), H: numeric('D'), J: numeric('Z'), K: text('AA'), O: numeric('L'), P: numeric('R'), Q: numeric('X'), R: numeric('I'), S: numeric('O'), T: numeric('U'), U: numeric('AC'), V: numeric('AD') };
  const periodType = lookup('AW');
  const periodLabel = lookup('AX');
  formulas.I = `=IF(${periodType}="Fiscal year",${periodLabel},IF(AND(ISNUMBER(${lookup('E')}),ISNUMBER(${lookup('F')})),TEXT(${lookup('E')},"mmm yyyy")&" to "&TEXT(${lookup('F')},"mmm yyyy"),IF(${periodLabel}="","",${periodLabel})))`;
  formulas.M = `=IF(K${row}="","",K${row}&" overall score")`;
  formulas.L = data.cycles.find(c => c.cycleKey === record.selectedCycleKey)?.scoreProfile
    ? `="${record.page1.status.replaceAll('"', '""')}"`
    : record.audienceType === null ? record.selectedCycleKey
    ? `=IF(ISNUMBER(J${row}),"Group score provisional · identity/environment pending","Identity/environment and remaining inputs pending")`
    : '="Scope/environment and scoring inputs pending"' : record.audienceType === 'Retailer' ? '="Shared brand board · no retailer score"' : text('AB');
  const csvValues = column => record.enablementCompanies.map(m => {
    const companyText = `"${m.company.replaceAll('"', '""')}"`;
    const value = `INDEX('Enablement'!$${column}$7:$${column}$${enablementEnd},MATCH(${companyText},'Enablement'!$A$7:$A$${enablementEnd},0))`;
    return `IF(${value}="","",${value})`;
  });
  formulas.AF = record.enablementCompanies.length ? `=_xlfn.TEXTJOIN("; ",TRUE,${csvValues('B').join(',')})` : '=""';
  formulas.AG = record.enablementCompanies.length ? `=_xlfn.TEXTJOIN("; ",TRUE,${csvValues('C').join(',')})` : '=""';
  for (const [column, formula] of Object.entries(formulas)) delivery.getRange(`${column}${row}`).formulas = [[formula]];
  if (newReportCompanies.has(record.prospectName)) {
    delivery.getRange(`I${row}:N${row}`).format.wrapText = true;
    delivery.getRange(`A${row}:AJ${row}`).format.rowHeight = 42;
  }
  if (['PacSun', 'Calvin Klein', 'Tommy Hilfiger', 'G-III Apparel Group', 'ME+EM', 'David Yurman', 'NORDSTROM', 'Fendi', 'Belmont Park Village', 'Christian Louboutin', 'New Balance', 'Marc Jacobs', 'DKNY', 'J.Crew', 'Jacquemus', 'Lafayette 148', 'Exemplar Luxury Group'].includes(record.prospectName)) delivery.getRange(`F${row}:G${row}`).format.wrapText = true;
}
delivery.getRange(`H7:H${deliveryEnd}`).setNumberFormat('dd mmm yyyy');
for (const c of ['J', 'O', 'P', 'Q']) delivery.getRange(`${c}7:${c}${deliveryEnd}`).setNumberFormat('0.0');
for (const c of ['R', 'T']) delivery.getRange(`${c}7:${c}${deliveryEnd}`).setNumberFormat('+0.00;-0.00;0.00');
delivery.getRange(`S7:S${deliveryEnd}`).setNumberFormat('+0.0%;-0.0%;0.0%');
for (const range of [`G7:M${deliveryEnd}`, `O7:V${deliveryEnd}`]) delivery.getRange(range).format.fill = green;
for (const range of [`E7:F${deliveryEnd}`, `N7:N${deliveryEnd}`, `Z7:AC${deliveryEnd}`, `AD7:AE${deliveryEnd}`]) delivery.getRange(range).format.fill = amber;
delivery.getRange(`A1:A${deliveryEnd}`).format.columnWidth = 18;
delivery.getRange(`B1:C${deliveryEnd}`).format.columnWidth = 29;
delivery.getRange(`D1:E${deliveryEnd}`).format.columnWidth = 19;
delivery.getRange(`F1:G${deliveryEnd}`).format.columnWidth = 27;
delivery.getRange(`I1:I${deliveryEnd}`).format.columnWidth = 30;
delivery.getRange(`L1:L${deliveryEnd}`).format.columnWidth = 39;
delivery.getRange(`N1:N${deliveryEnd}`).format.columnWidth = 96;
delivery.getRange(`W1:W${deliveryEnd}`).format.columnWidth = 35;
delivery.getRange(`Y1:Y${deliveryEnd}`).format.columnWidth = 56;
delivery.getRange(`Z1:Z${deliveryEnd}`).format.columnWidth = 90;
delivery.getRange(`AA1:AA${deliveryEnd}`).format.columnWidth = 29;
delivery.getRange(`AD1:AD${deliveryEnd}`).format.columnWidth = 44;
delivery.getRange(`AE1:AE${deliveryEnd}`).format.columnWidth = 100;
delivery.getRange(`AF1:AF${deliveryEnd}`).format.columnWidth = 68;
delivery.getRange(`AG1:AG${deliveryEnd}`).format.columnWidth = 42;
delivery.getRange(`AH1:AH${deliveryEnd}`).format.columnWidth = 45;
delivery.getRange(`AI1:AI${deliveryEnd}`).format.columnWidth = 50;
delivery.getRange(`AJ1:AJ${deliveryEnd}`).format.columnWidth = 22;
delivery.getRange(`AF7:AG${deliveryEnd}`).format.fill = green;
delivery.getRange(`J7:J${deliveryEnd}`).conditionalFormats.addCustom('=AND(ISNUMBER(J7),J7>=70)', { fill: '#DCEBDD' });
}

// Include Momentum sentiment now that all three component-specific labels are requested.
const supplement = publishedData.salesSocialSupplement;
const supplementColumns = supplement?.columns || [
  { field: 'smFeb2024', label: 'SM Feb ’24', type: 'percent' },
  { field: 'q4VsBaseline2024', label: 'Q4 vs Baseline ’24 (%)', type: 'percent' },
  { field: 'smFeb2025', label: 'SM Feb ’25', type: 'percent' },
  { field: 'q4VsBaseline2025', label: 'Q4 vs Baseline ’25 (%)', type: 'percent' },
  { field: 'smFeb2026', label: 'SM Feb ’26', type: 'percent' },
  { field: 'q4VsBaseline2026', label: 'Q4 vs Baseline ’26 (%)', type: 'percent' },
  { field: 'insightsDescriptive', label: 'Insights Descriptive', type: 'text' },
  { field: 'insightsStatistics', label: 'Insights Statistics', type: 'text' },
];
const yoyV2 = publishedData.salesYoyV2Supplement;
const yoyColumns = yoyV2?.columns || [
  { field: 'q4VsBaseline2024YoyV2', label: 'Q4 vs Baseline ’24 (%) YoY v2', type: 'percent' },
  { field: 'q4VsBaseline2025YoyV2', label: 'Q4 vs Baseline ’25 (%) YoY v2', type: 'percent' },
  { field: 'q4VsBaseline2026YoyV2', label: 'Q4 vs Baseline ’26 (%) YoY v2', type: 'percent' },
];
init(delivery, 'Fashion Momentum delivery table', 'AL', contentEnd);
delivery.tabColor = navy;
delivery.getRange('A4').values = [[`${data.records.length} rows: 30 scoped provisional results (24 own-unit/WWD proxies +6 parent hybrids),44 without a total. Six partials, two coverage-only reports; alternative source scores separate.`]];
const deliveryEnd = table(delivery, 6, ['Prospect', 'One core insight', 'Fashion Momentum Index', 'Overall sentiment',
  'Trend / Peer Trajectory score', 'Trend / Peer Trajectory category', 'Social / Show Attention score', 'Social / Show Attention category', 'Revenue / Commercial Pace score', 'Revenue / Commercial Pace category', 'Email domain(s)', 'Company code(s)',
  'Trend / Peer Trajectory descriptor', 'Trend / Peer Trajectory insight', 'Social / Show Attention descriptor', 'Social / Show Attention insight', 'Revenue / Commercial Pace descriptor', 'Revenue / Commercial Pace insight', 'Fashion Momentum Index (normalized 70–98)',
  'Trend / Peer Trajectory KPI', 'Trend / Peer Trajectory KPI label', 'Social / Show Attention KPI', 'Social / Show Attention KPI label', 'Revenue / Commercial Pace KPI', 'Revenue / Commercial Pace KPI label', 'Category', 'Leaderboard rank', ...supplementColumns.map(c => c.label), ...yoyColumns.map(c => c.label)],
  data.deliveryRows.map((r, index) => [r.prospect, null, null, null, null, null, null, null, null, null, null, null,
    r.momentumDescriptor, r.momentumInsight, r.socialDescriptor, r.socialInsight, r.strengthDescriptor, r.strengthInsight, null,
    r.momentumKpiValue, r.momentumKpiLabel, r.socialKpiValue, r.socialKpiLabel, r.strengthKpiValue, r.strengthKpiLabel, publishedData.deliveryRows[index].leaderboardCategory, null, ...supplementColumns.map(() => null), ...yoyColumns.map(() => null)]), 'CompactDelivery');
delivery.getRange('A5:R5').merge();
delivery.getRange('A5').values = [['Commercial insight = own sales performance. Its score/category retain peer-relative strength. Descriptors describe the narrative; categories describe the scores.']];
delivery.getRange('A5:R5').format = { fill: '#DDE8E0', font: { name: font, size: 10, color: navy }, wrapText: true, rowHeight: 30 };
delivery.getRange('A6:R6').format.rowHeight = 80;
for (let row = 7; row <= deliveryEnd; row++) {
  const lookup = column => `INDEX('Details'!$${column}$7:$${column}$${contentEnd},MATCH(A${row},'Details'!$B$7:$B$${contentEnd},0))`;
  const numeric = (column, roundDisplay = false) => `=IF(ISNUMBER(${lookup(column)}),${roundDisplay ? `ROUND(${lookup(column)},1)` : lookup(column)},"")`;
  const strengthLookup = `INDEX('Cycles'!$AR$7:$AR$${cycleEnd},MATCH(${lookup('F')},'Cycles'!$A$7:$A$${cycleEnd},0))`;
  const formulas = {
    B: `=IF(${lookup('N')}="","",${lookup('N')})`, C: numeric('J'), D: `=${sentimentFormula(`C${row}`)}`,
    E: numeric('O', true), F: `=${momentumLabel(lookup('O'))}`,
    G: numeric('P', true), H: `=${socialLabel(lookup('P'))}`,
    I: numeric('Q', true), J: `=IF(${strengthLookup}="","",${strengthLookup})`,
    K: `=IF(${lookup('AF')}="","",${lookup('AF')})`, L: `=IF(${lookup('AG')}="","",${lookup('AG')})`,
    S: `=IF(ISNUMBER(C${row}),IF('Method'!$B$145='Method'!$B$146,ROUND(('Method'!$B$143+'Method'!$B$144)/2,'Method'!$B$147),ROUND('Method'!$B$143+(C${row}-'Method'!$B$145)*('Method'!$B$144-'Method'!$B$143)/('Method'!$B$146-'Method'!$B$145),'Method'!$B$147)),"")`,
  };
  for (const [column, formula] of Object.entries(formulas)) delivery.getRange(`${column}${row}`).formulas = [[formula]];
}
delivery.freezePanes.freezeColumns(1);
delivery.getRange(`A1:A${deliveryEnd}`).format.columnWidth = 29;
delivery.getRange(`B1:B${deliveryEnd}`).format.columnWidth = 70;
delivery.getRange(`C1:J${deliveryEnd}`).format.columnWidth = 21;
delivery.getRange(`B7:B${deliveryEnd}`).format.wrapText = true;
delivery.getRange(`K1:K${deliveryEnd}`).format.columnWidth = 68;
delivery.getRange(`L1:L${deliveryEnd}`).format.columnWidth = 42;
for (const column of ['M', 'O', 'Q']) delivery.getRange(`${column}1:${column}${deliveryEnd}`).format.columnWidth = 28;
delivery.getRange(`Q1:Q${deliveryEnd}`).format.columnWidth = 36;
for (const column of ['N', 'P', 'R']) delivery.getRange(`${column}1:${column}${deliveryEnd}`).format.columnWidth = 68;
delivery.getRange(`M7:R${deliveryEnd}`).format.wrapText = true;
delivery.getRange(`M7:R${deliveryEnd}`).format.fill = amber;
delivery.getRange(`S1:S${deliveryEnd}`).format.columnWidth = 32;
delivery.getRange(`S7:S${deliveryEnd}`).format.fill = green;
delivery.getRange(`S7:S${deliveryEnd}`).setNumberFormat('0.0');
for (const column of ['T', 'V', 'X']) {
  delivery.getRange(`${column}1:${column}${deliveryEnd}`).format.columnWidth = 25;
  delivery.getRange(`${column}7:${column}${deliveryEnd}`).format.horizontalAlignment = 'right';
}
for (const column of ['U', 'W', 'Y']) delivery.getRange(`${column}1:${column}${deliveryEnd}`).format.columnWidth = 38;
delivery.getRange(`T7:Y${deliveryEnd}`).format.wrapText = true;
delivery.getRange(`T7:Y${deliveryEnd}`).format.fill = amber;
delivery.getRange('T6:AA6').format.rowHeight = 80;
delivery.getRange(`Z1:Z${deliveryEnd}`).format.columnWidth = 26;
delivery.getRange(`AA1:AA${deliveryEnd}`).format.columnWidth = 22;
delivery.getRange(`Z7:Z${deliveryEnd}`).format.fill = amber;
delivery.getRange(`AA7:AA${deliveryEnd}`).format.fill = green;
delivery.getRange(`Z7:AA${deliveryEnd}`).format.horizontalAlignment = 'center';
delivery.getRange(`AA7:AA${deliveryEnd}`).setNumberFormat('0');
data.records.forEach((record, index) => {
  const row = index + 7;
  for (const [key, column] of [['momentum', 'T'], ['social', 'V'], ['strength', 'X']]) {
    const kpi = record.page2[key].cardKpi;
    if (!kpi) continue;
    const decimals = kpi.decimals ? `.${'0'.repeat(kpi.decimals)}` : '';
    const prefix = kpi.comparisonOperator ? `"${kpi.comparisonOperator}"` : '';
    const format = kpi.unit === 'count' ? '#,##0' : kpi.unit === 'pp'
      ? `${prefix}+0${decimals}" pp";${prefix}-0${decimals}" pp";0${decimals}" pp"`
      : `${prefix}+0${decimals}%;${prefix}-0${decimals}%;0${decimals}%`;
    delivery.getRange(`${column}${row}`).setNumberFormat(format);
    const selectedKey = `INDEX('Details'!$F$7:$F$${contentEnd},MATCH(A${row},'Details'!$B$7:$B$${contentEnd},0))`;
    const sourceKey = kpi.sourceCycleKey === record.selectedCycleKey ? selectedKey : `"${kpi.sourceCycleKey}"`;
    const source = c => `INDEX('Cycles'!$${c}$7:$${c}$${cycleEnd},MATCH(${sourceKey},'Cycles'!$A$7:$A$${cycleEnd},0))`;
    let formula;
    if (kpi.basis === 'relative-momentum') formula = `=IF(ISNUMBER(${source('AO')}),${source('AO')},IF(ISNUMBER(${source('I')}),${source('I')},""))`;
    if (kpi.basis === 'social-lift') formula = `=IF(ISNUMBER(${source('O')}),${source('O')},"")`;
    if (kpi.basis === 'own-growth') formula = `=IF(ISNUMBER(${source('G')}),${source('G')},IF(ISNUMBER(${source('AV')}),${source('AV')},""))`;
    if (kpi.basis === 'own-growth-rate-change') {
      const sourceRow = commercialGrowthRows.get(record.prospectName);
      formula = `=IF(COUNT('Method'!B${sourceRow}:B${sourceRow + 1})=2,('Method'!B${sourceRow}-'Method'!B${sourceRow + 1})*100,"")`;
    }
    if (formula) {
      delivery.getRange(`${column}${row}`).formulas = [[formula]];
      delivery.getRange(`${column}${row}`).format.fill = green;
    }
  }
});
delivery.getRange('A7:J7').format.rowHeight = 42;
data.deliveryRows.forEach((r, i) => { if (r.coreInsight) delivery.getRange(`A${i + 7}:J${i + 7}`).format.rowHeight = 42; });
data.deliveryRows.forEach((r, i) => {
  if (r.prospect.length > 29) {
    delivery.getRange(`A${i + 7}`).format.wrapText = true;
    delivery.getRange(`A${i + 7}:L${i + 7}`).format.rowHeight = 42;
    details.getRange(`B${i + 7}`).format.wrapText = true;
    details.getRange(`A${i + 7}:AJ${i + 7}`).format.rowHeight = 42;
  }
});
data.deliveryRows.forEach((r, i) => {
  if (r.momentumInsight) delivery.getRange(`A${i + 7}:R${i + 7}`).format.rowHeight = 68;
});
for (const column of ['C', 'E', 'G', 'I']) delivery.getRange(`${column}7:${column}${deliveryEnd}`).setNumberFormat('0.0');
for (const column of ['D', 'F', 'H', 'J']) {
  delivery.getRange(`${column}7:${column}${deliveryEnd}`).conditionalFormats.addCustom(`=${column}7="Good"`, { fill: '#DCEBDD' });
  delivery.getRange(`${column}7:${column}${deliveryEnd}`).conditionalFormats.addCustom(`=${column}7="Neutral"`, { fill: '#FFF2CE' });
  delivery.getRange(`${column}7:${column}${deliveryEnd}`).conditionalFormats.addCustom(`=${column}7="Needs improvement"`, { fill: '#F8DEDE' });
  for (const label of ['High', 'Positive', 'Strong', 'Up and coming']) delivery.getRange(`${column}7:${column}${deliveryEnd}`).conditionalFormats.addCustom(`=${column}7="${label}"`, { fill: '#DCEBDD' });
  for (const label of ['Low', 'Negative', 'Fallback']) delivery.getRange(`${column}7:${column}${deliveryEnd}`).conditionalFormats.addCustom(`=${column}7="${label}"`, { fill: '#F8DEDE' });
}

// Exercise input-driven dependencies, missing components, a genuine zero and band boundaries.
const get = (sheet, address) => sheet.getRange(address).values[0][0];
const ultaContext = data.sourceContext.ultaCompanyOnly;
const ultaContextCycle = cycleRowByKey.get(ultaContext.selectedCycleKey);
const ultaContextPrior = cycleRowByKey.get(data.cycles.find(c => c.cycleKey === ultaContext.selectedCycleKey).priorCycleKey);
const nordContext = data.sourceContext.nordstromMixedPeriod;
const nordHistoricalCycle = cycleRowByKey.get(nordContext.financialCycleKey);
const nordCurrentCycle = cycleRowByKey.get(nordContext.socialCycleKey);
method.getRange('A119:B119').values = [['Nordstrom source proxy', 'Mixed years and assumed Strength; unused for standard Delivery']];
method.getRange('A119:B119').format = { fill: navy, font: { name: font, size: 10, bold: true, color: '#FFFFFF' }, wrapText: true, rowHeight: 42 };
method.getRange('A120:B132').values = [
  ['Source FY2024 Momentum', nordContext.reportedMomentumScore],
  ['Source FY2025 Social', nordContext.reportedSocialScore],
  ['Assumed Strength (unobserved)', nordContext.assumedStrengthScore],
  ['Weighted source components', null],
  ['Source reported overall', nordContext.reportedOverall],
  ['Source reported sentiment', nordContext.reportedOverallSentiment],
  ['Historical FY2024 Momentum', null],
  ['Current FY2025 Social', null],
  ['Observed FY2025 Strength', null],
  ['Standard FY2025 overall', null],
  ['Periods and financial scope', 'FY2024 consolidated merchandise sales including Rack; FY2025 Nordstrom nameplate social'],
  ['Source report', nordContext.sourceDocument],
  ['Reason unused', nordContext.reasonUnused],
];
const nordContextFormulas = {
  B123: '=IF(COUNT(B120:B122)=3,B120*$B$5+B121*$B$6+B122*$B$7,"")',
  B126: `=IF(ISNUMBER('Cycles'!L${nordHistoricalCycle}),'Cycles'!L${nordHistoricalCycle},"")`,
  B127: `=IF(ISNUMBER('Cycles'!R${nordCurrentCycle}),'Cycles'!R${nordCurrentCycle},"")`,
  B128: `=IF(ISNUMBER('Cycles'!X${nordCurrentCycle}),'Cycles'!X${nordCurrentCycle},"")`,
  B129: `=IF(ISNUMBER('Cycles'!Z${nordCurrentCycle}),'Cycles'!Z${nordCurrentCycle},"")`,
};
for (const [address, formula] of Object.entries(nordContextFormulas)) method.getRange(address).formulas = [[formula]];
method.getRange('A120:A132').format.wrapText = true;
method.getRange('A120:B132').format.rowHeight = 35;
method.getRange('B120:B129').format.horizontalAlignment = 'left';
method.getRange('B120:B124').setNumberFormat('0.0000');
method.getRange('B124').setNumberFormat('0.0');
method.getRange('B126:B129').setNumberFormat('0.0000');
method.getRange('B120:B122').format.fill = amber;
for (const address of Object.keys(nordContextFormulas)) method.getRange(address).format.fill = green;
method.getRange('B130:B132').format.wrapText = true;
method.getRange('A130:B132').format.rowHeight = 55;
method.getRange('A134:B140').values = [
  ['Component insight copy', `${Object.keys(data.selectedCycles).length} supplied company assessments; three descriptors and three factual sentences per company. Other prospect rows retain blank component copy.`],
  ['Trend / Peer Trajectory', 'Saved own growth versus the peer benchmark, corresponding to report section 3.'],
  ['Social / Show Attention', 'Saved likes/comment lift against the relevant baseline, corresponding to report section 2. This measures activity, not consumer opinion.'],
  ['Revenue / Commercial Pace copy', data.componentInsightPolicy.commercialCopyBasis],
  ['Commercial score and category', data.componentInsightPolicy.commercialScoreBasis],
  ['Missing/parent financials', 'RIMOWA standalone revenue unavailable; Bloomingdale’s copy uses own comparable sales, not Macy’s revenue. Nordstrom current financials remain unavailable; historical FY2024 sales are identified.'],
  ['Copy refresh', data.componentInsightPolicy.refresh],
];
method.getRange('A134:B140').format.wrapText = true;
method.getRange('A134:B140').format.rowHeight = 55;
method.getRange('A204:B210').values = [
  ['Highlighted component KPIs', 'Delivery T:Y adds one numeric value and label per component. Percent values use decimal fractions; growth gaps use pp; coverage counts stay unscored.'],
  ['Trend KPI', data.componentInsightPolicy.highlightKpi.trend],
  ['Social KPI', data.componentInsightPolicy.highlightKpi.social],
  ['Revenue KPI', data.componentInsightPolicy.highlightKpi.revenue],
  ['Period and comparison', 'Each insight names the year, quarter or show/campaign and its baseline. Show/campaign window = event day through day +7 versus the preceding 15 days.'],
  ['Separate available observations', 'Nordstrom uses historical FY2024 financial KPIs. Bloomingdale’s shows own comparable sales +7.4%. Exemplar shows historical Q2 FY2025 revenue change <−13%.'],
  ['Snapshot copy and index', 'KPI formulas follow saved source inputs; copy and labels need review if sources change. Component scores and both Fashion Momentum Index columns remain unchanged by these additions.'],
];
method.getRange('A204:B210').format.wrapText = true;
method.getRange('A204:B210').format.rowHeight = 55;
method.getRange('A142:B151').values = [
  ['Index display normalization', 'Separate 70–98 display scale. Original indices, insights and sentiments remain unchanged.'],
  ['Display minimum', data.overallDisplayNormalization.lowerBound],
  ['Display maximum', data.overallDisplayNormalization.upperBound],
  ['Current original minimum', null],
  ['Current original maximum', null],
  ['Display decimals', data.overallDisplayNormalization.decimals],
  ['Formula', 'Minimum + (original index − current original minimum) / (current original maximum − current original minimum) × (maximum − minimum)'],
  ['Population', 'All numeric selected overall indices in Delivery, including scoped parent hybrids. Context-only and incomplete totals excluded.'],
  ['Missing originals', 'Leave the normalized index blank. Original sentiments continue to describe original scores.'],
  ['Equal originals', 'If every available original index is identical, use the midpoint of the display bounds (84).'],
];
const originalIndexRange = `'Delivery'!$C$7:$C$${deliveryEnd}`;
method.getRange('B145').formulas = [[`=IF(COUNT(${originalIndexRange})>0,MIN(${originalIndexRange}),"")`]];
method.getRange('B146').formulas = [[`=IF(COUNT(${originalIndexRange})>0,MAX(${originalIndexRange}),"")`]];
method.getRange('A142:B151').format.wrapText = true;
method.getRange('A142:B151').format.rowHeight = 42;
method.getRange('B143:B144').format.fill = amber;
method.getRange('B147').format.fill = amber;
method.getRange('B145:B146').format.fill = green;
method.getRange('B143:B147').setNumberFormat('0.0');
const fendiAlternatives = data.sourceContext.fendiReportAlternatives;
const fendiPercentiles = fendiAlternatives.percentileComparison;
method.getRange('A153:B163').values = [
  ['Fendi annual parent proxy', `Selected FY2025 annual proxy: 47.3 / Neutral. Normalized 70–98 display: ${data.deliveryRows.find(r => r.prospect === 'Fendi').normalizedFashionMomentumIndex}. Fendi social and LVMH segment financials; standalone Fendi sales unavailable.`],
  ['Fendi parent financial scope', 'Momentum 50.4084 / Neutral: LVMH Fashion and Leather Goods versus Gucci/Hermès. Relative gap 2.1374 to 0.0817 pp gives Fallback 30, only 0.0557 pp beyond cutoff. Standalone/show totals unavailable.'],
  ['Fendi annual social', 'FY2024 median 8,315 / 604 posts to FY2025 8,616 / 336, +3.62%, Social 53.62 / Neutral. Both years cover all 12 months with numeric likes for included posts. Snapshot ages/archive completeness unverified.'],
  ['Fendi commercial copy', 'Own revenue unavailable. Parent Strength 30 remains in the score; commercial insight does not substitute LVMH sales for Fendi. Original Allen/LVMH environment, two code/domain pairings and invitation retained.'],
  ['Fendi show social (separate)', 'SS2026 show 24 Sep 2025, Europe/Rome. Baseline 9–23 Sep; event 24 Sep–1 Oct. Medians 7,860 / 21 posts to 12,370 / 17: +57.4%, Social 100 / Positive. #FendiSS26 selection excludes Palazzo opening; no show overall.'],
  ['Source percentile social scope', 'Five matched months: Jul/Aug/Sep/Oct/Dec 2024/2025. Medians 8,783 / 214 posts to 7,380 / 127: −15.97% / Negative. Different 11-observation cohort with mixed years. Full cohort records and SQL/posts not supplied.'],
  ['Source Momentum percentile', fendiPercentiles.reportedMomentumPercentile],
  ['Source Social percentile', fendiPercentiles.reportedSocialPercentile],
  ['Source Strength percentile', fendiPercentiles.reportedStrengthPercentile],
  ['Source percentile total (unused)', null],
  ['Fendi source and scale', `${fendiAlternatives.sourceDocument}. Source percentile 47.0 differs from original 47.3 and our min–max display ${data.deliveryRows.find(r => r.prospect === 'Fendi').normalizedFashionMomentumIndex}. The FY2025 annual total uses annual Fendi social; show and five-month social stay separate.`],
];
method.getRange('B162').formulas = [['=B159*$B$5+B160*$B$6+B161*$B$7']];
method.getRange('A153:B163').format.wrapText = true;
method.getRange('A153:B163').format.rowHeight = 60;
method.getRange('B159:B161').format.fill = amber;
method.getRange('B162').format.fill = green;
method.getRange('B159:B162').setNumberFormat('0.0');
const belmontContext = data.sourceContext.belmontOperatingCoverage;
const louboutinContext = data.sourceContext.louboutinCoverage;
const mentionContext = louboutinContext.retailerCaptionMentions;
method.getRange('A164:B164').values = [['Belmont and Louboutin coverage', 'Descriptive observations only; no numeric score or normalized index']];
method.getRange('A164:B164').format = { fill: navy, font: { name: font, size: 10, bold: true, color: '#FFFFFF' }, wrapText: true, rowHeight: 42 };
method.getRange('A165:B181').values = [
  ['Belmont account coverage', 'Two unique Instagram posts: 29 April /4 August 2026. Both lack numeric likes; comments median4 has no baseline. Archive/mirror share the same two posts.'],
  ['Belmont operating context', `Reported boutique openings and customer rewards, 11 April2025; does not establish sales growth. ${belmontContext.operatingObservation.sourceUrl}`],
  ['Belmont missing inputs', 'Matched social periods, village revenue/tenant sales, fiscal dates, footfall and occupancy history. Operator totals and mall averages are not substitutes.'],
  ['Louboutin account coverage', 'One TikTok post published20 October2026: 8,590 likes/38 comments. No baseline. No own Instagram match in the seven post/three profile tables checked by the source.'],
  ['Louboutin missing inputs', `Own-brand three-year revenue, fiscal calendar, aligned peers and matched social periods. Exor consolidated revenue and the EUR1bn ambition are not actual brand revenue. ${louboutinContext.financialTargetSourceUrl}`],
  ['Retailer caption sample', 'Third-party mentions in sampled retailer posts: 2024 versus2025; changing sample/retailer mix and small numerators. Not an own-account lift or score input.'],
  ['2024 caption mentions', mentionContext.baselineMentions],
  ['2024 sampled posts', mentionContext.baselineSampledPosts],
  ['2025 caption mentions', mentionContext.comparisonMentions],
  ['2025 sampled posts', mentionContext.comparisonSampledPosts],
  ['2024 sampled mention share', null],
  ['2025 sampled mention share', null],
  ['Sampled share change', null],
  ['Raw mention count change', null],
  ['Coverage evidence status', 'Source query date27 October2026; raw SQL, post IDs, retailer-caption records and accompanying calculations not supplied. Capture ages/timezones and independent source checks remain open.'],
  ['Belmont report', belmontContext.sourceDocument],
  ['Louboutin report', louboutinContext.sourceDocument],
];
method.getRange('B175:B178').formulas = [['=B171/B172'], ['=B173/B174'], ['=B176/B175-1'], ['=B173/B171-1']];
method.getRange('B171:B174').setNumberFormat('#,##0');
method.getRange('B175:B176').setNumberFormat('0.000%');
method.getRange('B177:B178').setNumberFormat('+0.00%;-0.00%;0.00%');
method.getRange('B171:B174').format.fill = amber;
method.getRange('B175:B178').format.fill = green;
method.getRange('B165:B181').format.wrapText = true;
method.getRange('A165:B170').format.rowHeight = 65;
method.getRange('A179:B179').format.rowHeight = 65;
method.getRange('A171:B178').format.rowHeight = 30;
const newBalanceContext = data.sourceContext.newBalanceReportAlternatives;
const exemplarContext = data.sourceContext.exemplarHistoricalPartial;
const exemplarCycleRow = cycleRowByKey.get(data.selectedCycles['Exemplar Luxury Group']);
method.getRange('A183:B183').values = [['Additional reports and source scales', 'Original capped scores, source alternatives and partial observations remain separate']];
method.getRange('A183:B183').format = { fill: navy, font: { name: font, size: 10, bold: true, color: '#FFFFFF' }, wrapText: true, rowHeight: 42 };
method.getRange('A184:B202').values = [
  ['New Balance annual inputs', 'Published 2024 growth 20% (secondary) and 2025 growth 19% (official). Rounded $7.8bn/$9.2bn imply 17.95% and are unused. Nike May fiscal years differ from calendar peers.'],
  ['New Balance Strength', 'Reported gaps 14.5941 to 21.5376 pp improve 6.9435 pp and current gap is positive: agreed Strong 80, original 66.0 / Neutral. Source Up and coming 70 and original 64.0 retained separately.'],
  ['New Balance source percentile', 'Source percentile components 100/10/55 total 64.0 use a separate eleven-observation cohort with mixed years. Our original is 66.0; 70–98 display is separate. Full cohort unsupplied.'],
  ['Superseded Marc Jacobs segment proxy', 'Earlier 31.4 / Needs improvement: LVMH segment Momentum 50.4084 and Strength 30 plus own matched-month likes 4,658 to 2,360. Standalone brand overall and commercial pace unavailable.'],
  ['Superseded Marc Jacobs percentile', 'Earlier source percentile 41.0 uses components 60/30/10 and differs from original 31.4. Current original minimum20.0 maps revised Marc Jacobs to70; ME+EM ordinary normalization is94.3; its supplied displayed index remains86.2.'],
  ['DKNY financial scope', 'Original 42.3 / Neutral uses G-III consolidated Momentum 12.623478 and parent Strength 30. Standalone DKNY revenue unavailable. Preserve DKNY/G-III environment and separate group row.'],
  ['DKNY comment metric', 'Median comments 8/93 posts to 15/89 across Jul/Aug/Sep/Oct/Dec 2024/2025 gives +87.5%, Social 100. Sparse likes 7/93 and 14/89 are excluded. Window differs from G-III three-brand portfolio.'],
  ['Superseded J.Crew social', 'Original Social 0 / Negative: 2,232/133 posts to 867/285, −61.16%. All 418 selected posts numeric. Source percentile Social 10 is unused; own-brand financials missing.'],
  ['Superseded Jacquemus social', 'Original Social 0 / Negative: 108,294/19 of 23 posts to 39,968/37 of 38, −63.09%. Missing likes 4/1 excluded, never zero. Source percentile Social 10 unused; financials missing.'],
  ['Jacquemus Le Paysan', 'Separate show 29 Jun 2025: baseline 14–28 Jun, 163,276/3 posts; show 29 Jun–6 Jul, 77,416/9. Lift −52.59%, Social 0 / Negative. Small baseline; selection, SQL and capture unverified; no overall.'],
  ['Superseded Lafayette social', 'Earlier Jun–Sep 2026 versus 2025: 51/37 posts to 41/64, −19.61%, Social 30.4 / Negative. No 2024 baseline. Four common complete months; no financials or overall.'],
  ['Exemplar banner social', 'Saks numeric posts 53/53 to 269/269; Neiman 203/203 to 330/337. Equal-banner median lift −25.22%, Social 24.8 / Negative. Bergdorf excluded for one baseline post. Historical proxy; no 2026 recovery score.'],
  ['Exemplar historical partial', 'Source 9.3 uses company-only Q2 FY2025 sales and annual banner social with redistributed weights 62.5%/37.5%, missing Strength. Kept below as alternate context; standard annual overall remains blank.'],
  ['Historical company-only sales score', exemplarContext.companyOnlySalesScore],
  ['Historical banner Social', null],
  ['Alternate sales weight', exemplarContext.redistributedSalesWeight],
  ['Alternate social weight', exemplarContext.redistributedSocialWeight],
  ['Alternate partial total (unused)', null],
  ['Batch source history', `${data.sourceReportCount} active reports /${Object.keys(data.selectedCycles).length} assessments /${data.receivedSourceReportCount} received files. Belmont/Louboutin replacement hashes match prior content. Original files retained; all71 identities,26 mappings,70 CSV pairings preserved.`],
];
method.getRange('B198').formulas = [[`=IF(ISNUMBER('Cycles'!R${exemplarCycleRow}),'Cycles'!R${exemplarCycleRow},"")`]];
method.getRange('B201').formulas = [['=IF(COUNT(B197:B200)=4,B197*B199+B198*B200,"")']];
method.getRange('B197:B198').setNumberFormat('0.0000');
method.getRange('B199:B200').setNumberFormat('0.0%');
method.getRange('B201').setNumberFormat('0.0');
method.getRange('B197:B200').format.fill = amber;
method.getRange('B198').format.fill = green;
method.getRange('B201').format.fill = green;
method.getRange('B184:B202').format.wrapText = true;
method.getRange('A184:B196').format.rowHeight = 65;
method.getRange('A197:B201').format.rowHeight = 30;
method.getRange('A202:B202').format.rowHeight = 65;
method.getRange('A89:B89').values = [['Ulta company-only context', 'Supporting alternate method; unused for standard Delivery and rankings']];
method.getRange('A89:B89').format = { fill: navy, font: { name: font, size: 10, bold: true, color: '#FFFFFF' }, wrapText: true, rowHeight: 42 };
method.getRange('A90:B106').values = [
  ['Source absolute Momentum', ultaContext.reportedMomentumScore],
  ['Source Social', ultaContext.reportedSocialScore],
  ['Source own-growth Strength', ultaContext.reportedStrengthScore],
  ['Weighted source components', null],
  ['Source reported overall', ultaContext.reportedOverall],
  ['Source reported sentiment', ultaContext.reportedOverallSentiment],
  ['Derived absolute Momentum', null],
  ['Derived Social', null],
  ['Own growth change (pp)', null],
  ['Raw-input context total', null],
  ['Raw-input rounded total', null],
  ['Raw-input sentiment', null],
  ['Standard peer-relative total', null],
  ['Standard benchmark status', null],
  ['Source report', ultaContext.sourceDocument],
  ['Alternate method scope', ultaContext.method],
  ['Source precision note', ultaContext.precisionNotes],
];
const ultaContextFormulas = {
  B93: '=IF(COUNT(B90:B92)=3,B90*$B$5+B91*$B$6+B92*$B$7,"")',
  B96: `=IF(ISNUMBER('Cycles'!AV${ultaContextCycle}),MIN($B$12,MAX($B$11,$B$8+$B$9*'Cycles'!AV${ultaContextCycle}*100)),"")`,
  B97: `=IF(ISNUMBER('Cycles'!Q${ultaContextCycle}),'Cycles'!Q${ultaContextCycle},"")`,
  B98: `=IF(AND(ISNUMBER('Cycles'!AV${ultaContextCycle}),ISNUMBER('Cycles'!AV${ultaContextPrior})),('Cycles'!AV${ultaContextCycle}-'Cycles'!AV${ultaContextPrior})*100,"")`,
  B99: '=IF(AND(ISNUMBER(B96),ISNUMBER(B97),ISNUMBER(B92)),B96*$B$5+B97*$B$6+B92*$B$7,"")',
  B100: '=IF(ISNUMBER(B99),ROUND(B99,$B$13),"")',
  B101: `=${sentimentFormula('B100')}`,
  B102: `=IF(ISNUMBER('Cycles'!Z${ultaContextCycle}),'Cycles'!Z${ultaContextCycle},"")`,
  B103: `='Cycles'!BK${ultaContextCycle}`,
};
for (const [address, formula] of Object.entries(ultaContextFormulas)) method.getRange(address).formulas = [[formula]];
method.getRange('A90:A106').format.wrapText = true;
method.getRange('A90:B104').format.rowHeight = 35;
method.getRange('B90:B103').format.horizontalAlignment = 'left';
method.getRange('B90:B94').setNumberFormat('0.0000');
method.getRange('B96:B100').setNumberFormat('0.0000');
method.getRange('B94').setNumberFormat('0.0');
method.getRange('B100').setNumberFormat('0.0');
method.getRange('B90:B92').format.fill = amber;
for (const address of Object.keys(ultaContextFormulas)) method.getRange(address).format.fill = green;
method.getRange('B104:B106').format.wrapText = true;
method.getRange('A105:B106').format.rowHeight = 55;
workbook.recalculate();
// Reordering source peers must preserve the cycle cohort, including missing/zero growth.
const peerInputLeft = peers.getRange(`A7:H${peerEnd}`).values;
const peerInputRight = peers.getRange(`J7:N${peerEnd}`).values;
const cohortBeforeSort = cycles.getRange(`H7:H${cycleEnd}`).values;
const ranksBeforeSort = cycles.getRange(`AC7:AD${cycleEnd}`).values;
const deliveryBeforeSort = delivery.getRange(`C7:J${6 + data.deliveryRows.length}`).values;
peers.getRange(`A7:H${peerEnd}`).values = [...peerInputLeft].reverse();
peers.getRange(`J7:N${peerEnd}`).values = [...peerInputRight].reverse();
workbook.recalculate();
assert.deepEqual(cycles.getRange(`H7:H${cycleEnd}`).values, cohortBeforeSort, 'Sorting peers changed medians');
assert.deepEqual(cycles.getRange(`AC7:AD${cycleEnd}`).values, ranksBeforeSort, 'Sorting peers changed ranks/counts');
assert.deepEqual(delivery.getRange(`C7:J${6 + data.deliveryRows.length}`).values, deliveryBeforeSort, 'Sorting peers changed scores');
peers.getRange(`A7:H${peerEnd}`).values = peerInputLeft;
peers.getRange(`J7:N${peerEnd}`).values = peerInputRight;
workbook.recalculate();
// Duplicate/missing observation keys must leave a pending benchmark, never a partial median.
const duplicatePeerKeyFormula = peers.getRange('O8').formulas;
peers.getRange('O8').values = [[get(peers, 'O7')]];
workbook.recalculate();
assert.equal(get(cycles, 'H7'), '');
assert.equal(get(cycles, 'AC7'), '');
peers.getRange('O8').formulas = duplicatePeerKeyFormula;
const sourcePeerGrowth = peers.getRange('F7:H7').values;
peers.getRange('F7:H7').clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(cycles, 'H7'), '');
peers.getRange('F7').values = [[0]];
workbook.recalculate();
assert.equal(get(cycles, 'BL7'), 0, 'A real zero peer-growth observation was lost');
assert.ok(Number.isFinite(get(cycles, 'H7')));
peers.getRange('F7:H7').values = sourcePeerGrowth;
workbook.recalculate();
assert.deepEqual(cycles.getRange(`H7:H${cycleEnd}`).values, cohortBeforeSort);
assert.deepEqual(delivery.getRange(`C7:J${6 + data.deliveryRows.length}`).values, deliveryBeforeSort);
const originalStrengthScore = get(method, 'E6');
const originalOverallScore = get(delivery, 'C7');
method.getRange('E6').values = [[originalStrengthScore + 1]];
workbook.recalculate();
assert.equal(get(delivery, 'I7'), originalStrengthScore + 1, 'Strength does not use the method mapping');
assert.notEqual(get(delivery, 'C7'), originalOverallScore);
method.getRange('E6').values = [[originalStrengthScore]];
workbook.recalculate();
assert.equal(get(delivery, 'C7'), originalOverallScore);
for (let index = 0; index < data.deliveryRows.length; index++) {
  const r = data.deliveryRows[index];
  assert.deepEqual(delivery.getRange(`M${index + 7}:R${index + 7}`).values[0],
    [r.momentumDescriptor, r.momentumInsight, r.socialDescriptor, r.socialInsight, r.strengthDescriptor, r.strengthInsight]);
}
assert.equal(data.deliveryRows.filter(r => r.momentumInsight).length, Object.keys(data.selectedCycles).length);
const contentRowFor = company => data.deliveryRows.findIndex(r => r.prospect === company) + 7;
const giiiRow = contentRowFor('G-III Apparel Group');
const meemRow = contentRowFor('ME+EM');
const yurmanRow = contentRowFor('David Yurman');
const nordRow = contentRowFor('NORDSTROM');
const giiiCycle = cycleRowByKey.get(data.selectedCycles['G-III Apparel Group']);
const meemCycle = cycleRowByKey.get(data.selectedCycles['ME+EM']);
const yurmanSelectedCycleKey = data.selectedCycles['David Yurman'];
const yurmanCycle = cycleRowByKey.get('david-yurman-calendar-2025-proxy');
details.getRange(`F${yurmanRow}`).values = [['david-yurman-calendar-2025-proxy']];
workbook.recalculate();
assert.deepEqual(delivery.getRange(`C${giiiRow}:J${giiiRow}`).values[0], [33.3, 'Needs improvement', 12.6, 'Low', 70, 'Positive', 30, 'Fallback']);
assert.deepEqual(delivery.getRange(`C${meemRow}:J${meemRow}`).values[0], [86, 'Good', 100, 'High', 100, 'Positive', 30, 'Fallback']);
assert.deepEqual(delivery.getRange(`C${yurmanRow}:J${yurmanRow}`).values[0], ['', '', '', '', 65.2, 'Positive', '', '']);
assert.deepEqual(delivery.getRange(`C${nordRow}:J${nordRow}`).values[0], ['', '', '', '', 34.8, 'Negative', '', '']);
assert.equal(get(delivery, `C${contentRowFor('DKNY')}`), 42.3);
assert.equal(get(delivery, `K${giiiRow}`), '');
assert.equal(get(delivery, `L${giiiRow}`), '');
assert.equal(get(details, `C${giiiRow}`), '');
assert.equal(get(details, `D${giiiRow}`), null);
assert.equal(get(details, `Z${giiiRow}`), null);
assert.equal(get(cycles, `M${giiiCycle}`), null);
assert.equal(get(cycles, `N${giiiCycle}`), null);
assert.ok(Math.abs(get(cycles, `O${giiiCycle}`) - 0.2) < 1e-10);
assert.equal(get(brandSocial, 'AA10'), 'Comments');
assert.equal(get(brandSocial, 'AA7'), 'Likes');
assert.equal(get(brandSocial, 'O10'), 0);
assert.equal(get(brandSocial, 'P12'), 0);
assert.ok(Math.abs(get(brandSocial, 'R11') - (9.5/13-1)) < 1e-10);
assert.equal(get(cycles, `AJ${meemCycle}`), 2);
assert.equal(get(cycles, `AK${meemCycle}`), 6);
assert.ok(Math.abs(get(cycles, `U${meemCycle}`) + 22.71) < 1e-10);
assert.equal(get(cycles, `E${yurmanCycle}`), null);
assert.equal(get(cycles, `F${yurmanCycle}`), null);
assert.equal(get(cycles, `AC${yurmanCycle}`), '');
assert.equal(get(cycles, `AC${nordCurrentCycle}`), '');
assert.equal(get(cycles, `AC${nordHistoricalCycle}`), 1);
assert.equal(get(method, 'B126'), 80.6079);
assert.equal(get(method, 'B127'), 34.8101);
assert.equal(get(method, 'B128'), '');
assert.equal(get(method, 'B129'), '');
assert.ok(Math.abs(get(method, 'B123') - 60.74698) < 1e-10);
details.getRange(`F${yurmanRow}`).values = [[yurmanSelectedCycleKey]];
workbook.recalculate();
// Comment inputs drive only the selected group; missing/zero counts keep their meaning.
brandSocial.getRange('J10').values = [[0]];
workbook.recalculate();
assert.equal(get(delivery, `G${giiiRow}`), 23.1);
assert.equal(get(delivery, `C${giiiRow}`), 19.2);
assert.equal(get(delivery, `C${contentRowFor('DKNY')}`), 42.3);
brandSocial.getRange('J10').values = [[17]];
brandSocial.getRange('J11').clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(delivery, `G${giiiRow}`), '');
assert.equal(get(delivery, `C${giiiRow}`), '');
brandSocial.getRange('J11').values = [[9.5]];
brandSocial.getRange('I10').values = [[0]];
workbook.recalculate();
assert.equal(get(delivery, `G${giiiRow}`), '');
brandSocial.getRange('I10').values = [[8]];
cycles.getRange(`P${giiiCycle}`).values = [[100]];
workbook.recalculate();
assert.equal(get(delivery, `C${giiiRow}`), 42.3);
assert.equal(get(delivery, `D${giiiRow}`), 'Neutral');
cycles.getRange(`P${giiiCycle}`).clear({ applyTo: 'contents' });
// A lower social input changes ME+EM's Good result despite its capped financial lead.
cycles.getRange(`N${meemCycle}`).values = [[523]];
workbook.recalculate();
assert.equal(get(delivery, `G${meemRow}`), 50);
assert.equal(get(delivery, `C${meemRow}`), 71);
cycles.getRange(`N${meemCycle}`).values = [[0]];
workbook.recalculate();
assert.equal(get(delivery, `G${meemRow}`), 0);
assert.equal(get(delivery, `C${meemRow}`), 56);
assert.equal(get(delivery, `D${meemRow}`), 'Neutral');
cycles.getRange(`N${meemCycle}`).values = [[1335.5]];
// An assumption in a separate source proxy never fills observed Strength/standard total.
method.getRange('B122').values = [[80]];
workbook.recalculate();
assert.ok(Math.abs(get(method, 'B123') - 66.74698) < 1e-10);
assert.equal(get(method, 'B128'), '');
assert.equal(get(method, 'B129'), '');
assert.equal(get(delivery, `I${nordRow}`), '');
assert.equal(get(delivery, `C${nordRow}`), '');
method.getRange('B122').clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(method, 'B123'), '');
method.getRange('B122').values = [[50]];
workbook.recalculate();
assert.equal(get(delivery, `C${giiiRow}`), 33.3);
assert.equal(get(delivery, `C${meemRow}`), 86);
assert.equal(get(method, 'B128'), '');
assert.equal(get(method, 'B129'), '');
const rimowaRow = contentRowFor('RIMOWA');
const bloomRow = contentRowFor('Bloomingdales');
const rimowaCycle = cycleRowByKey.get(data.selectedCycles.RIMOWA);
const bloomCycle = cycleRowByKey.get(data.selectedCycles.Bloomingdales);
assert.deepEqual(delivery.getRange(`C${rimowaRow}:J${rimowaRow}`).values[0], [46.3, 'Neutral', 50.4, 'Neutral', 50.4, 'Neutral', 30, 'Fallback']);
assert.deepEqual(delivery.getRange(`C${bloomRow}:J${bloomRow}`).values[0], [37.1, 'Needs improvement', 47.5, 'Neutral', 24.6, 'Negative', 30, 'Fallback']);
assert.equal(get(delivery, `K${rimowaRow}`), 'rimowa.com');
assert.equal(get(delivery, `L${rimowaRow}`), 'rimowa');
assert.equal(get(details, `C${rimowaRow}`), '');
assert.equal(get(details, `D${rimowaRow}`), null);
assert.equal(get(details, `C${bloomRow}`), 'Bloomingdales');
assert.equal(get(details, `D${bloomRow}`), 'Retailer');
assert.equal(get(details, `W${bloomRow}`), 'fashion-momentum-retailer-provisional');
assert.equal(get(details, `W${rimowaRow}`), 'fashion-momentum-luxe-provisional');
assert.equal(get(cycles, `BJ${rimowaCycle}`), 'Neutral');
assert.ok(Math.abs(get(cycles, `U${rimowaCycle}`) + 2.055746675448863) < 1e-10);
assert.ok(Math.abs(get(method, 'B93') - 73.056) < 1e-10);
assert.equal(get(method, 'B94'), 73.1);
assert.equal(get(method, 'B100'), 73.0);
assert.equal(get(method, 'B101'), 'Good');
assert.equal(get(method, 'B102'), '');
assert.equal(get(method, 'B103'), 'Incomplete');
assert.ok(Math.abs(get(method, 'B99') - ultaContext.derivedContextOverallUnrounded) < 1e-10);
const rimowaLatestGap = get(cycles, `AO${rimowaCycle}`);
const rimowaEarlierGap = get(cycles, `T${rimowaCycle}`);
cycles.getRange(`AO${rimowaCycle}`).values = [[rimowaEarlierGap - 2]];
workbook.recalculate();
assert.equal(get(delivery, `I${rimowaRow}`), 50);
assert.equal(get(delivery, `J${rimowaRow}`), 'Neutral');
assert.equal(get(delivery, `C${rimowaRow}`), 50.3);
assert.equal(get(delivery, `D${rimowaRow}`), 'Neutral');
cycles.getRange(`AO${rimowaCycle}`).values = [[rimowaEarlierGap - 2.0001]];
workbook.recalculate();
assert.equal(get(delivery, `I${rimowaRow}`), 30);
assert.equal(get(delivery, `J${rimowaRow}`), 'Fallback');
cycles.getRange(`AO${rimowaCycle}`).values = [[rimowaLatestGap]];
const originalUltaRevenue = get(cycles, `AE${ultaContextCycle}`);
cycles.getRange(`AE${ultaContextCycle}`).values = [[originalUltaRevenue + 0.1]];
workbook.recalculate();
assert.notEqual(get(method, 'B99'), ultaContext.derivedContextOverallUnrounded);
assert.equal(get(method, 'B102'), '');
assert.equal(get(delivery, `C${contentRowFor('Ulta Beauty')}`), 63.6);
assert.equal(get(delivery, `E${contentRowFor('Ulta Beauty')}`), 75.7);
assert.equal(get(delivery, `I${contentRowFor('Ulta Beauty')}`), 80);
cycles.getRange(`AE${ultaContextCycle}`).values = [[originalUltaRevenue]];
workbook.recalculate();
assert.equal(get(method, 'B100'), 73.0);
assert.equal(get(delivery, `C${rimowaRow}`), 46.3);
const vfRow = contentRowFor('VF Corporation');
const footRow = contentRowFor('Foot Locker');
const vfCycle = cycleRowByKey.get(data.selectedCycles['VF Corporation']);
const footCycle = cycleRowByKey.get(data.selectedCycles['Foot Locker']);
assert.deepEqual(delivery.getRange(`C${vfRow}:J${vfRow}`).values[0], [38.4, 'Needs improvement', 28.7, 'Low', 33.5, 'Negative', 70, 'Up and coming']);
assert.deepEqual(delivery.getRange(`C${footRow}:J${footRow}`).values[0], [36, 'Needs improvement', 0, 'Low', 100, 'Positive', 30, 'Fallback']);
assert.equal(get(delivery, `K${vfRow}`), '');
assert.equal(get(details, `C${vfRow}`), '');
assert.equal(get(details, `D${vfRow}`), null);
assert.equal(get(details, `Z${vfRow}`), null);
assert.equal(get(delivery, `K${footRow}`), 'footlocker.com');
assert.equal(get(delivery, `L${footRow}`), 'footlocker');
assert.equal(get(details, `D${footRow}`), null);
assert.equal(get(details, `W${footRow}`), 'fashion-momentum-retailer-provisional');
assert.ok(Math.abs(get(revenueProxies, 'H8')-7.677559) < 1e-10);
assert.ok(Math.abs(get(revenueProxies, 'H7')-7.988334) < 1e-10);
assert.ok(Math.abs(get(revenueProxies, 'J7')-0.000334) < 1e-10);
assert.equal(get(cycles, `AF${footCycle}`), 7.988);
assert.equal(get(cycles, `M${vfCycle}`), null);
assert.equal(get(cycles, `N${vfCycle}`), null);
assert.ok(Math.abs(get(cycles, `R${vfCycle}`)-33.50851757883291) < 1e-8);
assert.equal(get(brandSocial, 'O9'), 7);
assert.equal(get(brandSocial, 'P9'), 9);
brandSocial.getRange('Q7').values = [['No']];
workbook.recalculate();
assert.equal(get(delivery, `C${vfRow}`), 39.5);
brandSocial.getRange('Q7').values = [['Yes']];
brandSocial.getRange('I7').clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(delivery, `G${vfRow}`), '');
assert.equal(get(delivery, `C${vfRow}`), '');
brandSocial.getRange('I7').values = [[6279]];
brandSocial.getRange('J7').values = [[0]];
workbook.recalculate();
assert.equal(get(brandSocial, 'R7'), -1);
assert.equal(get(delivery, `G${vfRow}`), 33.5);
brandSocial.getRange('J7').values = [[4563]];
revenueProxies.getRange('F8').clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(delivery, `E${footRow}`), '');
assert.equal(get(delivery, `I${footRow}`), '');
assert.equal(get(delivery, `C${footRow}`), '');
assert.equal(get(delivery, `G${footRow}`), 100);
revenueProxies.getRange('F8').values = [[22.786502]];
cycles.getRange(`J${footCycle}`).clear({ applyTo: 'contents' });
cycles.getRange(`AO${footCycle}`).clear({ applyTo: 'contents' });
workbook.recalculate();
assert.ok(get(delivery, `E${footRow}`) > 0);
assert.ok(get(delivery, `C${footRow}`) > 36);
revenueProxies.getRange('F8').values = [[21.786502]];
cycles.getRange(`J${footCycle}`).values = [[0]];
cycles.getRange(`AO${footCycle}`).values = [[-10.15]];
workbook.recalculate();
assert.equal(get(delivery, `C${vfRow}`), 38.4);
assert.equal(get(delivery, `C${footRow}`), 36);
const ckRow = contentRowFor('Calvin Klein');
const tommyRow = contentRowFor('Tommy Hilfiger');
const ckCycle = cycleRowByKey.get(data.selectedCycles['Calvin Klein']);
const tommyCycle = cycleRowByKey.get(data.selectedCycles['Tommy Hilfiger']);
assert.deepEqual(delivery.getRange(`C${ckRow}:J${ckRow}`).values[0], [38.5, 'Needs improvement', 5.1, 'Low', 100, 'Positive', 30, 'Fallback']);
assert.deepEqual(delivery.getRange(`C${tommyRow}:J${tommyRow}`).values[0], [54.7, 'Neutral', 37.3, 'Low', 100, 'Positive', 30, 'Fallback']);
assert.ok(Math.abs(get(cycles, `L${ckCycle}`) - 5.075) < 1e-10);
assert.ok(Math.abs(get(cycles, `L${tommyCycle}`) - 37.325) < 1e-10);
assert.ok(Math.abs(get(cycles, `U${tommyCycle}`) + 2.03) < 1e-10);
assert.equal(get(details, `C${ckRow}`), 'PVH');
assert.equal(get(delivery, `K${ckRow}`), 'pvh.com');
assert.equal(get(delivery, `L${ckRow}`), 'pvh');
assert.equal(get(details, `C${tommyRow}`), '');
assert.equal(get(delivery, `K${tommyRow}`), '');
assert.equal(get(delivery, `L${tommyRow}`), '');
assert.equal(get(details, `Z${tommyRow}`), null);
assert.equal(get(details, `W${tommyRow}`), 'fashion-momentum-fast-follower-provisional');
// At exactly -2pp Tommy is Neutral50; its actual -2.03pp is Fallback30.
cycles.getRange(`AO${tommyCycle}`).values = [[-2.51]];
workbook.recalculate();
assert.equal(get(delivery, `J${tommyRow}`), 'Neutral');
assert.equal(get(delivery, `I${tommyRow}`), 50);
cycles.getRange(`AO${tommyCycle}`).values = [[-2.54]];
workbook.recalculate();
assert.equal(get(delivery, `J${tommyRow}`), 'Fallback');
assert.equal(get(delivery, `C${tommyRow}`), 54.7);
// Rounded source display5.1 would change CK overall; missing growth must not use it.
cycles.getRange(`G${ckCycle}`).clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(delivery, `E${ckRow}`), '');
assert.equal(get(delivery, `C${ckRow}`), '');
cycles.getRange(`G${ckCycle}`).values = [[-0.0681]];
workbook.recalculate();
assert.equal(get(delivery, `C${ckRow}`), 38.5);
const pacsunRow = contentRowFor('PacSun');
const pacsunSelectedCycleKey = data.selectedCycles.PacSun;
const pacsunCycle = cycleRowByKey.get('pacsun-calendar-ytd-2026');
details.getRange(`F${pacsunRow}`).values = [['pacsun-calendar-ytd-2026']];
workbook.recalculate();
assert.deepEqual(delivery.getRange(`C${pacsunRow}:J${pacsunRow}`).values[0], ['', '', '', '', 42.2, 'Neutral', '', '']);
assert.equal(get(details, `D${pacsunRow}`), 'Brand');
assert.equal(get(details, `C${pacsunRow}`), 'PacSun');
assert.equal(get(delivery, `K${pacsunRow}`), 'pacsun.com; pacificsunwear.com');
assert.equal(get(delivery, `L${pacsunRow}`), 'pacsun');
assert.equal(get(details, `W${pacsunRow}`), 'fashion-momentum-fast-follower-provisional');
assert.equal(get(cycles, `E${pacsunCycle}`), null);
assert.equal(get(cycles, `F${pacsunCycle}`), null);
assert.equal(get(cycles, `AJ${pacsunCycle}`), 179);
assert.equal(get(cycles, `AK${pacsunCycle}`), 61);
assert.equal(get(cycles, `BI${pacsunCycle}`), '2026-10-20T18:41:26Z (UTC)');
assert.equal(get(cycles, `BK${pacsunCycle}`), 'Incomplete');
assert.equal(get(cycles, `AC${pacsunCycle}`), '');
assert.ok(Math.abs(get(cycles, `O${pacsunCycle}`) - (593 / 643 - 1)) < 1e-10);
// Revenue and score edits stay blocked until own annual series/fiscal scope are validated.
cycles.getRange(`AE${pacsunCycle}:AF${pacsunCycle}`).values = [[2, 1]];
cycles.getRange(`J${pacsunCycle}`).values = [[100]];
workbook.recalculate();
assert.equal(get(delivery, `E${pacsunRow}`), '');
assert.equal(get(delivery, `C${pacsunRow}`), '');
assert.equal(get(cycles, `AC${pacsunCycle}`), '');
cycles.getRange(`AE${pacsunCycle}:AF${pacsunCycle}`).clear({ applyTo: 'contents' });
cycles.getRange(`J${pacsunCycle}`).clear({ applyTo: 'contents' });
// A numeric zero median gives a real capped Social0; a missing median gives blank.
cycles.getRange(`P${pacsunCycle}`).clear({ applyTo: 'contents' });
cycles.getRange(`N${pacsunCycle}`).values = [[0]];
workbook.recalculate();
assert.equal(get(delivery, `G${pacsunRow}`), 0);
assert.equal(get(delivery, `H${pacsunRow}`), 'Negative');
assert.equal(get(delivery, `C${pacsunRow}`), '');
cycles.getRange(`N${pacsunCycle}`).clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(delivery, `G${pacsunRow}`), '');
assert.equal(get(delivery, `H${pacsunRow}`), '');
cycles.getRange(`N${pacsunCycle}`).values = [[593]];
workbook.recalculate();
assert.equal(get(delivery, `G${pacsunRow}`), 42.2);
assert.equal(get(delivery, `H${pacsunRow}`), 'Neutral');
cycles.getRange(`P${pacsunCycle}`).values = [[42.2]];
workbook.recalculate();
const ultaRow = contentRowFor('Ulta Beauty');
const ultaCycle = cycleRowByKey.get('ulta-beauty-fy2025');
details.getRange(`F${ultaRow}`).values = [['ulta-beauty-fy2025']];
workbook.recalculate();
const amazonRow = contentRowFor('Amazon Fashion');
const amazonCycle = cycleRowByKey.get(data.selectedCycles['Amazon Fashion']);
assert.deepEqual(delivery.getRange(`C${ultaRow}:J${ultaRow}`).values[0], ['', '', '', '', 32.6, 'Negative', '', '']);
assert.deepEqual(delivery.getRange(`C${amazonRow}:J${amazonRow}`).values[0], ['', '', '', '', 0, 'Negative', '', '']);
assert.equal(get(cycles, `BK${ultaCycle}`), 'Incomplete');
assert.equal(get(cycles, `BK${amazonCycle}`), 'Incomplete');
assert.equal(get(cycles, `AC${ultaCycle}`), '');
assert.equal(get(cycles, `AC${amazonCycle}`), '');
assert.equal(get(cycles, `E${amazonCycle}`), null);
assert.equal(get(cycles, `F${amazonCycle}`), null);
assert.equal(get(cycles, `AJ${amazonCycle}`), 62);
assert.equal(get(cycles, `AK${amazonCycle}`), 27);
assert.equal(get(details, `D${ultaRow}`), null);
assert.equal(get(details, `C${ultaRow}`), '');
assert.equal(get(details, `D${amazonRow}`), 'Retailer');
assert.equal(get(details, `C${amazonRow}`), 'Amazon Fashion');
assert.equal(get(details, `W${ultaRow}`), 'fashion-momentum-retailer-provisional');
assert.equal(get(details, `W${amazonRow}`), 'fashion-momentum-retailer-provisional');
const sephoraRow = data.peerObservations.findIndex(p => p.cycleKey === 'ulta-beauty-fy2025' && p.peer === 'Sephora') + 7;
const douglasRow = data.peerObservations.findIndex(p => p.cycleKey === 'ulta-beauty-fy2025' && p.peer === 'Douglas') + 7;
assert.ok(Math.abs(get(peers, `I${douglasRow}`) - (4.5753 / 4.451 - 1)) < 1e-10);
// Numeric peer/component edits cannot turn a known incomplete benchmark into a result.
peers.getRange(`F${sephoraRow}`).values = [[0.1]];
cycles.getRange(`J${ultaCycle}`).values = [[100]];
cycles.getRange(`AO${ultaCycle}`).values = [[10]];
workbook.recalculate();
assert.equal(get(cycles, `H${ultaCycle}`), '');
assert.equal(get(delivery, `E${ultaRow}`), '');
assert.equal(get(delivery, `I${ultaRow}`), '');
assert.equal(get(delivery, `C${ultaRow}`), '');
assert.equal(get(cycles, `AC${ultaCycle}`), '');
peers.getRange(`F${sephoraRow}`).clear({ applyTo: 'contents' });
cycles.getRange(`J${ultaCycle}`).clear({ applyTo: 'contents' });
cycles.getRange(`AO${ultaCycle}`).clear({ applyTo: 'contents' });
// A real Social zero is preserved; missing medians become blank when source override is removed.
cycles.getRange(`P${amazonCycle}`).clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(delivery, `G${amazonRow}`), 0);
assert.equal(get(delivery, `H${amazonRow}`), 'Negative');
cycles.getRange(`N${amazonCycle}`).clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(delivery, `G${amazonRow}`), '');
assert.equal(get(delivery, `H${amazonRow}`), '');
assert.equal(get(delivery, `C${amazonRow}`), '');
cycles.getRange(`N${amazonCycle}`).values = [[14]];
cycles.getRange(`P${amazonCycle}`).values = [[0]];
cycles.getRange(`P${ultaCycle}`).clear({ applyTo: 'contents' });
cycles.getRange(`N${ultaCycle}`).values = [[1285]];
workbook.recalculate();
assert.equal(get(delivery, `G${ultaRow}`), 50);
assert.equal(get(delivery, `H${ultaRow}`), 'Neutral');
assert.equal(get(delivery, `C${ultaRow}`), '');
assert.equal(get(delivery, `I${ultaRow}`), '');
cycles.getRange(`N${ultaCycle}`).values = [[1061]];
cycles.getRange(`P${ultaCycle}`).values = [[32.57]];
workbook.recalculate();
assert.equal(get(delivery, `G${ultaRow}`), 32.6);
assert.equal(get(delivery, `G${amazonRow}`), 0);
details.getRange(`F${ultaRow}`).values = [[data.selectedCycles['Ulta Beauty']]];
workbook.recalculate();
assert.deepEqual(delivery.getRange(`C${ultaRow}:J${ultaRow}`).values[0], [63.6,'Neutral',75.7,'High',32.6,'Negative',80,'Strong']);
details.getRange(`F${pacsunRow}`).values = [[pacsunSelectedCycleKey]];
workbook.recalculate();
const fiscalExamples = [
  ['Lilly Pulitzer', [42.9, 'Neutral', 40.7, 'Neutral', 28.4, 'Negative', 70, 'Up and coming']],
  ["Kohl's", [48.9, 'Neutral', 35.6, 'Low', 70.5, 'Positive', 50, 'Neutral']],
  ['Target', ['', '', 40.5, 'Neutral', '', '', 30, 'Fallback']],
];
for (const [company, expected] of fiscalExamples) {
  const row = contentRowFor(company);
  assert.deepEqual(delivery.getRange(`C${row}:J${row}`).values[0], expected);
}
const lillyRow = contentRowFor('Lilly Pulitzer');
const lillyCycle = cycleRowByKey.get(data.selectedCycles['Lilly Pulitzer']);
const targetRow = contentRowFor('Target');
const targetCycle = cycleRowByKey.get(data.selectedCycles.Target);
const kohlsRow = contentRowFor("Kohl's");
const kohlsCycle = cycleRowByKey.get(data.selectedCycles["Kohl's"]);
assert.equal(get(cycles, `BF${targetCycle}`), 37.5);
assert.equal(get(cycles, `AT${targetCycle}`), null);
assert.equal(get(cycles, `P${targetCycle}`), null);
assert.equal(get(cycles, `M${targetCycle}`), null);
assert.equal(get(cycles, `N${targetCycle}`), null);
assert.equal(get(details, `D${targetRow}`), null);
assert.equal(get(details, `C${targetRow}`), '');
assert.equal(get(details, `D${kohlsRow}`), 'Retailer');
assert.equal(get(details, `C${kohlsRow}`), "Kohl's");
assert.equal(get(details, `W${kohlsRow}`), 'fashion-momentum-retailer-provisional');
assert.equal(get(details, `W${targetRow}`), 'fashion-momentum-retailer-provisional');
assert.equal(get(cycles, `BJ${kohlsCycle}`), 'Needs improvement');
assert.equal(get(cycles, `AA${kohlsCycle}`), 'Neutral');
assert.equal(get(cycles, `BI${kohlsCycle}`), '2026-10-27T09:50:52.084760');
assert.equal(get(cycles, `BF${lillyCycle}`), 49.1);
assert.equal(get(cycles, `AJ${lillyCycle}`), 125);
assert.equal(get(cycles, `AK${lillyCycle}`), 230);
assert.equal(get(cycles, `AJ${kohlsCycle}`), 8);
assert.equal(get(cycles, `AK${kohlsCycle}`), 180);
assert.equal(get(cycles, `H${cycleRowByKey.get('lilly-pulitzer-fy2024')}`), '');
assert.equal(get(cycles, `H${cycleRowByKey.get('target-fy2024')}`), '');
// Target must keep its financial-only source score separate through missing-component edits.
cycles.getRange(`J${targetCycle}`).values = [[80]];
workbook.recalculate();
assert.equal(get(delivery, `E${targetRow}`), 80);
assert.equal(get(delivery, `C${targetRow}`), '');
assert.equal(get(delivery, `D${targetRow}`), '');
assert.equal(get(cycles, `BF${targetCycle}`), 37.5);
cycles.getRange(`J${targetCycle}`).values = [[40.5]];
// Annual social inputs drive the score when the original component override is removed.
cycles.getRange(`P${lillyCycle}`).clear({ applyTo: 'contents' });
cycles.getRange(`N${lillyCycle}`).values = [[770]];
workbook.recalculate();
assert.equal(get(delivery, `G${lillyRow}`), 50);
assert.equal(get(delivery, `H${lillyRow}`), 'Neutral');
assert.equal(get(delivery, `C${lillyRow}`), 49.4);
cycles.getRange(`N${lillyCycle}`).values = [[603.5]];
cycles.getRange(`P${lillyCycle}`).values = [[28.38]];
cycles.getRange(`P${kohlsCycle}`).clear({ applyTo: 'contents' });
cycles.getRange(`M${kohlsCycle}`).clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(delivery, `G${kohlsRow}`), '');
assert.equal(get(delivery, `C${kohlsRow}`), '');
assert.equal(get(delivery, `I${kohlsRow}`), 50);
assert.equal(get(delivery, `E${kohlsRow}`), 35.6);
cycles.getRange(`M${kohlsCycle}`).values = [[41.5]];
cycles.getRange(`P${kohlsCycle}`).values = [[70.4819]];
workbook.recalculate();
assert.equal(get(delivery, `C${kohlsRow}`), 48.9);
assert.equal(get(delivery, `D${kohlsRow}`), 'Neutral');
assert.equal(get(delivery, `C${lillyRow}`), 42.9);
assert.equal(data.records.length, 74);
assert.equal(data.enablementRows.length, 70);
assert.equal(get(delivery, 'K7'), 'burberry.com');
assert.equal(get(delivery, 'L7'), 'burberry');
assert.equal(get(delivery, `K${contentRowFor('Coach')}`), 'tapestry.com');
assert.equal(get(delivery, `L${contentRowFor('Coach')}`), 'tapestry');
assert.equal(get(delivery, `L${contentRowFor('DKNY')}`), 'giiiapparelgroup');
assert.equal(get(delivery, `L${contentRowFor('Calvin Klein')}`), 'pvh');
assert.equal(get(delivery, `K${contentRowFor('Fendi')}`), 'fendi.com; lvmh.com');
assert.equal(get(delivery, `L${contentRowFor('Fendi')}`), 'fendi; lvmh');
assert.equal(get(delivery, `L${contentRowFor('Marc Jacobs')}`), 'marcjacobs; whpglobal');
assert.equal(get(delivery, `K${contentRowFor('TOM FORD')}`), 'tomfordfashion.com; tomfordinternational.com');
assert.equal(get(delivery, `K${contentRowFor('Estée Lauder')}`), 'estee.com');
assert.equal(get(delivery, `C${contentRowFor('Estée Lauder')}`), 81.3);
assert.equal(get(details, `C${contentRowFor('Estée Lauder')}`), '');
assert.equal(get(details, `D${contentRowFor('Estée Lauder')}`), null);
assert.equal(get(details, `L${contentRowFor('Estée Lauder')}`), 'Group score provisional · identity/environment pending');
// CSV source edits flow to the delivery; blank domains remain blank.
enablement.getRange('B7').values = [['changed.example']];
enablement.getRange('C7').values = [['changed-burberry-code']];
workbook.recalculate();
assert.equal(get(delivery, 'K7'), 'changed.example');
assert.equal(get(delivery, 'L7'), 'changed-burberry-code');
enablement.getRange('B7').clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(delivery, 'K7'), '');
enablement.getRange('B7:C7').values = [['burberry.com', 'burberry']];
workbook.recalculate();
assert.equal(get(delivery, 'C7'), 61.2);
assert.equal(get(delivery, 'D7'), 'Neutral');
assert.equal(get(delivery, 'E7'), 34.5);
assert.equal(get(delivery, 'F7'), 'Low');
assert.equal(get(delivery, 'H7'), 'Positive');
assert.equal(get(delivery, 'J7'), 'Up and coming');
assert.equal(get(cycles, 'X9'), 70);
assert.equal(get(cycles, 'AS9'), 70);
assert.equal(get(cycles, 'AT9'), 61.2);
assert.equal(get(cycles, 'AU9'), true);
assert.equal(get(details, 'L7'), 'Provisional · source review');
assert.ok(Math.abs(get(details, 'T7') - 7.8) < 1e-10);
assert.equal(get(delivery, 'C8'), 60.5);
assert.equal(get(delivery, 'H8'), 'Positive');
const gapRow = contentRowFor('GAP Inc');
const gapCycleRow = cycleRowByKey.get(data.selectedCycles['GAP Inc']);
assert.deepEqual(delivery.getRange(`C${gapRow}:J${gapRow}`).values[0], [60.5, 'Neutral', 33, 'Low', 100, 'Positive', 70, 'Up and coming']);
assert.equal(get(details, `C${gapRow}`), 'GAP Inc');
assert.equal(get(details, `D${gapRow}`), 'Brand');
assert.equal(get(delivery, `K${gapRow}`), 'gap.com');
assert.equal(get(delivery, `L${gapRow}`), 'gapinc');
assert.equal(get(cycles, `M${gapCycleRow}`), null);
assert.equal(get(cycles, `N${gapCycleRow}`), null);
assert.equal(get(cycles, `AI${gapCycleRow}`), null);
assert.equal(get(cycles, `J${gapCycleRow}`), 32.9747);
assert.equal(get(cycles, `AC${gapCycleRow}`), 3);
assert.ok(Math.abs(get(cycles, `I${gapCycleRow}`) + 3.3920536485991375) < 1e-9);
assert.ok(Math.abs(get(cycles, `BE${gapCycleRow}`) - 3.723377398236807) < 1e-9);
assert.ok(Math.abs(get(cycles, `Y${gapCycleRow}`) - 60.48735) < 1e-10);
assert.equal(get(campaigns, 'P10'), 'No');
assert.equal(get(campaigns, 'O10'), '');
assert.ok(Math.abs(get(cycles, `O${gapCycleRow}`) - (2641 / 518 - 1)) < 1e-10);
// Source override cleared: child eligibility and medians drive portfolio Social and total.
cycles.getRange(`P${gapCycleRow}`).clear({ applyTo: 'contents' });
campaigns.getRange('M7:M8').values = [[2], [2]];
workbook.recalculate();
assert.equal(get(campaigns, 'P7'), 'No');
assert.equal(get(campaigns, 'P8'), 'No');
assert.ok(Math.abs(get(cycles, `O${gapCycleRow}`) - (427 / 638.5 - 1)) < 1e-10);
assert.equal(get(delivery, `G${gapRow}`), 16.9);
assert.equal(get(delivery, `H${gapRow}`), 'Negative');
assert.equal(get(delivery, `C${gapRow}`), 35.5);
// Exactly three posts is eligible; missing numeric medians remain excluded.
campaigns.getRange('J10').values = [[14650]];
campaigns.getRange('L10:M10').values = [[3, 3]];
workbook.recalculate();
assert.equal(get(campaigns, 'P10'), 'Yes');
assert.equal(get(campaigns, 'O10'), 0);
assert.ok(Math.abs(get(cycles, `O${gapCycleRow}`) - (427 / 638.5 - 1) / 2) < 1e-10);
campaigns.getRange('J10').clear({ applyTo: 'contents' });
campaigns.getRange('L10:M10').values = [[0, 1]];
campaigns.getRange('M9').values = [[2]];
workbook.recalculate();
assert.equal(get(cycles, `O${gapCycleRow}`), '');
assert.equal(get(delivery, `G${gapRow}`), '');
assert.equal(get(delivery, `C${gapRow}`), '');
campaigns.getRange('M7:M9').values = [[18], [12], [7]];
workbook.recalculate();
assert.equal(get(delivery, `C${gapRow}`), 60.5);
// Exact annual revenue pairs recalculate Momentum if reported precision is removed.
cycles.getRange(`J${gapCycleRow}`).clear({ applyTo: 'contents' });
cycles.getRange(`AE${gapCycleRow}`).values = [[15.086]];
workbook.recalculate();
assert.equal(get(cycles, `AV${gapCycleRow}`), 0);
assert.ok(get(delivery, `E${gapRow}`) < 25);
cycles.getRange(`AE${gapCycleRow}`).values = [[15.366]];
cycles.getRange(`J${gapCycleRow}`).values = [[32.9747]];
cycles.getRange(`P${gapCycleRow}`).values = [[100]];
workbook.recalculate();
assert.equal(get(delivery, `C${gapRow}`), 60.5);
assert.equal(get(cycles, 'Z7'), '');
assert.equal(get(cycles, 'Z8'), 32.6);
const ralphDeliveryRow = data.deliveryRows.findIndex(r => r.prospect === 'Ralph Lauren') + 7;
const ralphCycleRow = cycleRowByKey.get(data.selectedCycles['Ralph Lauren']);
assert.ok(ralphDeliveryRow >= 7 && ralphCycleRow >= 7);
assert.equal(get(delivery, `C${ralphDeliveryRow}`), 67.9);
assert.equal(get(delivery, `D${ralphDeliveryRow}`), 'Neutral');
assert.equal(get(delivery, `E${ralphDeliveryRow}`), 100);
assert.equal(get(delivery, `F${ralphDeliveryRow}`), 'High');
assert.equal(get(delivery, `G${ralphDeliveryRow}`), 39.7);
assert.equal(get(delivery, `H${ralphDeliveryRow}`), 'Negative');
assert.equal(get(delivery, `I${ralphDeliveryRow}`), 30);
assert.equal(get(delivery, `J${ralphDeliveryRow}`), 'Fallback');
assert.equal(get(cycles, `P${ralphCycleRow}`), 39.74);
assert.equal(get(cycles, `AJ${ralphCycleRow}`), 35);
assert.equal(get(cycles, `AK${ralphCycleRow}`), 43);
assert.ok(Math.abs(get(cycles, `U${ralphCycleRow}`) + 11.51) < 1e-10);
const tomDeliveryRow = contentRowFor('TOM FORD');
const tomCycleRow = cycleRowByKey.get(data.selectedCycles['TOM FORD']);
assert.ok(tomDeliveryRow >= 7 && tomCycleRow >= 7);
assert.deepEqual(delivery.getRange(`C${tomDeliveryRow}:J${tomDeliveryRow}`).values[0], [64.8, 'Neutral', 57.5, 'Neutral', 100, 'Positive', 30, 'Fallback']);
assert.ok(Math.abs(get(cycles, `Y${tomCycleRow}`) - 64.75) < 1e-10);
assert.ok(Math.abs(get(cycles, `I${tomCycleRow}`) - 1.5) < 1e-10);
assert.ok(Math.abs(get(cycles, `U${tomCycleRow}`) + 6.5) < 1e-10);
assert.equal(get(cycles, `V${tomCycleRow}`), 'Same-season');
assert.equal(get(cycles, `AJ${tomCycleRow}`), 5);
assert.equal(get(cycles, `AK${tomCycleRow}`), 4);
assert.equal(get(cycles, `AC${tomCycleRow}`), 2);
assert.equal(get(cycles, `AU${tomCycleRow}`), true);
assert.equal(get(cycles, `Z${cycleRowByKey.get('tom-ford-autumn-winter-2025')}`), '');
assert.equal(get(cycles, `Z${cycleRowByKey.get('tom-ford-spring-summer-2026')}`), 59.8);
// A missing prior season removes Strength and overall, while Momentum and Social remain available.
cycles.getRange(`S${tomCycleRow}`).clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(delivery, `C${tomDeliveryRow}`), '');
assert.equal(get(delivery, `I${tomDeliveryRow}`), '');
assert.equal(get(delivery, `J${tomDeliveryRow}`), '');
assert.equal(get(delivery, `E${tomDeliveryRow}`), 57.5);
assert.equal(get(delivery, `G${tomDeliveryRow}`), 100);
cycles.getRange(`S${tomCycleRow}`).values = [['tom-ford-autumn-winter-2025']];
// Remove the reported Momentum value to exercise calculation from own/peer growth.
cycles.getRange(`J${tomCycleRow}`).clear({ applyTo: 'contents' });
cycles.getRange(`G${tomCycleRow}`).values = [[0.07]];
workbook.recalculate();
assert.equal(get(delivery, `E${tomDeliveryRow}`), 67.5);
assert.equal(get(delivery, `F${tomDeliveryRow}`), 'Medium');
assert.equal(get(delivery, `C${tomDeliveryRow}`), 69.8);
cycles.getRange(`G${tomCycleRow}`).values = [[0.05]];
cycles.getRange(`J${tomCycleRow}`).values = [[57.5]];
workbook.recalculate();
assert.equal(get(delivery, `C${tomDeliveryRow}`), 64.8);
const newExpected = [
  ['Moncler', [49.8, 'Neutral', 27.5, 'Low', 100, 'Positive', 30, 'Fallback']],
  ['Coach', [70.2, 'Good', 100, 'High', 13.9, 'Negative', 80, 'Strong']],
  ['Estée Lauder', [81.3, 'Good', 75.7, 'High', 91.7, 'Positive', 80, 'Strong']],
  ["Victoria's Secret & Co.", [61.1, 'Neutral', 50.2, 'Neutral', 100, 'Positive', 30, 'Fallback']],
];
for (const [company, expected] of newExpected) {
  const row = contentRowFor(company);
  assert.deepEqual(delivery.getRange(`C${row}:J${row}`).values[0], expected);
}
const monclerRow = contentRowFor('Moncler');
const moncler2026 = cycleRowByKey.get('moncler-grenoble-fw2026');
assert.equal(get(cycles, `R${moncler2026}`), 100);
assert.equal(get(cycles, `L${moncler2026}`), '');
assert.equal(get(cycles, `X${moncler2026}`), '');
assert.equal(get(cycles, `Z${moncler2026}`), '');
assert.equal(get(cycles, `H${moncler2026}`), null);
assert.equal(get(cycles, `E${moncler2026}`), null);
// Selecting the newer social-only cycle must not carry over the complete FW2025 total.
details.getRange(`F${monclerRow}`).values = [['moncler-grenoble-fw2026']];
workbook.recalculate();
assert.equal(get(delivery, `C${monclerRow}`), '');
assert.equal(get(delivery, `E${monclerRow}`), '');
assert.equal(get(delivery, `G${monclerRow}`), 100);
assert.equal(get(delivery, `I${monclerRow}`), '');
details.getRange(`F${monclerRow}`).values = [['moncler-grenoble-fw2025']];
const coachCycleRow = cycleRowByKey.get(data.selectedCycles.Coach);
const coachRow = contentRowFor('Coach');
assert.equal(get(cycles, `X${coachCycleRow}`), 80);
assert.equal(get(cycles, `AS${coachCycleRow}`), 70);
assert.equal(get(cycles, `AT${coachCycleRow}`), 68.2);
assert.equal(get(cycles, `AU${coachCycleRow}`), false);
assert.equal(get(cycles, `BD${coachCycleRow}`), 'Agreed rule supersedes source');
assert.ok(Math.abs(get(cycles, `AV${coachCycleRow}`) - (6914.7/5598.5-1)) < 1e-10);
assert.equal(get(cycles, `Z${cycleRowByKey.get('coach-fall-2025')}`), 73.4);
// Exact own revenue drives derived Momentum when the reported component is absent.
cycles.getRange(`J${coachCycleRow}`).clear({ applyTo: 'contents' });
cycles.getRange(`AE${coachCycleRow}`).values = [[5598.5]];
workbook.recalculate();
assert.equal(get(cycles, `AV${coachCycleRow}`), 0);
assert.ok(get(delivery, `E${coachRow}`) < 50);
assert.ok(get(delivery, `C${coachRow}`) < 70);
cycles.getRange(`AE${coachCycleRow}`).values = [[6914.7]];
cycles.getRange(`J${coachCycleRow}`).values = [[100]];
const elcCycleRow = cycleRowByKey.get(data.selectedCycles['Estée Lauder']);
const elcRow = contentRowFor('Estée Lauder');
assert.equal(get(cycles, `AS${elcCycleRow}`), 70);
assert.equal(get(cycles, `AT${elcCycleRow}`), 79.3);
assert.equal(get(cycles, `AU${elcCycleRow}`), false);
assert.equal(get(cycles, `AY${elcCycleRow}`), 'Annual group account');
assert.equal(get(cycles, `D${elcCycleRow}`), null);
assert.equal(get(cycles, `AK${elcCycleRow}`), 76);
// Annual social inputs recalculate without converting the record into a runway window.
cycles.getRange(`P${elcCycleRow}`).clear({ applyTo: 'contents' });
cycles.getRange(`N${elcCycleRow}`).values = [[471]];
workbook.recalculate();
assert.equal(get(delivery, `G${elcRow}`), 50);
assert.equal(get(delivery, `H${elcRow}`), 'Neutral');
assert.equal(get(delivery, `C${elcRow}`), 68.8);
cycles.getRange(`N${elcCycleRow}`).values = [[667.5]];
cycles.getRange(`P${elcCycleRow}`).values = [[91.72]];
cycles.getRange(`AO${elcCycleRow}`).values = [[-1]];
workbook.recalculate();
assert.equal(get(delivery, `J${elcRow}`), 'Up and coming');
assert.equal(get(delivery, `I${elcRow}`), 70);
assert.equal(get(delivery, `C${elcRow}`), 79.3);
cycles.getRange(`AO${elcCycleRow}`).values = [[5.129]];
workbook.recalculate();
assert.equal(get(delivery, `C${elcRow}`), 81.3);
assert.equal(get(delivery, `C${coachRow}`), 70.2);
assert.equal(get(delivery, `C${monclerRow}`), 49.8);
// Ralph Lauren changes from Fallback to Neutral at exactly -2 pp, despite leading peers.
const ralphSourceGap = get(cycles, `AO${ralphCycleRow}`);
const ralphPriorGap = get(cycles, `T${ralphCycleRow}`);
cycles.getRange(`AO${ralphCycleRow}`).values = [[ralphPriorGap - 2]];
workbook.recalculate();
assert.equal(get(delivery, `J${ralphDeliveryRow}`), 'Neutral');
assert.equal(get(delivery, `I${ralphDeliveryRow}`), 50);
assert.equal(get(delivery, `C${ralphDeliveryRow}`), 71.9);
assert.equal(get(delivery, `D${ralphDeliveryRow}`), 'Good');
cycles.getRange(`AO${ralphCycleRow}`).values = [[ralphSourceGap]];
workbook.recalculate();
assert.equal(get(delivery, `C${ralphDeliveryRow}`), 67.9);
assert.equal(get(delivery, `J${ralphDeliveryRow}`), 'Fallback');
cycles.getRange('J9').values = [[0]];
workbook.recalculate();
assert.equal(get(delivery, 'C7'), 44);
assert.equal(get(delivery, 'E7'), 0);
cycles.getRange('S9').clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(delivery, 'C7'), '');
assert.equal(get(delivery, 'D7'), '');
assert.equal(get(delivery, 'J7'), '');
cycles.getRange('S9').values = [['burberry-summer-2025']];
cycles.getRange('AO9').values = [[-10.90]];
cycles.getRange('J9').values = [[60]];
workbook.recalculate();
assert.equal(get(delivery, 'C7'), 70);
assert.equal(get(delivery, 'D7'), 'Good');
cycles.getRange('J9').values = [[34.49]];
cycles.getRange('AO9').values = [[-3.10]];
cycles.getRange('M9:N9').values = [[1000, 1000]];
cycles.getRange('P9').clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(cycles, 'R9'), 50);
assert.equal(get(delivery, 'C7'), 46.2);
cycles.getRange('M9:N9').values = [[3589, 6456]];
cycles.getRange('P9').values = [[100]];
for (const [score, label] of [[0, 'Negative'], [39.9, 'Negative'], [40, 'Neutral'], [60, 'Neutral'], [60.01, 'Positive'], [100, 'Positive']]) {
  cycles.getRange('P9').values = [[score]];
  workbook.recalculate();
  assert.equal(get(delivery, 'H7'), label);
}
for (const [score, label] of [[0, 'Low'], [39.9, 'Low'], [40, 'Neutral'], [60, 'Neutral'], [60.01, 'Medium'], [74.99, 'Medium'], [75, 'High'], [100, 'High']]) {
  cycles.getRange('J9').values = [[score]];
  workbook.recalculate();
  assert.equal(get(delivery, 'F7'), label);
}
cycles.getRange('J9').values = [[34.49]];
for (const [change, label, score] of [[-3, 'Fallback', 30], [-2, 'Neutral', 50], [0, 'Neutral', 50], [1.99, 'Neutral', 50], [2, 'Neutral', 50], [2.01, 'Up and coming', 70], [7.8, 'Up and coming', 70]]) {
  cycles.getRange('AO9').values = [[-10.9 + change]];
  workbook.recalculate();
  assert.equal(get(delivery, 'J7'), label);
  assert.equal(get(delivery, 'I7'), score);
}
// Cross the peer benchmark while improvement exceeds +2 pp.
for (const [gap, label, score] of [[-0.01, 'Up and coming', 70], [0, 'Strong', 80], [0.01, 'Strong', 80]]) {
  cycles.getRange('AO9').values = [[gap]];
  workbook.recalculate();
  assert.equal(get(delivery, 'J7'), label);
  assert.equal(get(delivery, 'I7'), score);
  assert.equal(get(delivery, 'C7'), score === 80 ? 63.2 : 61.2);
}
// Removing the current gap leaves both category and score unavailable.
cycles.getRange('AO9').clear({ applyTo: 'contents' });
cycles.getRange('G9').clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(delivery, 'J7'), '');
assert.equal(get(delivery, 'I7'), '');
assert.equal(get(delivery, 'C7'), '');
cycles.getRange('G9').values = [[0.0508]];
cycles.getRange('AO9').values = [[-3.10]];
workbook.recalculate();
assert.equal(get(delivery, 'C7'), 61.2);
assert.equal(get(delivery, 'D7'), 'Neutral');
assert.equal(get(delivery, 'J7'), 'Up and coming');
assert.equal(get(cycles, 'AU9'), true);
assert.equal(get(details, 'X7'), null);
assert.equal(get(details, 'E7'), null);
// The display-only transformation must preserve blanks and respond to original-index edits.
const originalIndexFormulas = delivery.getRange(`C7:C${deliveryEnd}`).formulas;
const checkNormalizedIndices = () => {
  data.deliveryRows.forEach((r, index) => {
    assert.equal(get(delivery, `C${index + 7}`), r.overallScore ?? '');
    assert.equal(get(delivery, `S${index + 7}`), r.normalizedFashionMomentumIndex ?? '');
  });
};
checkNormalizedIndices();
assert.equal(get(delivery, `S${contentRowFor('Marc Jacobs')}`), 70);
assert.equal(get(delivery, `S${contentRowFor('J.Crew')}`), 98);
assert.equal(get(delivery, `S${meemRow}`), 94.3);
const fendiRow = contentRowFor('Fendi');
const fendiAnnualCycle = cycleRowByKey.get(data.selectedCycles.Fendi);
const fendiShowCycle = cycleRowByKey.get(fendiAlternatives.separateShowCycleKey);
assert.deepEqual(delivery.getRange(`C${fendiRow}:J${fendiRow}`).values[0], [47.3, 'Neutral', 50.4, 'Neutral', 53.6, 'Neutral', 30, 'Fallback']);
assert.equal(get(delivery, `S${fendiRow}`), data.deliveryRows.find(r => r.prospect === 'Fendi').normalizedFashionMomentumIndex);
assert.equal(get(details, `C${fendiRow}`), 'LVMH');
assert.equal(get(delivery, `K${fendiRow}`), 'fendi.com; lvmh.com');
assert.equal(get(delivery, `L${fendiRow}`), 'fendi; lvmh');
assert.equal(get(delivery, `Q${fendiRow}`), 'Unavailable');
assert.equal(get(details, `W${fendiRow}`), 'fashion-momentum-luxe-provisional');
assert.equal(get(method, 'B162'), 47);
assert.equal(get(cycles, `R${fendiShowCycle}`), 100);
assert.equal(get(cycles, `L${fendiShowCycle}`), '');
assert.equal(get(cycles, `X${fendiShowCycle}`), '');
assert.equal(get(cycles, `Z${fendiShowCycle}`), '');
assert.equal(get(cycles, `AJ${fendiAnnualCycle}`), 604);
assert.equal(get(cycles, `AK${fendiAnnualCycle}`), 336);
assert.ok(Math.abs(get(cycles, `Y${fendiAnnualCycle}`) - 47.2902) < 1e-10);
const belmontRow = contentRowFor('Belmont Park Village');
const louboutinRow = contentRowFor('Christian Louboutin');
const belmontCycle = cycleRowByKey.get(data.selectedCycles['Belmont Park Village']);
const louboutinCycle = cycleRowByKey.get(data.selectedCycles['Christian Louboutin']);
for (const row of [belmontRow, louboutinRow]) {
  assert.deepEqual(delivery.getRange(`C${row}:J${row}`).values[0], Array(8).fill(''));
  assert.equal(get(delivery, `S${row}`), '');
  assert.equal(get(delivery, `O${row}`), 'Coverage only');
  assert.equal(get(details, `W${row}`), row === belmontRow ? 'fashion-momentum-retailer-provisional' : 'fashion-momentum-luxe-provisional');
}
assert.equal(get(cycles, `N${belmontCycle}`), null);
assert.equal(get(cycles, `N${louboutinCycle}`), 8590);
assert.equal(get(cycles, `AK${belmontCycle}`), 2);
assert.equal(get(cycles, `AK${louboutinCycle}`), 1);
assert.equal(get(details, `C${belmontRow}`), 'Belmont Park Village');
assert.equal(get(details, `C${louboutinRow}`), 'Christian Louboutin');
assert.ok(Math.abs(get(method, 'B177') - mentionContext.derivedShareChangePercent/100) < 1e-12);
assert.ok(Math.abs(get(method, 'B178') - 0.4) < 1e-12);
const newBalanceRow = contentRowFor('New Balance');
const marcRow = contentRowFor('Marc Jacobs');
const dknyRow = contentRowFor('DKNY');
const exemplarRow = contentRowFor('Exemplar Luxury Group');
const newBalanceCycle = cycleRowByKey.get(data.selectedCycles['New Balance']);
const marcCycle = cycleRowByKey.get(data.selectedCycles['Marc Jacobs']);
const dknyCycle = cycleRowByKey.get(data.selectedCycles['DKNY']);
assert.deepEqual(delivery.getRange(`C${newBalanceRow}:J${newBalanceRow}`).values[0], [66, 'Neutral', 100, 'High', 0, 'Negative', 80, 'Strong']);
assert.deepEqual(delivery.getRange(`C${marcRow}:J${marcRow}`).values[0], [20, 'Needs improvement', 11.5, 'Low', 0.7, 'Negative', 70, 'Up and coming']);
assert.deepEqual(delivery.getRange(`C${dknyRow}:J${dknyRow}`).values[0], [42.3, 'Neutral', 12.6, 'Low', 100, 'Positive', 30, 'Fallback']);
assert.equal(get(delivery, `S${newBalanceRow}`), 86.9);
assert.equal(get(delivery, `S${dknyRow}`), 78.2);
assert.equal(get(details, `C${marcRow}`), 'WHP Global / Marc Jacobs');
assert.equal(get(details, `C${dknyRow}`), 'G-III Apparel');
assert.equal(get(cycles, `M${dknyCycle}`), 8);
assert.equal(get(cycles, `N${dknyCycle}`), 15);
assert.equal(get(cycles, `AU${newBalanceCycle}`), false);
const formerSocialKeys = {'J.Crew':'jcrew-calendar-2025-social','Jacquemus':'jacquemus-calendar-2025-social','Lafayette 148':'lafayette-jun-sep-2026-social'};
for (const [name, score] of [['J.Crew', 0], ['Jacquemus', 0], ['Lafayette 148', 30.4], ['Exemplar Luxury Group', 24.8]]) {
  if (formerSocialKeys[name]) { details.getRange(`F${contentRowFor(name)}`).values = [[formerSocialKeys[name]]]; workbook.recalculate(); }
  const row = contentRowFor(name);
  assert.equal(get(delivery, `G${row}`), score);
  assert.equal(get(delivery, `C${row}`), '');
  assert.equal(get(delivery, `S${row}`), '');
  if (formerSocialKeys[name]) { details.getRange(`F${row}`).values = [[data.selectedCycles[name]]]; workbook.recalculate(); }
}
assert.ok(Math.abs(get(method, 'B201') - data.cycles.find(c => c.company === 'Exemplar Luxury Group').socialSubscoreUsed*0.375) < 1e-10);
// Source missingness must propagate rather than turn an Exemplar banner into zero.
const neimanSocialRow = socialChildren.findIndex(r => r.company === 'Exemplar Luxury Group' && r.brand === 'Neiman Marcus')+7;
const neimanMedian = get(brandSocial, `J${neimanSocialRow}`);
brandSocial.getRange(`J${neimanSocialRow}`).clear({applyTo:'contents'});
workbook.recalculate();
assert.equal(get(delivery, `G${exemplarRow}`), '');
assert.equal(get(method, 'B201'), '');
brandSocial.getRange(`J${neimanSocialRow}`).values = [[neimanMedian]];
workbook.recalculate();
assert.equal(get(delivery, `G${exemplarRow}`), 24.8);
delivery.getRange('C7').values = [[0]];
workbook.recalculate();
assert.equal(get(method, 'B145'), 0);
assert.equal(get(delivery, 'S7'), 70);
delivery.getRange(`C7:C${deliveryEnd}`).values = data.deliveryRows.map(r => [r.overallScore === null ? null : 5]);
workbook.recalculate();
assert.equal(get(delivery, 'S7'), 84);
assert.equal(get(delivery, `S${giiiRow}`), 84);
delivery.getRange(`C7:C${deliveryEnd}`).clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(method, 'B145'), '');
assert.equal(get(method, 'B146'), '');
assert.ok(delivery.getRange(`S7:S${deliveryEnd}`).values.every(row => row[0] === ''));
delivery.getRange(`C7:C${deliveryEnd}`).formulas = originalIndexFormulas;
workbook.recalculate();
checkNormalizedIndices();
for (const [index, record] of data.records.entries()) {
  for (const [key, column] of [['momentum', 'T'], ['social', 'V'], ['strength', 'X']]) {
    const kpi = record.page2[key].cardKpi;
    const actual = get(delivery, `${column}${index + 7}`);
    if (kpi) assert.ok(Math.abs(actual - kpi.value) < 1e-10, `${record.prospectName} ${key} KPI`);
    else assert.ok(actual === null || actual === '', `${record.prospectName} ${key} missing KPI`);
  }
}
console.log((await workbook.inspect({ kind: 'table', range: 'Delivery!S6:S17', include: 'values,formulas', tableMaxRows: 12, tableMaxCols: 1, maxChars: 1800 })).ndjson);
console.log((await workbook.inspect({ kind: 'table', range: 'Delivery!A6:L9', include: 'values,formulas', tableMaxRows: 4, tableMaxCols: 12, maxChars: 2500 })).ndjson);
console.log((await workbook.inspect({ kind: 'table', range: 'Delivery!A12:J17', include: 'values,formulas', tableMaxRows: 6, tableMaxCols: 10, maxChars: 3000 })).ndjson);
console.log((await workbook.inspect({ kind: 'table', range: `Delivery!A${elcRow}:L${elcRow}`, include: 'values,formulas', tableMaxRows: 1, tableMaxCols: 12, maxChars: 2000 })).ndjson);
const errors = await workbook.inspect({ kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: { useRegex: true, maxResults: 30 }, summary: 'Formula error scan', maxChars: 2000 });
console.log(errors.ndjson);
await fs.mkdir(outputDir, { recursive: true });

// October28 new rows and exact-input calculations, including missing and real-zero Social.
for (const [name, expected] of [
  ['LVMH',[32.6,'Needs improvement',11.5,'Low',42.6,'Neutral',70,'Up and coming']],
  ['Louis Vuitton',[31.5,'Needs improvement',11.5,'Low',39.1,'Negative',70,'Up and coming']],
  ['Five Below',['','',100,'High','','',80,'Strong']],
  ['Missoni',['','','','',47.9,'Neutral','','']]]) {
  const row=contentRowFor(name);
  assert.deepEqual(delivery.getRange(`C${row}:J${row}`).values[0],expected);
}
for (const name of ['LVMH','Louis Vuitton','Missoni']) {
  const row=contentRowFor(name);
  assert.equal(get(delivery,`K${row}`),'');
  assert.equal(get(delivery,`L${row}`),'');
  assert.equal(get(details,`C${row}`),'');
}
const fiveRow=contentRowFor('Five Below');
const fiveCycle=cycleRowByKey.get(data.selectedCycles['Five Below']);
cycles.getRange(`M${fiveCycle}:N${fiveCycle}`).values=[[100,0]];
workbook.recalculate();
assert.equal(get(delivery,`G${fiveRow}`),0);
assert.equal(get(delivery,`C${fiveRow}`),66);
cycles.getRange(`M${fiveCycle}:N${fiveCycle}`).clear({applyTo:'contents'});
workbook.recalculate();
assert.equal(get(delivery,`C${fiveRow}`),'');
const matasPeerRow=data.peerObservations.findIndex(p=>p.cycleKey===data.selectedCycles['Ulta Beauty']&&p.peer==='Matas banner')+7;
const peerHeaders=peers.getRange('A6:Z6').values[0];
const peerCurrentColumn=col(peerHeaders.findIndex(h=>h==='Current revenue (scope units)')+1);
assert.ok(peerCurrentColumn);
const matasCurrent=get(peers,`${peerCurrentColumn}${matasPeerRow}`);
peers.getRange(`${peerCurrentColumn}${matasPeerRow}`).clear({applyTo:'contents'});
workbook.recalculate();
assert.equal(get(delivery,`E${ultaRow}`),'');
assert.equal(get(delivery,`C${ultaRow}`),'');
peers.getRange(`${peerCurrentColumn}${matasPeerRow}`).values=[[matasCurrent]];
workbook.recalculate();
assert.equal(get(delivery,`C${ultaRow}`),63.6);

method.getRange('A226:B236').values = [
  ['28 October report refresh', 'Ten new report files. Agreed scoring and 70–98 normalization are unchanged. Source percentiles remain context.'],
  ['Ulta replacement benchmark', 'Overall 63.6: Momentum 75.6914, Social 32.5681, agreed Strong 80. Source 61.6 uses own-growth Strength 70. Earlier 73.1/73.0 is superseded context.'],
  ['Marc Jacobs revised proxy', 'LVMH consolidated group replaces the segment/Gucci comparison. Capped total 20.0; source percentile 25 is unused. Standalone brand revenue is unavailable.'],
  ['LVMH annual window', 'Full-year median likes 2,827→2,618 gives overall 32.6. Five-month capped total 27.1 and percentile 28 use a different window/scale and remain unused.'],
  ['Louis Vuitton proxy', 'Overall 31.5 uses group peer-gap Strength 70. Source 23.5 uses own-group Strength 30. Standalone brand financial results remain unavailable.'],
  ['Five Below', 'Momentum 100 and agreed Strong 80. Source own-growth Strength 70 is unused. Missing Social leaves overall unavailable.'],
  ['Missoni conflict', 'WWD 2025 sales of 125m conflict with 130m/+5%. Conditional total 30.2 is withheld; only Social 47.9 is delivered. Separate from the CSV US distributor.'],
  ['Earlier J.Crew analogue', 'Optional unrelated Gap proxy remains unused. The new J.Crew-labelled WWD annual series supplies a conditional financial score; Madewell inclusion remains unconfirmed.'],
  ['Belmont operating KPI', 'WWD, 19 March 2026: Q4 2025 monthly footfall more than doubled versus Q3. KPI >100% is a lower bound for footfall. All scores remain unavailable.'],
  ['RIMOWA', 'Source own-segment change −5.38 pp gives Fallback 30; agreed peer-gap change is −2.05575 pp. User Stable commercial descriptor and blank own-revenue KPI are retained.'],
  ['Report-only identities', 'LVMH, Louis Vuitton and Missoni have no inferred environment, domain, code or invitation. Existing LVMH/Fendi and Missoni distributor CSV pairings remain intact.'],
];
method.getRange('A226:B236').format.wrapText=true;
method.getRange('A226:B236').format.rowHeight=62;
// Explicit revisions are source values, not replacements for financial/social observations.
let scoreRevisionsSheet = null;
const revisionRecords = publishedData.records.filter(r => r.scoreRevision);
const normalizedOverrideRecords = publishedData.records.filter(r => r.normalizedDisplayOverride);
if (revisionRecords.length) {
  scoreRevisionsSheet = workbook.worksheets.add('Score revisions');
  init(scoreRevisionsSheet, 'Supplied score revisions and reconciliation', 'V', 6 + revisionRecords.length);
  scoreRevisionsSheet.getRange('A4:V4').merge();
  scoreRevisionsSheet.getRange('A4').values = [['Amber = explicitly supplied values. Earlier calculated observations remain in Cycles and Details. Supporting replacement evidence is pending.']];
  scoreRevisionsSheet.getRange('A4:V4').format.wrapText = true;
  scoreRevisionsSheet.getRange('A4:V4').format.rowHeight = 38;
  table(scoreRevisionsSheet, 6, ['Prospect', 'Supplied underlying index', 'Overall category', 'Supplied normalized index',
    'Momentum', 'Momentum category', 'Momentum descriptor', 'Social', 'Social category', 'Social descriptor',
    'Strength', 'Strength category', 'Strength descriptor', 'Authority', 'Received date', 'Supporting inputs',
    'Earlier calculation cycle', 'Weighted component total', 'Supplied minus weighted', 'Standard min–max display',
    'Standard Momentum category', 'Revision ID'], revisionRecords.map(record => {
      const revision = record.scoreRevision;
      return [record.prospectName, revision.overallScore, revision.overallSentiment, revision.normalizedFashionMomentumIndex,
        revision.components.momentum.score, revision.components.momentum.sentiment, revision.components.momentum.descriptor,
        revision.components.social.score, revision.components.social.sentiment, revision.components.social.descriptor,
        revision.components.strength.score, revision.components.strength.sentiment, revision.components.strength.descriptor,
        revision.authority, revision.receivedDate, revision.supportingDataSupplied ? 'Supplied' : 'Not supplied',
        record.selectedCycleKey, null, null, null, null, revision.revisionId];
    }), 'SuppliedScoreRevisions');
  scoreRevisionsSheet.getRange(`A7:V${6 + revisionRecords.length}`).format.wrapText = true;
  scoreRevisionsSheet.getRange(`A7:V${6 + revisionRecords.length}`).format.rowHeight = 96;
  scoreRevisionsSheet.getRange(`B7:Q${6 + revisionRecords.length}`).format.fill = amber;
  scoreRevisionsSheet.getRange(`R7:U${6 + revisionRecords.length}`).format.fill = green;
  for (const column of ['B', 'D', 'E', 'H', 'K', 'T']) scoreRevisionsSheet.getRange(`${column}7:${column}${6 + revisionRecords.length}`).setNumberFormat('0.0');
  scoreRevisionsSheet.getRange(`R7:S${6 + revisionRecords.length}`).setNumberFormat('0.00');
  for (const column of ['A', 'G', 'J', 'M', 'P', 'Q', 'V']) scoreRevisionsSheet.getRange(`${column}1:${column}${6 + revisionRecords.length}`).format.columnWidth = 32;
  scoreRevisionsSheet.getRange(`N1:N${6 + revisionRecords.length}`).format.columnWidth = 65;
  const revisionNoteAuthor = workbook.comments.setSelf({ displayName: 'Fashion Momentum delivery', initials: 'FM' });
  revisionRecords.forEach((record, index) => {
    const sourceRow = index + 7, deliveryRow = contentRowFor(record.prospectName);
    const source = column => `'Score revisions'!${column}${sourceRow}`;
    const numeric = (column, roundDisplay = false) => `=IF(ISNUMBER(${source(column)}),${roundDisplay ? `ROUND(${source(column)},1)` : source(column)},"")`;
    for (const [column, sourceColumn] of Object.entries({ C: 'B', E: 'E', G: 'H', I: 'K' })) {
      delivery.getRange(`${column}${deliveryRow}`).formulas = [[numeric(sourceColumn, column !== 'C')]];
      delivery.getRange(`${column}${deliveryRow}`).format.fill = amber;
    }
    for (const [column, sourceColumn, scoreColumn] of [['D','C','C'],['F','F','E'],['H','I','G'],['J','L','I']]) {
      delivery.getRange(`${column}${deliveryRow}`).formulas = [[`=IF(ISNUMBER(${scoreColumn}${deliveryRow}),${source(sourceColumn)},"")`]];
    }
    delivery.getRange(`S${deliveryRow}`).formulas = [[`=IF(AND(ISNUMBER(C${deliveryRow}),ISNUMBER(${source('D')})),${source('D')},"")`]];
    delivery.getRange(`S${deliveryRow}`).format.fill = amber;
    for (const [column, sourceColumn] of [['M','G'],['O','J'],['Q','M']]) delivery.getRange(`${column}${deliveryRow}`).formulas = [[`=${source(sourceColumn)}`]];
    scoreRevisionsSheet.getRange(`R${sourceRow}`).formulas = [[`=IF(AND(ISNUMBER(E${sourceRow}),ISNUMBER(H${sourceRow}),ISNUMBER(K${sourceRow})),E${sourceRow}*'Method'!$B$5+H${sourceRow}*'Method'!$B$6+K${sourceRow}*'Method'!$B$7,"")`]];
    scoreRevisionsSheet.getRange(`S${sourceRow}`).formulas = [[`=IF(AND(ISNUMBER(B${sourceRow}),ISNUMBER(R${sourceRow})),B${sourceRow}-R${sourceRow},"")`]];
    scoreRevisionsSheet.getRange(`T${sourceRow}`).formulas = [[`=IF(ISNUMBER(B${sourceRow}),IF('Method'!$B$145='Method'!$B$146,84,ROUND('Method'!$B$143+(B${sourceRow}-'Method'!$B$145)*('Method'!$B$144-'Method'!$B$143)/('Method'!$B$146-'Method'!$B$145),1)),"")`]];
    scoreRevisionsSheet.getRange(`U${sourceRow}`).formulas = [[`=${momentumLabel(`E${sourceRow}`)}`]];
    const revision = record.scoreRevision;
    if (revision.normalizationPolicy === 'cohort-min-max') {
      scoreRevisionsSheet.getRange(`D${sourceRow}`).formulas = [[`=IF(ISNUMBER(T${sourceRow}),T${sourceRow},"")`]];
      scoreRevisionsSheet.getRange(`D${sourceRow}`).format.fill = green;
    }
    const notes = revision.acceptedMixedPeriodProxy ? {
      C: `User-approved report proxy ${revision.overallScore}: FY2024 group financials including Rack + FY2025 nameplate social + assumed Strength 50. Standard FY2025 overall is unavailable. See Score revisions and Method. Authority: ${revision.authority}.`,
      E: 'Historical FY2024 Momentum score from the report; not FY2025 financial performance.',
      I: 'User-approved report Strength assumption of 50; no observed comparable peer-gap change. This is not an observed Neutral assessment.',
    } : {
      C: `Supplied underlying overall ${revision.overallScore}; revised components weight to ${revision.reconciliation.componentWeightedOverall}. See Score revisions for reconciliation.`,
      S: `Explicit supplied normalized display ${revision.normalizedFashionMomentumIndex}; not the ordinary min–max result (${revision.reconciliation.standardNormalizedIndexForSuppliedOverall}). Source: ${revision.authority}. See Score revisions.`,
      F: `Preserve the supplied Momentum category ${revision.components.momentum.sentiment} at score ${revision.components.momentum.score}; the standard map gives ${revision.reconciliation.standardComponentSentiments.momentum}. See Score revisions.`,
      J: `Preserve the supplied Strength category ${revision.components.strength.sentiment} at score ${revision.components.strength.score}; the agreed map normally gives ${data.trendScoreMapping[revision.components.strength.sentiment]}. See Score revisions.`,
    };
    for (const [column, text] of Object.entries(notes)) workbook.notes.add({
      id: `${revision.revisionId}:${column}${deliveryRow}`,
      target: { cell: { sheetName: delivery.name, sheetId: delivery.sheetId, address: `${column}${deliveryRow}` } },
      authorId: revisionNoteAuthor.id, createdAt: '', body: { plainText: text },
    });
    details.getRange(`L${deliveryRow}`).values = [['Earlier calculated report context; current supplied values are on Score revisions']];
  });
  method.getRange('A238:B244').values = [
    ['Estée Lauder supplied revision', '28 October user instruction: normalized 86.5 / Good; underlying 78.3 / Good; Momentum 72.7 / High / Leading peers; Social 86.7 / Positive / Attention up; Strength 75.0 / Strong / Recovering.'],
    ['Component reconciliation', '50% × 72.7 + 30% × 86.7 + 20% × 75 = 77.36 (77.4), versus supplied overall 78.3. The supplied total is preserved; no hidden inputs are backsolved.'],
    ['Normalization exception', 'Supplied 86.5 is retained. Standard min–max normalization of 78.3 on the current 20.0–96.0 scale is 91.5. Other calculated rows retain the normal formula except explicitly supplied normalized-only displays.'],
    ['Category exceptions', 'Supplied Momentum High at 72.7 overrides the usual Medium threshold. Supplied Strength 75/Strong overrides the category map score of 80. No general rules change.'],
    ['Earlier source calculation', 'Cycles and Details preserve the earlier calculated overall 81.3 and original observations. Delivery references the separately recorded supplied revision.'],
    ['Insights and KPI provenance', 'Accepted core/component insights and KPIs remain earlier-report context, not evidence for this revision. JSON marks KPI qualifiers and retains the complete prior calculation.'],
    ['Evidence and publication', 'No replacement supporting report or underlying measurements were supplied. Revision remains provisional and excluded from leaderboard publication.'],
  ];
  method.getRange('A238:B244').format.wrapText = true;
  method.getRange('A238:B244').format.rowHeight = 72;
  delivery.getRange('A5').values = [['Commercial insight = own sales performance; calculated score/category measure peer-relative strength. Estée Lauder uses supplied revised scores; its insights/KPIs retain earlier evidence. See Score revisions.']];
  delivery.getRange('A5:R5').format.rowHeight = 42;
  workbook.recalculate();
  // The supplied total and display must stay independent of component edits.
  const revisedElc = revisionRecords.find(r => r.prospectName === 'Estée Lauder');
  if (revisedElc) {
    const row = contentRowFor('Estée Lauder'), sourceRow = revisionRecords.indexOf(revisedElc) + 7;
    assert.equal(get(delivery, `C${row}`), 78.3);
    assert.equal(get(delivery, `S${row}`), 86.5);
    assert.ok(Math.abs(get(scoreRevisionsSheet, `R${sourceRow}`) - 77.36) < 1e-10);
    assert.ok(Math.abs(get(scoreRevisionsSheet, `S${sourceRow}`) - 0.94) < 1e-10);
    assert.equal(get(scoreRevisionsSheet, `T${sourceRow}`), 91.5);
    assert.equal(get(scoreRevisionsSheet, `U${sourceRow}`), 'Medium');
    assert.equal(get(delivery, `F${row}`), 'High');
    assert.equal(get(delivery, `J${row}`), 'Strong');
    // A supplied original outside the old bounds rescales the other rows, but
    // does not replace an explicitly supplied normalized index or category.
    scoreRevisionsSheet.getRange(`B${sourceRow}`).values = [[99]];
    workbook.recalculate();
    assert.equal(get(method, 'B146'), 99);
    assert.equal(get(delivery, `S${meemRow}`), 93.4);
    assert.equal(get(delivery, `S${row}`), 86.5);
    assert.equal(get(scoreRevisionsSheet, `T${sourceRow}`), 98);
    scoreRevisionsSheet.getRange(`B${sourceRow}`).values = [[0]];
    workbook.recalculate();
    assert.equal(get(method, 'B145'), 0);
    assert.equal(get(delivery, `S${fendiRow}`), 83.8);
    assert.equal(get(delivery, `S${row}`), 86.5);
    assert.equal(get(scoreRevisionsSheet, `T${sourceRow}`), 70);
    scoreRevisionsSheet.getRange(`B${sourceRow}`).values = [[78.3]];
    workbook.recalculate();
    scoreRevisionsSheet.getRange(`K${sourceRow}`).values = [[80]];
    workbook.recalculate();
    assert.equal(get(delivery, `I${row}`), 80);
    assert.equal(get(delivery, `C${row}`), 78.3);
    assert.equal(get(delivery, `S${row}`), 86.5);
    assert.ok(Math.abs(get(scoreRevisionsSheet, `R${sourceRow}`) - 78.36) < 1e-10);
    scoreRevisionsSheet.getRange(`K${sourceRow}`).values = [[75]];
    scoreRevisionsSheet.getRange(`B${sourceRow}`).clear({ applyTo: 'contents' });
    workbook.recalculate();
    assert.equal(get(delivery, `C${row}`), '');
    assert.equal(get(delivery, `S${row}`), '');
    scoreRevisionsSheet.getRange(`B${sourceRow}`).values = [[78.3]];
    workbook.recalculate();
  }
}
const acceptedNordstromProxy = revisionRecords.find(r => r.prospectName === 'NORDSTROM');
if (acceptedNordstromProxy) {
  const revisionRow = revisionRecords.indexOf(acceptedNordstromProxy) + 7;
  method.getRange('A119:B119').values = [['Nordstrom user-approved mixed-period proxy', '60.7 is accepted for Delivery; standard FY2025 calculation remains unavailable.']];
  method.getRange('A132:B132').values = [['Standard calculation gap', nordContext.reasonUnused]];
  details.getRange(`I${nordRow}`).values = [['FY2024 group financials; FY2025 nameplate social; assumed Strength 50']];
  details.getRange(`L${nordRow}`).values = [['User-approved mixed-period proxy; no standard FY2025 financial total']];
  details.getRange(`AI${nordRow}`).values = [[acceptedNordstromProxy.deliveryScope]];
  delivery.getRange('A4').values = [['74 rows:31 delivered provisional totals (30 scoped results +1 accepted Nordstrom proxy),43 without totals. Five unscored partials, two coverage-only reports.']];
  workbook.recalculate();
  assert.deepEqual(delivery.getRange(`C${nordRow}:J${nordRow}`).values[0],
    [60.7, 'Neutral', 80.6, 'High', 34.8, 'Negative', 50, 'Neutral']);
  assert.equal(get(delivery, `S${nordRow}`), 85);
  assert.equal(get(method, 'B128'), '');
  assert.equal(get(method, 'B129'), '');
  // Report components and original are independent supplied inputs, with visible reconciliation.
  scoreRevisionsSheet.getRange(`K${revisionRow}`).values = [[30]];
  workbook.recalculate();
  assert.equal(get(delivery, `I${nordRow}`), 30);
  assert.equal(get(delivery, `C${nordRow}`), 60.7);
  assert.equal(get(delivery, `S${nordRow}`), 85);
  scoreRevisionsSheet.getRange(`K${revisionRow}`).values = [[50]];
  const sourceTotal = scoreRevisionsSheet.getRange(`B${revisionRow}`);
  sourceTotal.clear({ applyTo: 'contents' });
  workbook.recalculate();
  assert.equal(get(delivery, `C${nordRow}`), '');
  assert.equal(get(delivery, `S${nordRow}`), '');
  sourceTotal.values = [[60.7]];
  workbook.recalculate();
}
// Normalized-only overrides are independent of original and component scores.
const displayOverrideHeaderRow = 11 + revisionRecords.length;
if (normalizedOverrideRecords.length) {
  if (!scoreRevisionsSheet) {
    scoreRevisionsSheet = workbook.worksheets.add('Score revisions');
    init(scoreRevisionsSheet, 'Supplied normalized display revisions', 'P',
      displayOverrideHeaderRow + normalizedOverrideRecords.length);
  }
  const first = displayOverrideHeaderRow + 1, last = displayOverrideHeaderRow + normalizedOverrideRecords.length;
  scoreRevisionsSheet.getRange(`A${displayOverrideHeaderRow - 2}:P${last}`).format.font = { name: font, size: 10, color: '#222222' };
  scoreRevisionsSheet.getRange(`A${displayOverrideHeaderRow - 2}`).values = [['Normalized display only']];
  scoreRevisionsSheet.getRange(`A${displayOverrideHeaderRow - 2}`).format.font = { name: font, size: 12, bold: true, color: navy };
  table(scoreRevisionsSheet, displayOverrideHeaderRow,
    ['Prospect', 'Supplied normalized index', 'Standard min–max display', 'Supplied minus standard'],
    normalizedOverrideRecords.map(record => [record.prospectName, record.normalizedDisplayOverride.value, null, null]),
    'NormalizedDisplayOverrides');
  scoreRevisionsSheet.getRange(`N${displayOverrideHeaderRow}:P${displayOverrideHeaderRow}`).values =
    [['Authority', 'Received date', 'Supporting data']];
  scoreRevisionsSheet.getRange(`N${displayOverrideHeaderRow}:P${displayOverrideHeaderRow}`).format = {
    fill: navy, font: { name: font, size: 10, bold: true, color: '#FFFFFF' }, wrapText: true, rowHeight: 55,
  };
  scoreRevisionsSheet.getRange(`A${first}:P${last}`).format.wrapText = true;
  scoreRevisionsSheet.getRange(`A${first}:P${last}`).format.rowHeight = 42;
  scoreRevisionsSheet.getRange(`A${displayOverrideHeaderRow - 2}:P${last}`).format.verticalAlignment = 'center';
  scoreRevisionsSheet.getRange(`B${first}:B${last}`).format.fill = amber;
  scoreRevisionsSheet.getRange(`C${first}:D${last}`).format.fill = green;
  scoreRevisionsSheet.getRange(`B${first}:D${last}`).setNumberFormat('0.0');
  normalizedOverrideRecords.forEach((record, index) => {
    const sourceRow = first + index, deliveryRow = contentRowFor(record.prospectName);
    const override = record.normalizedDisplayOverride;
    const underlying = `INDEX('Delivery'!$C$7:$C$${deliveryEnd},MATCH(A${sourceRow},'Delivery'!$A$7:$A$${deliveryEnd},0))`;
    scoreRevisionsSheet.getRange(`C${sourceRow}`).formulas = [[`=IF(ISNUMBER(${underlying}),IF('Method'!$B$145='Method'!$B$146,ROUND(('Method'!$B$143+'Method'!$B$144)/2,'Method'!$B$147),ROUND('Method'!$B$143+(${underlying}-'Method'!$B$145)*('Method'!$B$144-'Method'!$B$143)/('Method'!$B$146-'Method'!$B$145),'Method'!$B$147)),"")`]];
    scoreRevisionsSheet.getRange(`D${sourceRow}`).formulas = [[`=IF(AND(ISNUMBER(B${sourceRow}),ISNUMBER(C${sourceRow})),B${sourceRow}-C${sourceRow},"")`]];
    scoreRevisionsSheet.getRange(`N${sourceRow}:P${sourceRow}`).values =
      [[override.authority, override.receivedDate, override.supportingDataSupplied ? 'Supplied' : 'Not supplied']];
    scoreRevisionsSheet.getRange(`N${sourceRow}:P${sourceRow}`).format.fill = amber;
    delivery.getRange(`S${deliveryRow}`).formulas = [[`=IF(AND(ISNUMBER(C${deliveryRow}),ISNUMBER('Score revisions'!B${sourceRow})),'Score revisions'!B${sourceRow},"")`]];
    delivery.getRange(`S${deliveryRow}`).format.fill = amber;
  });
  scoreRevisionsSheet.freezePanes.freezeRows(revisionRecords.length ? 6 : displayOverrideHeaderRow);
  workbook.recalculate();
  normalizedOverrideRecords.forEach((record, index) => {
    const sourceRow = first + index, deliveryRow = contentRowFor(record.prospectName);
    assert.equal(get(delivery, `S${deliveryRow}`), record.normalizedDisplayOverride.value);
    assert.equal(get(scoreRevisionsSheet, `C${sourceRow}`), record.normalizedDisplayOverride.standardNormalizedIndex);
    assert.ok(Math.abs(get(scoreRevisionsSheet, `D${sourceRow}`) - record.normalizedDisplayOverride.suppliedMinusStandard) < 1e-10);
  });
}
method.getRange('A256:B257').values = [
  ['ME+EM normalized display', 'User instruction, 28 October: normalized Fashion Momentum Index 86.2, retaining the supplied display; ordinary normalization was 98.0 before this annual refresh and is now 94.3. Underlying 86.0 and all component scores, categories, insights and KPIs remain unchanged.'],
  ['Nordstrom accepted proxy', 'User-approved source proxy: original 60.7 / Neutral; normalized 85.0 on current 20–96 bounds; RETAILER rank 2. Uses FY2024 finances, FY2025 social and assumed Strength 50. Standard FY2025 result remains unavailable.'],
];
method.getRange('A256:B257').format.wrapText = true;
method.getRange('A256:B257').format.rowHeight = 66;

// Check the final published values, including unchanged companies, after revisions.
for (const [index, row] of publishedData.deliveryRows.entries()) {
  const excelRow = index + 7;
  assert.deepEqual(delivery.getRange(`C${excelRow}:J${excelRow}`).values[0],
    ['overallScore','overallSentiment','momentumScore','momentumSentiment','socialScore','socialSentiment','strengthScore','strengthSentiment'].map(k => row[k] ?? ''));
  assert.equal(get(delivery, `S${excelRow}`), row.normalizedFashionMomentumIndex ?? '');
}
// Category ranks read the final displayed indices after supplied score revisions.
for (let row = 7; row <= deliveryEnd; row++) {
  delivery.getRange(`AA${row}`).formulas = [[`=IF(AND(ISNUMBER(S${row}),Z${row}<>""),1+COUNTIFS($Z$7:$Z$${deliveryEnd},Z${row},$S$7:$S$${deliveryEnd},">"&S${row}),"")`]];
}
method.getRange('A247:B253').values = [
  ['Category leaderboards', 'User-approved groups: LUXE (20), FAST FOLLOWER (30), RETAILER (13), OTHER (11). Each prospect belongs to one category.'],
  ['Ranking basis', 'Delivery Z = Category; AA = Leaderboard rank. Rank within the category by column S, the displayed normalized Fashion Momentum Index, descending.'],
  ['Ties', 'Equal displayed indices share competition ranks: 1, 2, 2, 4. Calvin Klein and VF Corporation both show 76.8 and share FAST FOLLOWER rank 10.'],
  ['Missing scores', 'Keep the category; leave rank blank when S is missing. Missing scores do not count toward ranks. Numeric zero is valid.'],
  ['Supplied revisions', 'Estée Lauder shares LUXE rank 3 with TOM FORD using its supplied normalized 86.5, not its underlying 78.3 or an ordinary normalization replacement.'],
  ['Current coverage', '31 ranked and 43 unranked prospects across 74 rows, including the accepted Nordstrom proxy. OTHER has no available scores. Categories preserve identity, audience and source scope.'],
  ['Refresh and scope', 'Ranks recalculate with S or category edits. Approved mappings live in leaderboardCategories in canonical inputs. Provisional ranks retain existing evidence/publication gates.'],
];
method.getRange('A247:B253').format.wrapText = true;
method.getRange('A247:B253').format.rowHeight = 66;
for (let row = 7; row <= deliveryEnd; row++) {
  const fromDelivery = column => `INDEX('Delivery'!$${column}$7:$${column}$${deliveryEnd},MATCH(B${row},'Delivery'!$A$7:$A$${deliveryEnd},0))`;
  const rank = fromDelivery('AA'), category = fromDelivery('Z');
  details.getRange(`X${row}`).formulas = [[`=IF(ISNUMBER(${rank}),${rank},"")`]];
  details.getRange(`W${row}`).formulas = [[`=IF(${category}="","","fashion-momentum-"&LOWER(SUBSTITUTE(${category}," ","-"))&"-provisional")`]];
}
details.getRange(`X7:X${deliveryEnd}`).setNumberFormat('0');
details.getRange(`W7:X${deliveryEnd}`).format.fill = green;
workbook.recalculate();
const verifyCategoryRanks = () => {
  for (const [index, row] of publishedData.deliveryRows.entries()) {
    assert.deepEqual(delivery.getRange(`Z${index + 7}:AA${index + 7}`).values[0],
      [row.leaderboardCategory, row.leaderboardRank ?? ''], `Category/rank disagreement: ${row.prospect}`);
    assert.equal(get(details, `X${index + 7}`), row.leaderboardRank ?? '');
  }
};
verifyCategoryRanks();
assert.equal(get(delivery, `AA${coachRow}`), 1);
assert.equal(get(delivery, `AA${meemRow}`), 3);
assert.equal(get(delivery, `AA${newBalanceRow}`), 2);
assert.equal(get(delivery, `AA${ultaRow}`), 1);
assert.equal(get(delivery, `AA${nordRow}`), 2);
assert.equal(get(delivery, `AA${elcRow}`), 3);
assert.equal(get(delivery, `AA${ckRow}`), 10);
assert.equal(get(delivery, `AA${vfRow}`), 10);
assert.equal(get(delivery, `AA${giiiRow}`), 12);
// Editing the explicit normalized input changes ranks without changing the underlying score.
const meemOverrideIndex = normalizedOverrideRecords.findIndex(r => r.prospectName === 'ME+EM');
if (meemOverrideIndex >= 0) {
  const sourceCell = `B${displayOverrideHeaderRow + 1 + meemOverrideIndex}`;
  scoreRevisionsSheet.getRange(sourceCell).values = [[95]];
  workbook.recalculate();
  assert.equal(get(delivery, `C${meemRow}`), 86);
  assert.equal(get(delivery, `S${meemRow}`), 95);
  assert.equal(get(delivery, `AA${meemRow}`), 2); // J.Crew remains higher at98.
  scoreRevisionsSheet.getRange(sourceCell).clear({ applyTo: 'contents' });
  workbook.recalculate();
  assert.equal(get(delivery, `C${meemRow}`), 86);
  assert.equal(get(delivery, `S${meemRow}`), '');
  assert.equal(get(delivery, `AA${meemRow}`), '');
  scoreRevisionsSheet.getRange(sourceCell).values = [[86.2]];
  workbook.recalculate();
  verifyCategoryRanks();
}
// Changing a grouping must update both the moved row and its old cohort.
delivery.getRange(`Z${ckRow}`).values = [['LUXE']];
workbook.recalculate();
assert.equal(get(delivery, `AA${ckRow}`), 11);
assert.equal(get(delivery, `AA${giiiRow}`), 11);
delivery.getRange(`Z${ckRow}`).values = [['FAST FOLLOWER']];
workbook.recalculate();
// Missing normalized indices have no rank; an actual zero still has a rank.
const originalCoachIndexFormula = delivery.getRange(`S${coachRow}`).formulas;
delivery.getRange(`S${coachRow}`).clear({ applyTo: 'contents' });
workbook.recalculate();
assert.equal(get(delivery, `AA${coachRow}`), '');
assert.equal(get(delivery, `AA${elcRow}`), 2);
delivery.getRange(`S${coachRow}`).values = [[0]];
workbook.recalculate();
assert.equal(get(delivery, `AA${coachRow}`), 13);
delivery.getRange(`S${coachRow}`).formulas = originalCoachIndexFormula;
workbook.recalculate();
verifyCategoryRanks();
console.log('Category leaderboard checks passed: all 74 rows, displayed-score basis, ties, category changes, missing vs zero.');

// The independent source snapshot feeds only the eight supplementary columns.
// Cached source forecasts remain snapshots; no imported formula changes scoring.
let salesSocialSheet;
if (supplement) {
  salesSocialSheet = workbook.worksheets.add('Sales and social');
  const sourceEnd = 6 + supplement.records.length;
  const safeText = value => typeof value === 'string' && value.startsWith('=') ? `'${value}` : value;
  init(salesSocialSheet, 'Supplementary sales and social', 'M', sourceEnd + 30);
  salesSocialSheet.getRange('A4:L4').merge();
  salesSocialSheet.getRange('A4').values = [[`Source: ${supplement.source.fileName} · ${supplement.source.sheet} · received ${supplement.source.receivedDate}`]];
  salesSocialSheet.getRange('A5:L5').merge();
  salesSocialSheet.getRange('A5').values = [[`${supplement.summary.matchedRows} matched brands; ${supplement.summary.unmatchedBrands.join(', ') || 'no unmatched brands'} outside Delivery. Q4 ’26 values are source forecasts.`]];
  table(salesSocialSheet, 6,
    ['Source brand', 'Matched prospect', ...supplementColumns.map(c => c.label), 'Source row', 'Match status', 'Source qualifications'],
    supplement.records.map(r => [r.sourceBrand, r.prospect, ...supplementColumns.map(c => safeText(r.values[c.field])), r.sourceRow, r.matchStatus, (r.reviewNotes || []).join(' ')]),
    'SupplementarySalesSocial');
  salesSocialSheet.freezePanes.freezeColumns(2);
  salesSocialSheet.getRange(`A1:B${sourceEnd}`).format.columnWidth = 29;
  salesSocialSheet.getRange(`C1:H${sourceEnd}`).format.columnWidth = 25;
  salesSocialSheet.getRange(`I1:J${sourceEnd}`).format.columnWidth = 48;
  salesSocialSheet.getRange(`K1:L${sourceEnd}`).format.columnWidth = 23;
  salesSocialSheet.getRange('A6:L6').format.rowHeight = 80;
  salesSocialSheet.getRange(`C7:H${sourceEnd}`).setNumberFormat('0.0%;-0.0%;0.0%');
  salesSocialSheet.getRange(`C7:J${sourceEnd}`).format.fill = amber;
  salesSocialSheet.getRange(`C7:H${sourceEnd}`).format.horizontalAlignment = 'right';
  salesSocialSheet.getRange(`I7:J${sourceEnd}`).format.wrapText = true;
  salesSocialSheet.getRange(`I7:J${sourceEnd}`).format.verticalAlignment = 'top';
  salesSocialSheet.getRange(`M1:M${sourceEnd}`).format.columnWidth = 82;
  salesSocialSheet.getRange(`M7:M${sourceEnd}`).format = { wrapText: true, verticalAlignment: 'top' };
  for (const [index, item] of supplement.records.entries()) {
    if (item.values.insightsDescriptive || item.values.insightsStatistics || item.reviewNotes?.length) salesSocialSheet.getRange(`A${index + 7}:M${index + 7}`).format.autofitRows();
  }
  const notes = [
    supplement.definitions.social, supplement.definitions.sales, supplement.definitions.forecast2026,
    supplement.definitions.missing, supplement.definitions.insights,
    `File SHA-256: ${supplement.source.sha256}`,
    ...supplement.source.notes,
  ];
  notes.forEach((text, index) => {
    const row = sourceEnd + 3 + index;
    salesSocialSheet.getRange(`A${row}:M${row}`).merge();
    salesSocialSheet.getRange(`A${row}`).values = [[text]];
    salesSocialSheet.getRange(`A${row}:M${row}`).format.wrapText = true;
    salesSocialSheet.getRange(`A${row}:M${row}`).format.rowHeight = 40;
  });
  delivery.getRange('AB5:AG5').merge();
  delivery.getRange('AB5').values = [['Supplementary snapshot · mixed social windows · Q4 ’26 is a forecast']];
  delivery.getRange('AB5:AG5').format = { fill: '#DDE8E0', font: { name: font, size: 10, color: navy }, wrapText: true, rowHeight: 30 };
  delivery.getRange(`AB1:AG${deliveryEnd}`).format.columnWidth = 25;
  delivery.getRange(`AH1:AI${deliveryEnd}`).format.columnWidth = 48;
  delivery.getRange('AB6:AI6').format.rowHeight = 80;
  delivery.getRange(`AB7:AG${deliveryEnd}`).setNumberFormat('0.0%;-0.0%;0.0%');
  delivery.getRange(`AB7:AG${deliveryEnd}`).format.horizontalAlignment = 'right';
  delivery.getRange(`AH7:AI${deliveryEnd}`).format.wrapText = true;
  delivery.getRange(`AB7:AI${deliveryEnd}`).format.fill = green;
  for (let row = 7; row <= deliveryEnd; row++) {
    supplementColumns.forEach((spec, index) => {
      const sourceColumn = col(index + 3), targetColumn = col(index + 28);
      const source = `INDEX('Sales and social'!$${sourceColumn}$7:$${sourceColumn}$${sourceEnd},MATCH(A${row},'Sales and social'!$B$7:$B$${sourceEnd},0))`;
      const available = spec.type === 'percent' ? `ISNUMBER(${source})` : `${source}<>""`;
      delivery.getRange(`${targetColumn}${row}`).formulas = [[`=IF(COUNTIFS('Sales and social'!$B$7:$B$${sourceEnd},A${row})=1,IF(${available},${source},""),"")`]];
    });
  }
  workbook.recalculate();
  const verifySupplement = () => {
    publishedData.deliveryRows.forEach((r, index) => {
      assert.deepEqual(delivery.getRange(`AB${index + 7}:AI${index + 7}`).values[0], supplementColumns.map(c => r[c.field] ?? ''));
    });
  };
  verifySupplement();
  // Validate live source links, sorting, missing vs zero, and unrelated score preservation.
  const originalValues = salesSocialSheet.getRange(`A7:M${sourceEnd}`).values;
  const scoreValues = delivery.getRange(`C7:AA${deliveryEnd}`).values;
  salesSocialSheet.getRange(`A7:M${sourceEnd}`).values = [...originalValues].reverse();
  workbook.recalculate();
  verifySupplement();
  salesSocialSheet.getRange(`A7:M${sourceEnd}`).values = originalValues;
  const mutableIndex = supplement.records.findIndex(r => r.prospect && Number.isFinite(r.values.smFeb2024));
  if (mutableIndex >= 0) {
    const targetRow = contentRowFor(supplement.records[mutableIndex].prospect);
    const sourceCell = `C${mutableIndex + 7}`;
    const originalSm = salesSocialSheet.getRange(sourceCell).values;
    salesSocialSheet.getRange(sourceCell).values = [[0]];
    workbook.recalculate();
    assert.equal(get(delivery, `AB${targetRow}`), 0);
    assert.deepEqual(delivery.getRange(`C7:AA${deliveryEnd}`).values, scoreValues);
    salesSocialSheet.getRange(sourceCell).values = [[null]];
    workbook.recalculate();
    assert.equal(get(delivery, `AB${targetRow}`), '');
    assert.deepEqual(delivery.getRange(`C7:AA${deliveryEnd}`).values, scoreValues);
    salesSocialSheet.getRange(sourceCell).values = originalSm;
    workbook.recalculate();
    if (supplement.records.length > 1) {
      const otherRow = mutableIndex === 0 ? 8 : 7;
      const originalName = salesSocialSheet.getRange(`B${otherRow}`).values;
      salesSocialSheet.getRange(`B${otherRow}`).values = [[supplement.records[mutableIndex].prospect]];
      workbook.recalculate();
      assert.equal(get(delivery, `AB${targetRow}`), '');
      salesSocialSheet.getRange(`B${otherRow}`).values = originalName;
      workbook.recalculate();
    }
  }
  assert.deepEqual(delivery.getRange(`C7:AA${deliveryEnd}`).values, scoreValues);
  verifySupplement();
  // Fit only the rows whose new descriptive/statistical text needs more space.
  supplement.records.filter(r => r.prospect && (r.values.insightsDescriptive || r.values.insightsStatistics)).forEach(item => {
    const row = contentRowFor(item.prospect);
    const range = delivery.getRange(`AH${row}:AI${row}`);
    const previousHeight = range.format.rowHeight;
    range.format.autofitRows();
    range.format.rowHeight = Math.max(previousHeight, range.format.rowHeight);
    range.format.verticalAlignment = 'top';
  });
  console.log('Supplement checks passed: exact cached values, missing vs zero, sorted source links, unchanged indices/scores/insights/KPIs/ranks.');
}

// Independent YoY v2 source, with the original eight-field snapshot preserved.
let yoySheet;
let yoyEnd;
if (yoyV2) {
  const originalDelivery = delivery.getRange(`A7:AI${deliveryEnd}`).values;
  yoySheet = workbook.worksheets.add('YoY v2');
  yoyEnd = 6 + yoyV2.records.length;
  init(yoySheet, 'Q4 sales year-over-year — v2', 'H', yoyEnd + 25);
  yoySheet.getRange('A4:H4').merge();
  yoySheet.getRange('A4').values = [[`Source: ${yoyV2.source.fileName} · ${yoyV2.source.sheet} · received ${yoyV2.source.receivedDate}`]];
  yoySheet.getRange('A5:H5').merge();
  yoySheet.getRange('A5').values = [['Q4 sales versus preceding-year Q4. The 2026 comparison uses the source projection; review qualifications in H.']];
  table(yoySheet, 6,
    ['Source brand', 'Matched prospect', ...yoyColumns.map(c => c.label), 'Source row', 'Match status', 'Source qualifications'],
    yoyV2.records.map(r => [r.sourceBrand, r.prospect, ...yoyColumns.map(c => r.values[c.field]), r.sourceRow, r.matchStatus, (r.reviewNotes || []).join(' ')]),
    'SalesYoyV2');
  yoySheet.getRange(`A1:B${yoyEnd}`).format.columnWidth = 29;
  yoySheet.getRange(`C1:E${yoyEnd}`).format.columnWidth = 32;
  yoySheet.getRange(`F1:F${yoyEnd}`).format.columnWidth = 20;
  yoySheet.getRange(`G1:G${yoyEnd}`).format.columnWidth = 24;
  yoySheet.getRange(`H1:H${yoyEnd}`).format.columnWidth = 72;
  yoySheet.getRange('A6:H6').format.rowHeight = 80;
  yoySheet.getRange(`C7:E${yoyEnd}`).setNumberFormat('#,##0.0%;-#,##0.0%;0.0%');
  yoySheet.getRange(`C7:E${yoyEnd}`).format.fill = amber;
  yoySheet.getRange(`C7:E${yoyEnd}`).format.horizontalAlignment = 'right';
  yoySheet.getRange(`H7:H${yoyEnd}`).format.wrapText = true;
  yoySheet.getRange(`H7:H${yoyEnd}`).format.verticalAlignment = 'top';
  yoyV2.records.forEach((r, index) => {
    if (r.reviewNotes?.length) yoySheet.getRange(`A${index + 7}:H${index + 7}`).format.autofitRows();
  });
  const sourceNotes = [`File SHA-256: ${yoyV2.source.sha256}`, ...Object.values(yoyV2.definitions), ...yoyV2.source.notes];
  sourceNotes.forEach((text, index) => {
    const row = yoyEnd + 3 + index;
    yoySheet.getRange(`A${row}:H${row}`).merge();
    yoySheet.getRange(`A${row}`).values = [[text]];
    yoySheet.getRange(`A${row}:H${row}`).format.wrapText = true;
    yoySheet.getRange(`A${row}:H${row}`).format.rowHeight = 40;
  });
  delivery.getRange('AJ5:AL5').merge();
  delivery.getRange('AJ5').values = [['Q4 growth versus preceding year · 2026 uses a source projection']];
  delivery.getRange('AJ5:AL5').format = { fill: '#DDE8E0', font: { name: font, size: 10, color: navy }, wrapText: true, rowHeight: 30 };
  delivery.getRange(`AJ1:AL${deliveryEnd}`).format.columnWidth = 32;
  delivery.getRange('AJ6:AL6').format.rowHeight = 80;
  delivery.getRange(`AJ7:AL${deliveryEnd}`).setNumberFormat('#,##0.0%;-#,##0.0%;0.0%');
  delivery.getRange(`AJ7:AL${deliveryEnd}`).format.fill = green;
  delivery.getRange(`AJ7:AL${deliveryEnd}`).format.horizontalAlignment = 'right';
  for (let row = 7; row <= deliveryEnd; row++) {
    yoyColumns.forEach((spec, index) => {
      const sourceColumn = col(index + 3), targetColumn = col(index + 36);
      const source = `INDEX('YoY v2'!$${sourceColumn}$7:$${sourceColumn}$${yoyEnd},MATCH(A${row},'YoY v2'!$B$7:$B$${yoyEnd},0))`;
      delivery.getRange(`${targetColumn}${row}`).formulas = [[`=IF(COUNTIFS('YoY v2'!$B$7:$B$${yoyEnd},A${row})=1,IF(ISNUMBER(${source}),${source},""),"")`]];
    });
  }
  workbook.recalculate();
  const verifyYoy = () => publishedData.deliveryRows.forEach((r, index) => {
    assert.deepEqual(delivery.getRange(`AJ${index + 7}:AL${index + 7}`).values[0], yoyColumns.map(c => r[c.field] ?? ''));
  });
  verifyYoy();
  const sourceValues = yoySheet.getRange(`A7:H${yoyEnd}`).values;
  yoySheet.getRange(`A7:H${yoyEnd}`).values = [...sourceValues].reverse();
  workbook.recalculate();
  verifyYoy();
  yoySheet.getRange(`A7:H${yoyEnd}`).values = sourceValues;
  const mutableIndex = yoyV2.records.findIndex(r => r.prospect && Number.isFinite(r.values.q4VsBaseline2024YoyV2));
  if (mutableIndex >= 0) {
    const sourceRow = mutableIndex + 7, targetRow = contentRowFor(yoyV2.records[mutableIndex].prospect);
    const originalValue = yoySheet.getRange(`C${sourceRow}`).values;
    yoySheet.getRange(`C${sourceRow}`).values = [[0]];
    workbook.recalculate();
    assert.equal(get(delivery, `AJ${targetRow}`), 0);
    assert.deepEqual(delivery.getRange(`A7:AI${deliveryEnd}`).values, originalDelivery);
    yoySheet.getRange(`C${sourceRow}`).values = [[null]];
    workbook.recalculate();
    assert.equal(get(delivery, `AJ${targetRow}`), '');
    assert.deepEqual(delivery.getRange(`A7:AI${deliveryEnd}`).values, originalDelivery);
    yoySheet.getRange(`C${sourceRow}`).values = originalValue;
    if (yoyV2.records.length > 1) {
      const otherRow = mutableIndex === 0 ? 8 : 7;
      const originalName = yoySheet.getRange(`B${otherRow}`).values;
      yoySheet.getRange(`B${otherRow}`).values = [[yoyV2.records[mutableIndex].prospect]];
      workbook.recalculate();
      assert.equal(get(delivery, `AJ${targetRow}`), '');
      yoySheet.getRange(`B${otherRow}`).values = originalName;
    }
  }
  workbook.recalculate();
  verifyYoy();
  assert.deepEqual(delivery.getRange(`A7:AI${deliveryEnd}`).values, originalDelivery);
  console.log('YoY v2 checks passed: sorted source, cached blanks, zero, duplicate matches, and all 35 original fields unchanged.');
}

const annualReportContext = publishedData.sourceContext.annualReports20261028;
if (annualReportContext) {
  method.getRange('A260:F260').values = [['Annual report refresh', 'Reported raw FMI', 'Agreed raw FMI', 'Reported display', 'Delivery display', 'Source scope']];
  method.getRange('A260:F260').format = { verticalAlignment:'center', horizontalAlignment:'left', fill: navy, font: {name:font,size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:55 };
  method.getRange('C261:E265').setNumberFormat('0.0');
  method.getRange('F260:F265').format.columnWidth = 100;
  Object.entries(annualReportContext.companies).forEach(([name, source], i) => {
    const r=261+i, deliveryRow=contentRowFor(name), cycle=cycleRowByKey.get(data.selectedCycles[name]);
    details.getRange(`L${deliveryRow}`).values=[['Annual WWD proxy; core insight is earlier-source copy']];
    details.getRange(`L${deliveryRow}`).format.wrapText=true;
    details.getRange(`I${deliveryRow}:L${deliveryRow}`).format.rowHeight=64;
    method.getRange(`A${r}:F${r}`).values=[[name,source.reportedOverall,null,source.reportedNormalizedFashionMomentumIndex,null,source.sourceScopeNotes]];
    method.getRange(`C${r}`).formulas=[[`='Delivery'!C${deliveryRow}`]];
    method.getRange(`E${r}`).formulas=[[`='Delivery'!S${deliveryRow}`]];
    method.getRange(`A${r}:F${r}`).format.wrapText=true;
    method.getRange(`A${r}:F${r}`).format.rowHeight=75;
    const sample = cycles.getRange(`M${cycle}:N${cycle}`).values;
    const count = cycles.getRange(`AJ${cycle}`).values;
    const prior = cycles.getRange(`S${cycle}`).values;
    cycles.getRange(`AJ${cycle}`).values=[[19]];
    workbook.recalculate();
    assert.equal(get(delivery,`G${deliveryRow}`),'');
    assert.equal(get(delivery,`C${deliveryRow}`),'');
    cycles.getRange(`AJ${cycle}`).values=count;
    cycles.getRange(`N${cycle}`).values=[[0]];
    workbook.recalculate();
    assert.equal(get(delivery,`G${deliveryRow}`),0);
    assert.ok(Number.isFinite(get(delivery,`C${deliveryRow}`)));
    cycles.getRange(`M${cycle}:N${cycle}`).values=sample;
    cycles.getRange(`S${cycle}`).clear({applyTo:'contents'});
    workbook.recalculate();
    assert.equal(get(delivery,`I${deliveryRow}`),'');
    assert.equal(get(delivery,`C${deliveryRow}`),'');
    cycles.getRange(`S${cycle}`).values=prior;
  });
  workbook.recalculate();
  verifyCategoryRanks();
  method.getRange('A267:F268').merge();
  method.getRange('A267').values=[['2026 social uses FY2025 financials (FY2024 for Jacquemus). WWD Actual labels and source SQL are unverified. Agreed Strength compares peer-gap changes; source company-only Strength and fixed 20–94 displays remain alternatives. Accepted core copy is retained from earlier source; current component cards/KPIs carry the new references.']];
  method.getRange('A267:F268').format.wrapText=true;
  method.getRange('A267:F268').format.rowHeight=38;
}

const finalErrors = await workbook.inspect({ kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: { useRegex: true, maxResults: 30 }, summary: 'Final formula error scan', maxChars: 2000 });
console.log(finalErrors.ndjson);

const previewFilter = new Set((process.env.WWD_PREVIEW_FILES || '').split(',').filter(Boolean));
const vsCopyRow = contentRowFor("Victoria's Secret & Co.");
for (const [sheetName, range, fileName] of [
  ...Object.keys(annualReportContext?.companies || {}).flatMap(name => { const r=contentRowFor(name); const s=annualReportContext.companies[name]; const slug=s.account.slice(1); return [['Delivery',`A${r}:J${r}`,`annual-${slug}-scores.png`],['Delivery',`M${r}:AA${r}`,`annual-${slug}-cards.png`],['Details',`I${r}:L${r}`,`annual-${slug}-period-status.png`]]; }),
  ...(annualReportContext ? [['Method','A260:F268','annual-source-reconciliation.png'],['Method','A85:B87','annual-current-coverage.png']] : []),
  ...(yoyV2 ? [['YoY v2', 'A2:H17', 'yoy-v2-source.png'], ['Delivery', 'AJ5:AL17', 'yoy-v2-delivery.png'], ['YoY v2', `A${yoyV2.records.findIndex(r => r.prospect === 'Belmont Park Village') + 7}:H${yoyV2.records.findIndex(r => r.prospect === 'Belmont Park Village') + 7}`, 'yoy-v2-belmont.png'], ['Delivery', `AJ${contentRowFor('Belmont Park Village')}:AL${contentRowFor('Belmont Park Village')}`, 'yoy-v2-belmont-delivery.png'], ['YoY v2', `A${yoyEnd + 3}:H${yoyEnd + 10}`, 'yoy-v2-definitions.png']] : []),
  ...(supplement ? [['Sales and social', 'A2:M8', 'expanded-source-header.png'], ...['GAP Inc','Coach','Lafayette 148','Ralph Lauren','G-III Apparel Group','TOM FORD'].flatMap(name => { const i=supplement.records.findIndex(r => r.prospect===name), r=contentRowFor(name); return i < 0 ? [] : [['Sales and social',`I${i+7}:M${i+7}`,`expanded-${name.toLowerCase().replaceAll(' ','-')}-qualifications.png`],['Delivery',`AB${r}:AI${r}`,`expanded-${name.toLowerCase().replaceAll(' ','-')}-delivery.png`]]; }), ['Sales and social', 'A2:L13', 'sales-social-source.png'], ['Sales and social', 'A16:L27', 'sales-social-definitions.png'], ['Delivery', 'AB5:AI17', 'sales-social-delivery.png'], ['Delivery', `AB${contentRowFor('Lafayette 148')}:AI${contentRowFor('Lafayette 148')}`, 'sales-social-lafayette.png'], ['Sales and social', 'I6:J12', 'sales-social-source-insights.png'], ['Delivery', `AH${contentRowFor('Burberry')}:AI${contentRowFor('Burberry')}`, 'sales-social-burberry-insights.png'], ['Delivery', `AH${contentRowFor('Moncler')}:AI${contentRowFor('Moncler')}`, 'sales-social-moncler-insights.png'], ['Delivery', `AH${contentRowFor('Ralph Lauren')}:AI${contentRowFor('Ralph Lauren')}`, 'sales-social-ralph-insights.png'], ['Delivery', `AH${contentRowFor('TOM FORD')}:AI${contentRowFor('TOM FORD')}`, 'sales-social-tomford-insights.png']] : []),
  ['Delivery', `A${meemRow}:J${meemRow}`, 'meem-unchanged-underlying.png'],
  ['Delivery', `S${meemRow}:AA${meemRow}`, 'meem-normalized-and-rank.png'],
  ['Method', 'A256:B257', 'meem-nordstrom-method.png'],
  ...(normalizedOverrideRecords.length ? [['Score revisions', `A${displayOverrideHeaderRow}:D${displayOverrideHeaderRow + normalizedOverrideRecords.length}`, 'normalized-display-inputs.png'],
    ['Score revisions', `N${displayOverrideHeaderRow}:P${displayOverrideHeaderRow + normalizedOverrideRecords.length}`, 'normalized-display-provenance.png']] : []),
  ['Delivery', `S${nordRow}:AA${nordRow}`, 'nordstrom-proxy-normalized-rank.png'],
  ['Score revisions', `A${revisionRecords.findIndex(r => r.prospectName === 'NORDSTROM') + 7}:M${revisionRecords.findIndex(r => r.prospectName === 'NORDSTROM') + 7}`, 'nordstrom-proxy-revision.png'],
  ['Method', 'A119:B132', 'nordstrom-proxy-context.png'],
  ['Delivery', `A${nordRow}:J${nordRow}`, 'nordstrom-accepted-proxy.png'],
  ['Delivery', 'A6:A24', 'category-leaderboard-companies.png'],
  ['Delivery', 'S6:S24', 'category-leaderboard-indices.png'],
  ['Delivery', 'Z6:AA24', 'category-leaderboard-ranks.png'],
  ['Delivery', `Z${ckRow}:AA${ckRow}`, 'category-leaderboard-tie-ck.png'],
  ['Delivery', `Z${vfRow}:AA${vfRow}`, 'category-leaderboard-tie-vf.png'],
  ['Method', 'A247:B253', 'category-leaderboard-method.png'],
  ['Details', 'W6:Y12', 'category-leaderboard-details.png'],
  ['Delivery', `A${elcRow}:J${elcRow}`, 'estee-revised-scores.png'],
  ['Delivery', `M${elcRow}:Y${elcRow}`, 'estee-revised-insights.png'],
  ['Method', 'A238:B244', 'estee-revision-method.png'],
  ...(scoreRevisionsSheet ? [['Score revisions', 'A6:M7', 'estee-revision-inputs.png'], ['Score revisions', 'R6:U7', 'estee-revision-reconciliation.png']] : []),
  ...['Ulta Beauty','Marc Jacobs','RIMOWA','Belmont Park Village','LVMH','Louis Vuitton','Missoni','Five Below'].flatMap(name=>{
    const r=contentRowFor(name), slug=name.toLowerCase().replaceAll(' ','-');
    return [['Delivery',`A${r}:J${r}`,`oct28-${slug}-scores.png`],['Delivery',`M${r}:Y${r}`,`oct28-${slug}-insights.png`]];
  }),
  ['Method','A226:B236','oct28-method.png'],
  ['Peers', 'N6:P11', 'review-peer-keys.png'],
  ['Cycles', 'BL6:BM12', 'review-peer-lookups.png'],
  ['Cycles', 'G6:L11', 'review-cycle-headers.png'],
  ['Method', 'D4:E8', 'review-strength-map.png'],
  ['Method', 'A23:B25', 'review-copy-policy.png'],
  ['Delivery', `M${amazonRow}:R${amazonRow}`, 'amazon-insights.png'],
  ['Delivery', `Q${rimowaRow}:Y${rimowaRow}`, 'rimowa-stable-override.png'],
  ['Method', 'A223:B224', 'rimowa-stable-method.png'],
  ['Delivery', `Q${contentRowFor('TOM FORD')}:Y${contentRowFor("Victoria's Secret & Co.")}`, 'corrected-commercial-strength.png'],
  ['Delivery', `Q${bloomRow}:Y${bloomRow}`, 'corrected-bloomingdales-strength.png'],
  ['Method', 'A212:B221', 'commercial-strength-inputs.png'],
  ['Delivery', 'T6:Y12', 'highlight-kpis-top.png'],
  ['Delivery', `T${vsCopyRow}:Y${vsCopyRow}`, 'highlight-kpis-victoria.png'],
  ['Delivery', `M${vsCopyRow}:R${vsCopyRow}`, 'crisp-insights-victoria.png'],
  ['Delivery', 'M6:R12', 'crisp-insights-top.png'],
  ['Delivery', `T${nordRow}:Y${bloomRow}`, 'highlight-kpis-historical.png'],
  ['Delivery', `T${exemplarRow}:Y${exemplarRow}`, 'highlight-kpis-exemplar.png'],
  ['Method', 'A204:B210', 'highlight-kpis-method.png'],
  ['Delivery', `A${marcRow}:J${dknyRow}`, 'new-hybrids-delivery.png'],
  ['Delivery', `M${marcRow}:S${dknyRow}`, 'new-hybrids-insights.png'],
  ['Delivery', `A${newBalanceRow}:J${newBalanceRow}`, 'new-balance-delivery.png'],
  ['Delivery', `M${newBalanceRow}:S${newBalanceRow}`, 'new-balance-insights.png'],
  ['Delivery', `A${contentRowFor('Jacquemus')}:J${exemplarRow}`, 'new-partials-delivery.png'],
  ['Delivery', `M${contentRowFor('Jacquemus')}:S${exemplarRow}`, 'new-partials-insights.png'],
  ['Delivery', `A${contentRowFor('J.Crew')}:J${contentRowFor('J.Crew')}`, 'jcrew-delivery.png'],
  ['Details', `B${marcRow}:N${dknyRow}`, 'new-hybrids-details.png'],
  ['Details', `B${newBalanceRow}:N${newBalanceRow}`, 'new-balance-details.png'],
  ['Cycles', `M${dknyCycle}:R${dknyCycle}`, 'dkny-comment-inputs.png'],
  ['Brand social', 'C13:T14', 'exemplar-banner-inputs.png'],
  ['Method', 'A183:B202', 'nine-reports-method.png'],
  ['Delivery', `A${belmontRow}:D${belmontRow}`, 'belmont-delivery.png'],
  ['Delivery', `M${belmontRow}:S${belmontRow}`, 'belmont-insights.png'],
  ['Delivery', `A${louboutinRow}:D${louboutinRow}`, 'louboutin-delivery.png'],
  ['Delivery', `M${louboutinRow}:S${louboutinRow}`, 'louboutin-insights.png'],
  ['Details', `B${belmontRow}:N${belmontRow}`, 'belmont-details.png'],
  ['Details', `B${louboutinRow}:N${louboutinRow}`, 'louboutin-details.png'],
  ['Cycles', `M${belmontCycle}:AD${louboutinCycle}`, 'coverage-cycles.png'],
  ['Method', 'A164:B181', 'coverage-method.png'],
  ['Delivery', `A${fendiRow}:J${fendiRow}`, 'fendi-delivery.png'],
  ['Delivery', `M${fendiRow}:S${fendiRow}`, 'fendi-insights.png'],
  ['Details', `B${fendiRow}:N${fendiRow}`, 'fendi-details.png'],
  ['Cycles', `M${fendiAnnualCycle}:AD${fendiShowCycle}`, 'fendi-cycles.png'],
  ['Method', 'A153:B163', 'fendi-method.png'],
  ['Delivery', 'S6:S17', 'normalized-index.png'],
  ['Method', 'A142:B151', 'normalized-index-method.png'],
  ['Delivery', 'M6:R12', 'component-insights-top.png'],
  ['Delivery', `M${vsCopyRow}:R${vsCopyRow + 1}`, 'component-insights-victoria.png'],
  ['Delivery', `M${rimowaRow}:R${rimowaRow + 1}`, 'component-insights-rimowa.png'],
  ['Delivery', `M${bloomRow}:R${bloomRow}`, 'component-insights-bloomingdales.png'],
  ['Method', 'A134:B140', 'component-insight-method.png'],
  ['Delivery', 'A2:J18', 'delivery-compact.png'],
  ['Delivery', `A${elcRow}:L${elcRow + 1}`, 'elc-delivery.png'],
  ['Details', `B${elcRow}:N${elcRow}`, 'elc-details.png'],
  ['Cycles', 'M16:AD20', 'new-cycles.png'],
  ['Cycles', 'AV16:BD25', 'comparison-periods.png'],
  ['Cycles', 'AE23:AH25', 'coach-revenue.png'],
  ['Peers', 'B37:N42', 'coach-peers.png'],
  ['Method', 'A41:B49', 'normalization-method.png'],
  ['Method', 'A50:B54', 'gap-method.png'],
  ['Delivery', 'A6:J9', 'gap-delivery.png'],
  ['Details', 'B8:N8', 'gap-details.png'],
  ['Campaigns', 'C6:R10', 'gap-campaigns.png'],
  ['Campaigns', 'S6:Y10', 'gap-campaign-evidence.png'],
  ['Cycles', `G${gapCycleRow}:AD${gapCycleRow}`, 'gap-components.png'],
  ['Cycles', `BB${gapCycleRow}:BE${gapCycleRow}`, 'gap-strength-precision.png'],
  ['Delivery', `A${lillyRow}:J${lillyRow}`, 'lilly-delivery.png'],
  ['Delivery', `A${kohlsRow}:J${kohlsRow}`, 'kohls-delivery.png'],
  ['Delivery', `A${targetRow}:L${targetRow}`, 'target-delivery.png'],
  ['Details', `B${targetRow}:N${targetRow}`, 'target-details.png'],
  ['Cycles', `BF${lillyCycle}:BJ${kohlsCycle}`, 'annual-source-limits.png'],
  ['Method', 'A55:B60', 'annual-method.png'],
  ['Delivery', `A${ultaRow}:L${ultaRow}`, 'ulta-delivery.png'],
  ['Delivery', `A${amazonRow}:L${amazonRow}`, 'amazon-delivery.png'],
  ['Details', `B${ultaRow}:N${ultaRow}`, 'ulta-details.png'],
  ['Details', `B${amazonRow}:N${amazonRow}`, 'amazon-details.png'],
  ['Cycles', `AY${amazonCycle}:BK${amazonCycle}`, 'amazon-social-scope.png'],
  ['Method', 'A61:B64', 'social-only-method.png'],
  ['Delivery', `A${pacsunRow}:L${pacsunRow}`, 'pacsun-delivery.png'],
  ['Details', `B${pacsunRow}:N${pacsunRow}`, 'pacsun-details.png'],
  ['Cycles', `AY${pacsunCycle}:BK${pacsunCycle}`, 'pacsun-scope.png'],
  ['Method', 'A65:B67', 'pacsun-method.png'],
  ['Delivery', `A${ckRow}:L${ckRow}`, 'calvin-klein-delivery.png'],
  ['Delivery', `A${tommyRow}:L${tommyRow}`, 'tommy-hilfiger-delivery.png'],
  ['Details', `B${ckRow}:N${ckRow}`, 'calvin-klein-details.png'],
  ['Details', `B${tommyRow}:N${tommyRow}`, 'tommy-hilfiger-details.png'],
  ['Cycles', `G${ckCycle}:AD${ckCycle}`, 'calvin-klein-components.png'],
  ['Cycles', `G${tommyCycle}:AD${tommyCycle}`, 'tommy-hilfiger-components.png'],
  ['Method', 'A68:B72', 'pvh-method.png'],
  ['Delivery', `A${vfRow}:L${vfRow}`, 'vf-delivery.png'],
  ['Delivery', `A${footRow}:L${footRow}`, 'footlocker-delivery.png'],
  ['Details', `B${vfRow}:N${vfRow}`, 'vf-details.png'],
  ['Details', `B${footRow}:N${footRow}`, 'footlocker-details.png'],
  ['Brand social', 'C6:T9', 'vf-brand-social.png'],
  ['Brand social', 'U6:Z9', 'vf-social-evidence.png'],
  ['Revenue proxies', 'C6:L8', 'footlocker-revenue-proxy.png'],
  ['Revenue proxies', 'M6:P8', 'footlocker-proxy-evidence.png'],
  ['Method', 'A73:B78', 'vf-footlocker-method.png'],
  ['Delivery', `A${rimowaRow}:L${rimowaRow}`, 'rimowa-delivery.png'],
  ['Delivery', `A${bloomRow}:L${bloomRow}`, 'bloomingdales-delivery.png'],
  ['Details', `B${rimowaRow}:N${rimowaRow}`, 'rimowa-details.png'],
  ['Details', `B${bloomRow}:N${bloomRow}`, 'bloomingdales-details.png'],
  ['Cycles', `G${rimowaCycle}:AD${rimowaCycle}`, 'rimowa-components.png'],
  ['Cycles', `G${bloomCycle}:AD${bloomCycle}`, 'bloomingdales-components.png'],
  ['Method', 'A79:B87', 'hybrid-method.png'],
  ['Method', 'A89:B106', 'ulta-company-only-context.png'],
  ['Delivery', `A${giiiRow}:L${giiiRow}`, 'giii-delivery.png'],
  ['Delivery', `A${meemRow}:L${meemRow}`, 'meem-delivery.png'],
  ['Delivery', `A${yurmanRow}:L${yurmanRow}`, 'yurman-delivery.png'],
  ['Delivery', `A${nordRow}:L${nordRow}`, 'nordstrom-delivery.png'],
  ['Details', `B${giiiRow}:N${giiiRow}`, 'giii-details.png'],
  ['Details', `B${meemRow}:N${meemRow}`, 'meem-details.png'],
  ['Details', `B${yurmanRow}:N${yurmanRow}`, 'yurman-details.png'],
  ['Details', `B${nordRow}:N${nordRow}`, 'nordstrom-details.png'],
  ['Brand social', 'C9:T12', 'giii-comments.png'],
  ['Brand social', 'U9:AA12', 'giii-comment-evidence.png'],
  ['Method', 'A107:B116', 'four-reports-method.png'],
  ['Method', 'A119:B132', 'nordstrom-source-context.png'],
  ['Method', 'A27:B32', 'current-source-definitions.png'],
]) {
  if (previewFilter.size && !previewFilter.has(fileName)) continue;
  const preview = await workbook.render({ sheetName, range, scale: 1.3, format: 'png' });
  await fs.writeFile(path.join(outputDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(path.join(outputDir, 'fashion-momentum-delivery.xlsx'));
console.log('Exported one workbook. Thirty scoped formula/supplied results (24 own-unit/WWD proxies + six hybrids), six standard partials and two unscored coverage reports; Belmont/Louboutin missing-baseline and sampled-mention context verified; Fendi annual/show/percentile methods separated; G-III comments/equal median/missing-vs-zero/separate identity, ME+EM source year/social sensitivity, David matched-month metadata, Nordstrom assumed-source versus observed blanks and all prior score/routing rules verified.');
