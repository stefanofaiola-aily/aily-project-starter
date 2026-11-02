import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [source, destination, previewFlag] = process.argv.slice(2);
const payload = JSON.parse(await fs.readFile(source, 'utf8'));
const wb = Workbook.create();
const col = n => { let s = ''; for (n++; n; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + (n - 1) % 26) + s; return s; };
const starts = new Map();
const refs = new Map();
const dateKeys = new Set(['show_date', 'period_start', 'period_end', 'forecast_target_start', 'forecast_target_end', 'current_start', 'current_end', 'baseline_start', 'baseline_end']);
const timestampKeys = new Set(['cutoff', 'available_at', 'date_posted', 'crawled_at', 'forecast_vintage', 'follower_capture', 'prior_follower_capture']);
const booleanKeys = new Set(['prospect', 'proxy', 'approved', 'comparable', 'mapping_approved', 'reviewed', 'relevant', 'selected', 'headline', 'financial_comparable', 'social_coverage_reviewed', 'forecast_alignment_reviewed']);
const stringify = v => v && typeof v === 'object' ? JSON.stringify(v) : v;
for (const spec of payload.sheets) {
  const sh = wb.worksheets.add(spec.name);
  const start = ['inputs', 'flat-delivery'].includes(payload.kind) ? 1 : 4;
  starts.set(spec.name, start);
  refs.set(spec.name, new Map(spec.keys.map((k, i) => [k, col(i)])));
  sh.showGridLines = false;
  if (start > 1) {
    const isDelivery = spec.name === 'Delivery';
    const scoreCount = spec.rows.filter(r => r.fmi_status === 'available').length;
    sh.getRange('A2').values = [[isDelivery ? (scoreCount ? 'Fashion Momentum Index delivery' : 'FMI coverage report') : spec.name]];
    sh.getRange('A2').format.font = { name: 'Arial', size: 14, bold: true, color: '#172D45' };
    if (isDelivery) {
      const forecastCount = spec.rows.filter(r => r.forecast_status === 'available').length;
      sh.getRange('A3').values = [[`${spec.rows.length} ${spec.rows.length === 1 ? 'prospect' : 'prospects'}. ${scoreCount} reviewed FMI ${scoreCount === 1 ? 'score' : 'scores'}. ${forecastCount} adjusted ${forecastCount === 1 ? 'forecast' : 'forecasts'}.${scoreCount ? '' : ' Inputs and historical vintages require review.'}`]];
      sh.getRange('A3').format.font = { name: 'Arial', size: 10, color: '#172D45' };
      sh.getRange('A3').format.rowHeight = 24;
    }
    if (spec.name === 'Collection coverage') {
      sh.getRange('A2').values = [['FMI database collection']];
      const revenueCount = spec.rows.filter(r => r.actual_revenue_rows > 0).length;
      const socialCount = spec.rows.filter(r => r.social_capture_rows > 0).length;
      sh.getRange('A3').values = [[`${spec.rows.length} prospects. Revenue candidates for ${revenueCount}. Instagram captures for ${socialCount}. Source data, not released historical scores.`]];
      sh.getRange('A3').format.font = { name: 'Arial', size: 10, color: '#172D45' };
      sh.getRange('A3').format.rowHeight = 24;
    }
  }
  const last = Math.max(start + spec.rows.length, start + 1);
  const end = col(spec.keys.length - 1);
  const region = sh.getRange(`A${start}:${end}${last}`);
  region.format.font = { name: 'Arial', size: 10, color: '#172D45' };
  region.format.rowHeight = 38;
  region.format.columnWidth = 23;
  region.format.verticalAlignment = 'center';
  sh.getRange(`A${start}:${end}${start}`).values = [spec.labels];
  sh.getRange(`A${start}:${end}${start}`).format = {
    fill: '#213D59', font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' },
    wrapText: true, rowHeight: 60, horizontalAlignment: 'center', verticalAlignment: 'center',
  };
  const fields = new Map((spec.fields || []).map(f => [f.field_key, f]));
  const widths = new Map(spec.keys.map(k => [k, 23]));
  const setWidth = (range, key, width) => { range.format.columnWidth = width; widths.set(key, width); };
  const matrix = spec.rows.map(r => spec.keys.map(k => {
    const v = r[k] ?? null;
    const field = fields.get(k);
    const date = field?.type === 'date' || field?.type === 'datetime' || dateKeys.has(k) || timestampKeys.has(k) || k.endsWith('_period_start') || k.endsWith('_period_end');
    if (v && date) {
      const parsed = new Date(v);
      return Number.isFinite(parsed.getTime()) ? parsed : null;
    }
    const out = stringify(v);
    return typeof out === 'string' && /^[=+@]/.test(out) ? `'${out}` : out;
  }));
  if (matrix.length) sh.getRange(`A${start + 1}:${end}${start + matrix.length}`).values = matrix;
  spec.keys.forEach((k, i) => {
    const range = sh.getRange(`${col(i)}${start + 1}:${col(i)}${last}`);
    const field = fields.get(k);
    if (field?.type === 'date' || dateKeys.has(k) || k.endsWith('_period_start') || k.endsWith('_period_end')) range.setNumberFormat('yyyy-mm-dd');
    else if (field?.type === 'datetime' || timestampKeys.has(k)) { range.setNumberFormat('yyyy-mm-dd hh:mm:ss'); setWidth(range, k, 25); }
    else if (field?.unit === 'fraction') range.setNumberFormat('0.0%');
    else if (field?.type === 'number') range.setNumberFormat('#,##0.0;(#,##0.0);0.0');
    else if (field?.type === 'integer') range.setNumberFormat('#,##0');
    if (spec.editable && !k.endsWith('_id')) range.format.font.color = '#1655AA';
    if (booleanKeys.has(k) && spec.editable) range.dataValidation = { rule: { type: 'list', values: ['true', 'false'] } };
    if (k.includes('status') || k === 'missing_reasons') {
      range.conditionalFormats.add('containsText', {text: 'unavailable', format: {fill: '#FFF0D8', font: {color: '#854A00'}}});
    }
    if (['name', 'financial_subject', 'evidence', 'description', 'derivation', 'details', 'query_scope', 'missing_reasons', 'limitations', 'narrative'].includes(k)) setWidth(range, k, ['details', 'query_scope', 'missing_reasons', 'narrative'].includes(k) ? 100 : 44);
    if (k.startsWith('dossier_') && (k.endsWith('_evidence') || k.endsWith('_limitations') || k === 'dossier_source')) setWidth(range, k, k.endsWith('_limitations') ? 150 : 80);
    if (k.endsWith('_id') || ['post_key', 'field_key', 'reference', 'excel_label', 'unit'].includes(k)) setWidth(range, k, k === 'source_row_id' || k === 'reference' ? 70 : 42);
    range.format.wrapText = true;
    if (spec.name === 'Fields') range.format.rowHeight = 62;
    if (['Evidence', 'Collection evidence', 'Report facts'].includes(spec.name) && ['details', 'query_scope'].includes(k)) {
      spec.rows.forEach((r, j) => {
        const chars = Math.max(String(stringify(r.details) ?? '').length, String(stringify(r.query_scope) ?? '').length);
        sh.getRange(`A${start + 1 + j}:${end}${start + 1 + j}`).format.rowHeight = Math.min(spec.name === 'Evidence' ? 260 : 409, Math.max(38, 16 * Math.ceil(chars / 95)));
      });
    }
  });
  if (spec.name === 'Delivery') {
    spec.rows.forEach((r, i) => {
      const chars = Math.max(String(r.missing_reasons ?? '').length, String(r.narrative ?? '').length);
      sh.getRange(`A${start + 1 + i}:${end}${start + 1 + i}`).format.rowHeight = Math.max(38, 16 * Math.ceil(chars / 95));
    });
  }
  if (['flat-delivery', 'inputs'].includes(payload.kind)) {
    // Long peer/source text should widen its supporting column, not make every
    // headline row unnecessarily tall. Retain all text and native types.
    spec.keys.forEach((k, i) => {
      const chars = Math.max(0, ...spec.rows.map(r => typeof r[k] === 'string' ? r[k].length : 0));
      const width = Math.min(150, Math.max(widths.get(k), Math.ceil(chars / 4) + 3));
      setWidth(sh.getRange(`${col(i)}${start}:${col(i)}${last}`), k, width);
    });
    spec.rows.forEach((r, i) => {
      const lines = Math.max(1, ...spec.keys.map(k => typeof r[k] === 'string'
        ? r[k].split('\n').reduce((total, line) => total + Math.max(1, Math.ceil(line.length / Math.max(10, widths.get(k) - 3))), 0)
        : 1));
      sh.getRange(`A${start + 1 + i}:${end}${start + 1 + i}`).format.rowHeight = Math.min(409, Math.max(38, 16 * lines));
    });
  }
  sh.freezePanes.freezeRows(start);
  sh.freezePanes.freezeColumns(payload.kind === 'flat-delivery' ? 2 : spec.name === 'Delivery' ? 3 : 1);
  sh.tables.add(`A${start}:${end}${last}`, true, spec.name.replace(/[^a-zA-Z]/g, '') + 'Table');
  if (spec.name === 'Delivery') sh.tabColor = '#213D59';
}

