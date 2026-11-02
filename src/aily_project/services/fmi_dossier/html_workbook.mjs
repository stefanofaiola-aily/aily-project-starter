import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const [source, destination, previewFlag] = process.argv.slice(2);
const spec = JSON.parse(await fs.readFile(source, 'utf8')).sheets[0];
const wb = Workbook.create();
const sh = wb.worksheets.add('Delivery');
const column = index => {
  let label = '';
  for (index++; index; index = Math.floor((index - 1) / 26)) label = String.fromCharCode(65 + (index - 1) % 26) + label;
  return label;
};
const last = spec.rows.length + 1;
const end = column(spec.keys.length - 1);
const safeText = value => typeof value === 'string' && /^[=+@]/.test(value) ? `'${value}` : value;
sh.showGridLines = false;
sh.tabColor = '#213D59';
const data = sh.getRange(`A1:${end}${last}`);
data.format.font = {name: 'Arial', size: 10, color: '#172D45'};
data.format.verticalAlignment = 'top';
data.format.wrapText = true;
data.format.columnWidth = 24;
sh.getRange(`A1:${end}1`).values = [spec.labels];
sh.getRange(`A1:${end}1`).format = {
  fill: '#213D59', font: {name: 'Arial', size: 10, bold: true, color: '#FFFFFF'},
  horizontalAlignment: 'center', verticalAlignment: 'center', rowHeight: 76, wrapText: true
};
if (spec.rows.length) sh.getRange(`A2:${end}${last}`).values = spec.rows.map(row => spec.keys.map(key => safeText(row[key] ?? null)));
const widths = new Map();
for (const [index, key] of spec.keys.entries()) {
  const field = spec.fields[index];
  const width = /methodology|source$/.test(key) ? 120 : /insight|basis/.test(key) ? 80 : key === 'name' ? 38 : 26;
  widths.set(key, width);
  const cells = sh.getRange(`${column(index)}2:${column(index)}${last}`);
  sh.getRange(`${column(index)}1:${column(index)}${last}`).format.columnWidth = width;
  if (field.unit === 'fraction') cells.setNumberFormat('0.00%');
  else if (field.unit === 'pp') cells.setNumberFormat('0.00" pp"');
  else if (field.unit === 'count' || key === 'baseline_unit_multiplier') cells.setNumberFormat('#,##0');
  else if (field.type === 'number') cells.setNumberFormat('0.0####');
  if (field.type === 'number') cells.format.horizontalAlignment = 'right';
}
for (const [index, row] of spec.rows.entries()) {
  const lines = Math.max(1, ...spec.keys.map(key => {
    const value = row[key];
    return typeof value === 'string' ? value.split('\n').reduce((sum, text) => sum + Math.max(1, Math.ceil(text.length / (widths.get(key) - 4))), 0) : 1;
  }));
  sh.getRange(`A${index + 2}:${end}${index + 2}`).format.rowHeight = Math.min(409, Math.max(42, lines * 15));
}
sh.tables.add(`A1:${end}${last}`, true, 'HtmlDelivery').style = 'TableStyleLight9';
sh.freezePanes.freezeRows(1);
sh.freezePanes.freezeColumns(1);
wb.recalculate();
const errors = await wb.inspect({kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!', options: {useRegex: true, maxResults: 20}, maxChars: 3000});
if (errors.ndjson.includes('"kind":"cell"')) throw new Error(`Workbook errors: ${errors.ndjson}`);
console.log('Formula error scan:', errors.ndjson);
if (previewFlag === 'true') {
  const fendiIndex = spec.rows.findIndex(row => row.name === 'Fendi');
  const row = fendiIndex >= 0 ? fendiIndex + 2 : 2;
  // Separate bounded views stay legible at normal zoom instead of shrinking
  // every column into one very wide image. Only one workbook is exported.
  for (const [name, range] of [
    ['scores', 'A1:J3'],
    ['history', `AB${row}:AG${row}`],
    ['projection', `AH${row}:AI${row}`],
    ['forecast', `AJ${row}:AQ${row}`],
    ['methodology', `AT${row}:AX${row}`]
  ]) {
    const preview = await wb.render({sheetName: 'Delivery', range, scale: 1, format: 'png'});
    await fs.writeFile(path.join(path.dirname(destination), `html-${name}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
}
const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(destination);
console.log(`Exported ${spec.rows.length} rows, ${spec.keys.length} columns, one Delivery sheet.`);
