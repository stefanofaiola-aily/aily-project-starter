import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [source, destination, previewFlag] = process.argv.slice(2);
const payload = JSON.parse(await fs.readFile(source, 'utf8'));
const wb = Workbook.create();
const spec = payload.sheets[0];
const sh = wb.worksheets.add('Delivery');
const col = index => {
  let label = '';
  for (index++; index; index = Math.floor((index - 1) / 26)) label = String.fromCharCode(65 + (index - 1) % 26) + label;
  return label;
};
const columns = new Map(spec.keys.map((key, i) => [key, col(i)]));
const fields = new Map(spec.fields.map(field => [field.field_key, field]));
const end = col(spec.keys.length - 1);
const last = Math.max(2, spec.rows.length + 1);
const range = sh.getRange(`A1:${end}${last}`);
sh.showGridLines = false;
sh.tabColor = '#213D59';
range.format.font = {name: 'Arial', size: 10, color: '#172D45'};
range.format.verticalAlignment = 'center';
range.format.rowHeight = 38;
range.format.columnWidth = 23;
range.format.wrapText = true;
sh.getRange(`A1:${end}1`).values = [spec.labels];
sh.getRange(`A1:${end}1`).format = {
  fill: '#213D59', font: {name: 'Arial', size: 10, bold: true, color: '#FFFFFF'},
  wrapText: true, rowHeight: 60, horizontalAlignment: 'center', verticalAlignment: 'center'
};
// Excel timestamps lose their zone on read. The input convention is UTC;
// never let the host's local timezone shift that recorded timestamp on export.
const spreadsheetDate = (value, type) => new Date(
  type === 'datetime' && typeof value === 'string' && !/(Z|[+-]\d{2}:\d{2})$/i.test(value)
    ? `${value}Z` : value
);
const matrix = spec.rows.map(record => spec.keys.map(key => {
  const value = record[key] ?? null;
  if (value && ['date', 'datetime'].includes(fields.get(key)?.type)) return spreadsheetDate(value, fields.get(key).type);
  const text = value && typeof value === 'object' ? JSON.stringify(value) : value;
  return typeof text === 'string' && /^[=+@]/.test(text) ? `'${text}` : text;
}));
if (matrix.length) sh.getRange(`A2:${end}${last}`).values = matrix;
const widths = new Map();
for (const [index, key] of spec.keys.entries()) {
  const field = fields.get(key);
  const cells = sh.getRange(`${col(index)}2:${col(index)}${last}`);
  if (field.type === 'date') cells.setNumberFormat('yyyy-mm-dd');
  else if (field.type === 'datetime') cells.setNumberFormat('yyyy-mm-dd hh:mm:ss');
  else if (field.unit === 'fraction') cells.setNumberFormat('0.0%');
  else if (field.unit === 'count') cells.setNumberFormat('#,##0');
  else if (key === 'display_fmi') cells.setNumberFormat('0.0');
  else if (field.unit === 'score_0_100') cells.setNumberFormat('0.0####');
  else if (field.unit === 'score_points') cells.setNumberFormat('0.0####');
  else if (field.type === 'number') cells.setNumberFormat('#,##0.0;(#,##0.0);0.0');
  const longest = Math.max(0, ...spec.rows.map(r => typeof r[key] === 'string' ? r[key].length : field.type === 'array' && r[key] ? JSON.stringify(r[key]).length : 0));
  const width = Math.min(150, Math.max(key === 'name' ? 38 : 23, Math.ceil(longest / 4) + 3));
  sh.getRange(`${col(index)}1:${col(index)}${last}`).format.columnWidth = width;
  widths.set(key, width);
}
const rawRange = `$${columns.get('raw_fmi')}$2:$${columns.get('raw_fmi')}$${last}`;
const categoryRange = `$${columns.get('leaderboard_category')}$2:$${columns.get('leaderboard_category')}$${last}`;
const displayRange = `$${columns.get('display_fmi')}$2:$${columns.get('display_fmi')}$${last}`;
for (const [index, record] of spec.rows.entries()) {
  const cell = key => `${columns.get(key)}${index + 2}`;
  const write = (key, formula) => sh.getRange(cell(key)).formulas = [[formula]];
  for (const component of ['ir', 'social', 'trend']) {
    if (record[`${component}_score`] != null) write(`${component}_contribution`, `=${cell(component + '_score')}*${cell(component + '_weight')}`);
  }
  if (record.weighted_component_fmi != null) {
    write('weighted_component_fmi', `=${cell('ir_contribution')}+${cell('social_contribution')}+${cell('trend_contribution')}`);
    if (record.reported_fmi != null) write('reported_component_difference', `=${cell('weighted_component_fmi')}-${cell('reported_fmi')}`);
  }
  if (record.raw_fmi != null) {
    write('raw_fmi', `=${cell(record.score_method === 'reported' ? 'reported_fmi' : 'weighted_component_fmi')}`);
    write('cohort_min', `=MIN(${rawRange})`);
    write('cohort_max', `=MAX(${rawRange})`);
    const p = payload.policy;
    write('display_fmi', `=ROUND(IF(${cell('cohort_min')}=${cell('cohort_max')},${p.display_equal},${p.display_lower}+(${p.display_upper}-${p.display_lower})*(${cell('raw_fmi')}-${cell('cohort_min')})/(${cell('cohort_max')}-${cell('cohort_min')})),1)`);
    write('uplift_fraction', `=${p.uplift_max}*(EXP(${p.uplift_exponent}*${cell('display_fmi')}/100)-1)/(EXP(${p.uplift_exponent})-1)`);
    write('legacy_uplift_fraction', `=IF(${cell('raw_fmi')}<=${p.legacy_uplift_threshold},0,${p.legacy_uplift_intercept}+(${cell('raw_fmi')}-${p.legacy_uplift_threshold})*${p.legacy_uplift_per_score})`);
  }
  for (const prefix of ['', 'legacy_']) if (record[prefix + 'adjusted_forecast'] != null) {
    write(prefix + 'adjustment', `=${cell('baseline_revenue')}*${cell(prefix + 'uplift_fraction')}`);
    write(prefix + 'adjusted_forecast', `=${cell('baseline_revenue')}+${cell(prefix + 'adjustment')}`);
  }
  for (const [key, amount] of [['baseline_forecast_yoy','baseline_revenue'],['adjusted_forecast_yoy','adjusted_forecast'],['legacy_adjusted_forecast_yoy','legacy_adjusted_forecast']]) {
    if (record[key] != null) write(key, `=${cell(amount)}/${cell('prior_year_actual')}-1`);
  }
  for (const [key, amount] of [
    ['baseline_forecast_vs_py_forecast_yoy','baseline_revenue'],
    ['adjusted_forecast_vs_py_forecast_yoy','adjusted_forecast'],
    ['legacy_adjusted_forecast_vs_py_forecast_yoy','legacy_adjusted_forecast'],
    ['source_legacy_adjusted_forecast_vs_py_forecast_yoy','source_legacy_adjusted_forecast']
  ]) if (record[key] != null) write(key, `=IF(AND(ISNUMBER(${cell('prior_year_forecast')}),${cell('prior_year_forecast')}>0,ISNUMBER(${cell(amount)})),${cell(amount)}/${cell('prior_year_forecast')}-1,"")`);
  if (record.fmi_increment_vs_py_forecast_pp != null) write('fmi_increment_vs_py_forecast_pp', `=IF(AND(ISNUMBER(${cell('adjusted_forecast_vs_py_forecast_yoy')}),ISNUMBER(${cell('baseline_forecast_vs_py_forecast_yoy')})),100*(${cell('adjusted_forecast_vs_py_forecast_yoy')}-${cell('baseline_forecast_vs_py_forecast_yoy')}),"")`);
  if (record.leaderboard_member_count != null) {
    write('leaderboard_member_count', `=COUNTIFS(${categoryRange},${cell('leaderboard_category')})`);
    write('leaderboard_scored_count', `=COUNTIFS(${categoryRange},${cell('leaderboard_category')},${displayRange},">="&${payload.policy.display_lower})`);
  }
  if (record.leaderboard_rank != null) write('leaderboard_rank', `=IF(ISNUMBER(${cell('display_fmi')}),1+COUNTIFS(${categoryRange},${cell('leaderboard_category')},${displayRange},">"&${cell('display_fmi')}),"")`);
  if (record.source_legacy_uplift_fraction != null) {
    const p = payload.policy;
    write('source_legacy_uplift_fraction', `=IF(${cell('source_display_fmi')}<=${p.legacy_uplift_threshold},0,${p.legacy_uplift_intercept}+(${cell('source_display_fmi')}-${p.legacy_uplift_threshold})*${p.legacy_uplift_per_score})`);
  }
  if (record.source_legacy_adjusted_forecast != null) write('source_legacy_adjusted_forecast', `=${cell('baseline_revenue')}*(1+${cell('source_legacy_uplift_fraction')})`);
  if (record.source_projection_difference != null) write('source_projection_difference', `=${cell('source_legacy_adjusted_forecast')}-${cell('source_projected_forecast')}`);
  for (const key of ['raw_fmi', 'ir_score', 'social_score', 'trend_score']) {
    const difference = `weighted_reference_${key}_difference`;
    if (record[difference] != null) write(difference, `=${cell(key)}-${cell('weighted_reference_' + key)}`);
  }
  const lines = Math.max(1, ...spec.keys.map(key => {
    const value = fields.get(key).type === 'array' && record[key] ? JSON.stringify(record[key]) : record[key];
    return typeof value === 'string' ? value.split('\n').reduce((total, line) => total + Math.max(1, Math.ceil(line.length / Math.max(10, widths.get(key) - 3))), 0) : 1;
  }));
  sh.getRange(`A${index + 2}:${end}${index + 2}`).format.rowHeight = Math.min(409, Math.max(38, 16 * lines));
}
sh.freezePanes.freezeRows(1);
sh.freezePanes.freezeColumns(3);
sh.tables.add(`A1:${end}${last}`, true, 'DossierDelivery');
// Exercise changed formula dependencies, then restore the authoritative inputs.
const probeIndex = spec.rows.findIndex(r => r.source_legacy_adjusted_forecast != null);
if (probeIndex >= 0) {
  const record = spec.rows[probeIndex];
  const address = key => `${columns.get(key)}${probeIndex + 2}`;
  const read = key => sh.getRange(address(key)).values[0][0];
  const originalDisplay = read('source_display_fmi');
  const originalForecast = read('source_legacy_adjusted_forecast');
  const originalNewForecast = read('adjusted_forecast');
  sh.getRange(address('source_display_fmi')).values = [[originalDisplay + 1]];
  wb.recalculate();
  const expectedChange = record.baseline_revenue * payload.policy.legacy_uplift_per_score;
  if (Math.abs(read('source_legacy_adjusted_forecast') - originalForecast - expectedChange) > 1e-8 || Math.abs(read('adjusted_forecast') - originalNewForecast) > 1e-8) throw new Error('Source legacy recalculation/isolation failed');
  sh.getRange(address('source_display_fmi')).values = [[originalDisplay]];
  console.log('Source legacy input-change/isolation check passed; input restored.');
}
wb.recalculate();
const pyProbe = spec.rows.findIndex(r => r.adjusted_forecast_vs_py_forecast_yoy != null);
if (pyProbe >= 0) {
  const address = key => `${columns.get(key)}${pyProbe + 2}`;
  const read = key => sh.getRange(address(key)).values[0][0];
  const prior = read('prior_year_forecast');
  const unchangedScore = read('raw_fmi');
  const unchangedForecast = read('adjusted_forecast');
  sh.getRange(address('prior_year_forecast')).values = [[prior * 2]];
  wb.recalculate();
  if (Math.abs(read('adjusted_forecast_vs_py_forecast_yoy') - (unchangedForecast / (prior * 2) - 1)) > 1e-10 || read('raw_fmi') !== unchangedScore || read('adjusted_forecast') !== unchangedForecast) throw new Error('PY comparison recalculation/isolation failed');
  sh.getRange(address('prior_year_forecast')).values = [[0]];
  wb.recalculate();
  if (!['', null].includes(read('adjusted_forecast_vs_py_forecast_yoy'))) throw new Error('Zero PY forecast should leave YoY blank');
  sh.getRange(address('prior_year_forecast')).values = [[prior]];
  wb.recalculate();
  console.log('PY forecast input-change/zero/isolation check passed; input restored.');
}
const rankProbe = spec.rows.findIndex(r => r.leaderboard_rank != null);
if (rankProbe >= 0) {
  const address = key => `${columns.get(key)}${rankProbe + 2}`;
  const original = sh.getRange(address('leaderboard_category')).values[0][0];
  sh.getRange(address('leaderboard_category')).values = [['ONE_TIME_RANK_PROBE']];
  wb.recalculate();
  if (sh.getRange(address('leaderboard_rank')).values[0][0] !== 1 || sh.getRange(address('leaderboard_scored_count')).values[0][0] !== 1) throw new Error('Category reassignment did not recalculate ranking');
  sh.getRange(address('leaderboard_category')).values = [[original]];
  wb.recalculate();
  console.log('Category rank reassignment check passed; input restored.');
}
console.log((await wb.inspect({kind:'table',range:'Delivery!A1:L4',include:'values,formulas',tableMaxRows:4,tableMaxCols:12,maxChars:2500})).ndjson);
const errors = await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:2000});
console.log(errors.ndjson);
if (previewFlag === 'true') {
  const preview = await wb.render({sheetName:'Delivery',range:'A1:L7',scale:1.25,format:'png'});
  await fs.writeFile(destination.replace(/\.xlsx$/, '.png'), new Uint8Array(await preview.arrayBuffer()));
  for (const [view, from, to] of [
    ['prior-forecast', 'prior_year_forecast', 'prior_year_forecast_comparison_status'],
    ['cards', 'ir_score', 'trend_kpi_label'],
    ['comparison', 'weighted_reference_match_status', 'weighted_reference_comparison_reason']
  ]) {
    const image = await wb.render({sheetName:'Delivery',range:`${columns.get(from)}1:${columns.get(to)}7`,scale:1,format:'png'});
    await fs.writeFile(destination.replace(/\.xlsx$/, `-${view}.png`), new Uint8Array(await image.arrayBuffer()));
  }
}
await (await SpreadsheetFile.exportXlsx(wb)).save(destination);