if (payload.kind === 'delivery') {
  const spec = payload.sheets.find(s => s.name === 'Delivery');
  const sh = wb.worksheets.getItem('Delivery');
  const map = refs.get('Delivery');
  const first = starts.get('Delivery') + 1;
  const policy = payload.sheets.find(s => s.name === 'Policy');
  const policyMap = refs.get('Policy');
  const policyRef = key => {
    const i = policy.rows.findIndex(r => r.parameter === key);
    return `'Policy'!$${policyMap.get('value')}$${starts.get('Policy') + 1 + i}`;
  };
  const eligibleRows = spec.rows.flatMap((r, i) => r.fmi_status === 'available' && r.headline_selection && r.raw_fmi !== null ? [first + i] : []);
  const rawRefs = eligibleRows.map(r => `${map.get('raw_fmi')}${r}`).join(',');
  spec.rows.forEach((record, i) => {
    const row = first + i;
    const cell = key => `${map.get(key)}${row}`;
    const write = (key, formula) => sh.getRange(cell(key)).formulas = [[formula]];
    // Eligibility and joins are owned by Python. Derived eligible values remain
    // auditable Excel formulas; input-review changes require a service refresh.
    for (const c of ['ir', 'social', 'trend']) if (record[`${c}_score`] !== null) write(`${c}_contribution`, `=${cell(c + '_score')}*${cell(c + '_weight')}`);
    if (record.raw_fmi !== null) {
      write('raw_fmi', `=${cell('ir_contribution')}+${cell('social_contribution')}+${cell('trend_contribution')}`);
      write('raw_classification', `=IF(${cell('raw_fmi')}>=70,"High",IF(${cell('raw_fmi')}>=60,"Medium",IF(${cell('raw_fmi')}>=40,"Neutral","Low")))`);
    }
    if (eligibleRows.includes(row)) {
      write('cohort_min', `=MIN(${rawRefs})`);
      write('cohort_max', `=MAX(${rawRefs})`);
      write('display_fmi', `=ROUND(IF(${cell('cohort_min')}=${cell('cohort_max')},${policyRef('display_equal')},${policyRef('display_lower')}+(${policyRef('display_upper')}-${policyRef('display_lower')})*(${cell('raw_fmi')}-${cell('cohort_min')})/(${cell('cohort_max')}-${cell('cohort_min')})),1)`);
      write('uplift_fraction', `=${policyRef('uplift_max')}*(EXP(${policyRef('uplift_exponent')}*${cell('display_fmi')}/100)-1)/(EXP(${policyRef('uplift_exponent')})-1)`);
      if (record.legacy_uplift_fraction !== null && map.has('legacy_uplift_fraction')) {
        write('legacy_uplift_fraction', `=IF(${cell('raw_fmi')}<=${policyRef('legacy_uplift_threshold')},0,${policyRef('legacy_uplift_intercept')}+(${cell('raw_fmi')}-${policyRef('legacy_uplift_threshold')})*${policyRef('legacy_uplift_per_score')})`);
      }
    }
    if (record.adjusted_forecast !== null) {
      write('adjustment', `=${cell('baseline_revenue')}*${cell('uplift_fraction')}`);
      write('adjusted_forecast', `=${cell('baseline_revenue')}+${cell('adjustment')}`);
      if (record.legacy_adjusted_forecast !== null && map.has('legacy_adjusted_forecast')) {
        write('legacy_adjustment', `=${cell('baseline_revenue')}*${cell('legacy_uplift_fraction')}`);
        write('legacy_adjusted_forecast', `=${cell('baseline_revenue')}+${cell('legacy_adjustment')}`);
      }
    }
    for (const kind of ['baseline', 'adjusted']) if (record[`${kind}_forecast_yoy`] !== null) write(`${kind}_forecast_yoy`, `=${cell(kind === 'baseline' ? 'baseline_revenue' : 'adjusted_forecast')}/${cell('prior_year_actual')}-1`);
    if (record.legacy_adjusted_forecast_yoy !== null && map.has('legacy_adjusted_forecast_yoy')) write('legacy_adjusted_forecast_yoy', `=${cell('legacy_adjusted_forecast')}/${cell('prior_year_actual')}-1`);
  });
}

wb.recalculate();
const errors = await wb.inspect({kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: {useRegex: true, maxResults: 20}, maxChars: 2500});
if (/"(?:value|text)":"#/.test(errors.ndjson)) throw new Error(errors.ndjson);
console.log(errors.ndjson);
console.log((await wb.inspect({kind: 'table', range: `${payload.sheets[0].name}!A${starts.get(payload.sheets[0].name)}:L${starts.get(payload.sheets[0].name) + 3}`, include: 'values,formulas', tableMaxRows: 4, tableMaxCols: 12, maxChars: 1800})).ndjson);
if (previewFlag === 'true') {
  const directory = path.join(path.dirname(destination), '.previews', path.basename(destination, '.xlsx'));
  await fs.mkdir(directory, {recursive: true});
  for (const spec of payload.sheets) {
    const start = starts.get(spec.name);
    const blob = await wb.render({sheetName: spec.name, range: `A1:${col(Math.min(spec.keys.length, 7) - 1)}${Math.min(start + spec.rows.length, 10)}`, scale: 1.5, format: 'png'});
    await fs.writeFile(path.join(directory, `${spec.name}.png`), new Uint8Array(await blob.arrayBuffer()));
    if (spec.name === 'Dossier reference') {
      const columns = refs.get(spec.name);
      for (const [label, first, last] of [
        ['IR comparison', 'dossier_ir_score', 'comparison_ir_fmi_impact'],
        ['Social comparison', 'dossier_social_score', 'comparison_social_fmi_impact'],
        ['Trend comparison', 'dossier_trend_score', 'comparison_trend_fmi_impact'],
        ['new scenario', 'dossier_scenario_display_fmi', 'dossier_scenario_legacy_uplift_fraction'],
        ['forecast amounts', 'dossier_scenario_adjustment', 'dossier_scenario_legacy_adjusted_forecast'],
        ['method evidence', 'dossier_headline_evidence', 'dossier_period_evidence'],
      ]) {
        if (!columns.has(first) || !columns.has(last)) continue;
        const detail = await wb.render({sheetName: spec.name, range: `${columns.get(first)}1:${columns.get(last)}7`, scale: 1.5, format: 'png'});
        await fs.writeFile(path.join(directory, `${spec.name} ${label}.png`), new Uint8Array(await detail.arrayBuffer()));
      }
    }
  }
  const delivery = payload.sheets.find(s => s.name === 'Delivery');
  if (delivery) {
    const columns = refs.get('Delivery');
    const start = starts.get('Delivery');
    const key = 'missing_reasons';
    const blob = await wb.render({sheetName: 'Delivery', range: `${columns.get(key)}${start}:${columns.get(key)}${start + 2}`, scale: 1.5, format: 'png'});
    await fs.writeFile(path.join(directory, 'Delivery quality.png'), new Uint8Array(await blob.arrayBuffer()));
    if (payload.kind === 'flat-delivery') {
      for (const [label, first, last] of [
        ['uplift', 'uplift_fraction', 'legacy_adjusted_forecast'],
        ['native forecast', 'baseline_period_label', 'baseline_period_end'],
        ['score drivers', 'ir_score', 'trend_score'],
        ['revenue growth', 'earlier_growth', 'latest_growth'],
        ['forecast context', 'observed_target_forecast_candidate_count', 'observed_target_forecast_date'],
        ['revenue context', 'observed_revenue_amount', 'observed_revenue_currency'],
        ['social context', 'observed_social_month', 'observed_social_total_posts'],
        ['likes context', 'observed_social_median_likes', 'observed_social_likes_change'],
      ]) {
        const blob = await wb.render({sheetName: 'Delivery', range: `${columns.get(first)}1:${columns.get(last)}7`, scale: 1.5, format: 'png'});
        await fs.writeFile(path.join(directory, `Delivery ${label}.png`), new Uint8Array(await blob.arrayBuffer()));
      }
    }
  }
}
const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(destination);
