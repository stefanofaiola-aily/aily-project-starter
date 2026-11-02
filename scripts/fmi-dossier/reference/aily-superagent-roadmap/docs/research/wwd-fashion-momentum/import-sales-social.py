#!/usr/bin/env python3
"""Import only the agreed Sales & Social fields; never change scoring inputs."""
import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import posixpath
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL_ID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
COLUMNS = [
    {'field': 'smFeb2024', 'label': 'SM Feb ’24', 'type': 'percent'},
    {'field': 'q4VsBaseline2024', 'label': 'Q4 vs Baseline ’24 (%)', 'type': 'percent'},
    {'field': 'smFeb2025', 'label': 'SM Feb ’25', 'type': 'percent'},
    {'field': 'q4VsBaseline2025', 'label': 'Q4 vs Baseline ’25 (%)', 'type': 'percent'},
    {'field': 'smFeb2026', 'label': 'SM Feb ’26', 'type': 'percent'},
    {'field': 'q4VsBaseline2026', 'label': 'Q4 vs Baseline ’26 (%)', 'type': 'percent',
     'qualification': 'Source forecast derived from the uploaded workbook’s FMI, not observed sales'},
    {'field': 'insightsDescriptive', 'label': 'Insights Descriptive', 'type': 'text'},
    {'field': 'insightsStatistics', 'label': 'Insights Statistics', 'type': 'text'},
]

YOY_V2_COLUMNS = [
    {'field': 'q4VsBaseline2024YoyV2', 'label': 'Q4 vs Baseline ’24 (%) YoY v2', 'type': 'percent',
     'qualification': 'Q4 2024 sales versus Q4 2023 sales'},
    {'field': 'q4VsBaseline2025YoyV2', 'label': 'Q4 vs Baseline ’25 (%) YoY v2', 'type': 'percent',
     'qualification': 'Q4 2025 sales versus Q4 2024 sales'},
    {'field': 'q4VsBaseline2026YoyV2', 'label': 'Q4 vs Baseline ’26 (%) YoY v2', 'type': 'percent',
     'qualification': 'Source Q4 2026 projection versus Q4 2025 sales; unavailable results stay blank'},
]


def read_sheet(path, sheet_name):
    """Read cached values and formula provenance without executing source formulas."""
    with zipfile.ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(si.itertext()) for si in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        book = ET.fromstring(archive.read('xl/workbook.xml'))
        matches = [s for s in book.find('s:sheets', NS) if s.get('name') == sheet_name]
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one tab named {sheet_name!r}')
        rels = {r.get('Id'): r.get('Target') for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        target = rels[matches[0].get(REL_ID)]
        member = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
        rows = {}
        for row in ET.fromstring(archive.read(member)).findall('s:sheetData/s:row', NS):
            cells = {}
            for cell in row.findall('s:c', NS):
                address = cell.get('r')
                column = ''.join(c for c in address if c.isalpha())
                text = cell.find('s:v', NS)
                kind = cell.get('t')
                if kind == 'inlineStr':
                    value = ''.join(cell.find('s:is', NS).itertext())
                elif kind == 'str' and text is not None and text.text is None:
                    value = ''  # Explicit cached empty-string formula result, not a missing cache.
                elif text is None or text.text is None:
                    value = None
                elif kind == 's':
                    value = strings[int(text.text)]
                elif kind in ('str', 'e'):
                    value = text.text
                elif kind == 'b':
                    value = bool(int(text.text))
                else:
                    value = float(text.text)
                formula = cell.find('s:f', NS)
                cells[column] = {'address': address, 'value': value, 'kind': kind,
                                 'formula': '=' + formula.text if formula is not None and formula.text else None}
            rows[int(row.get('r'))] = cells
        return rows


def qualification_signals(notes, scope):
    """Record recognized source qualifications; later imports cannot silently drop them."""
    if scope == 'yoy-v2':
        return {
            'unavailable2026Conflict': any('Sales Q4 2026 vacío' in note for note in notes),
            'belmontTinyDenominator': any(note.startswith('Belmont Park Village:') and '0,25' in note for note in notes),
        }
    return {'mixedAnnualSocialPeriods': any('annual median captured likes YoY' in note for note in notes)}


def check_qualification_continuity(notes, scope, previous_snapshot):
    current = qualification_signals(notes, scope)
    if previous_snapshot:
        source = previous_snapshot['source']
        previous = source.get('qualificationSignals', qualification_signals(source.get('notes', []), scope))
        dropped = [name for name, active in previous.items() if active and not current.get(name)]
        if dropped:
            raise ValueError(f'Source qualifications changed or removed: {", ".join(dropped)}. Review the source notes and accepted qualification definitions before reimporting.')
    return current


def require_qualified_brands(expected, records):
    """Reject missing or renamed brands referenced by the recognized source profile."""
    names = {value.strip().casefold().replace('’', "'")
             for record in records for value in (record['sourceBrand'], record['prospect']) if value}
    missing = sorted(name for name in expected if name.strip().casefold().replace('’', "'") not in names)
    if missing:
        raise ValueError(f'Qualified source brands missing or renamed: {", ".join(missing)}. Review identity and qualification mappings before reimporting.')


def extract(path, delivery_rows, sheet_name='Sales & Social', received_date=None, scope='sales-social', previous_snapshot=None):
    if scope not in ('sales-social', 'yoy-v2'):
        raise ValueError(f'Unknown import scope: {scope}')
    columns = YOY_V2_COLUMNS if scope == 'yoy-v2' else COLUMNS
    rows = read_sheet(path, sheet_name)
    headers = {}
    for column, cell in rows.get(1, {}).items():
        value = cell['value']
        if value is not None:
            if value in headers:
                raise ValueError(f'Duplicate source header: {value}')
            headers[value] = column
    required = ['Brand'] + [c['label'] for c in columns]
    missing = [label for label in required if label not in headers]
    if missing:
        raise ValueError(f'Missing required headers: {missing}')
    names = {r['prospect'].strip().casefold(): r['prospect'] for r in delivery_rows}
    if len(names) != len(delivery_rows):
        raise ValueError('Delivery identities must be unique')
    records, seen = [], set()
    last_data_row = 1
    for number in range(2, max(rows) + 1):
        cells = rows.get(number, {})
        brand = cells.get(headers['Brand'], {}).get('value')
        if brand in (None, ''):
            break
        if not isinstance(brand, str):
            raise ValueError(f'Row {number}: Brand must be text')
        key = brand.strip().casefold()
        if key in seen:
            raise ValueError(f'Duplicate source brand: {brand}')
        seen.add(key)
        values, raw, references, formulas = {}, {}, {}, {}
        for spec in columns:
            cell = cells.get(headers[spec['label']], {})
            value = cell.get('value')
            if cell.get('kind') == 'e':
                raise ValueError(f'{cell["address"]}: source formula error {value}')
            if cell.get('formula') and value is None:
                raise ValueError(f'{cell["address"]}: missing formula cache; recalculate and save the source workbook')
            raw[spec['field']] = value
            if value in (None, '', 'N/D'):
                value = None
            elif spec['type'] == 'percent':
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f'Row {number}, {spec["label"]}: expected a numeric percentage fraction or N/D')
            elif not isinstance(value, str):
                raise ValueError(f'Row {number}, {spec["label"]}: expected text')
            values[spec['field']] = value
            references[spec['field']] = cell.get('address', f'{headers[spec["label"]]}{number}')
            if cell.get('formula'):
                formulas[spec['field']] = cell['formula']
        records.append({'sourceBrand': brand, 'prospect': names.get(key), 'sourceRow': number,
                        'matchStatus': 'Matched' if key in names else 'Not in delivery',
                        'values': values, 'rawValues': raw, 'cellReferences': references,
                        'sourceFormulas': formulas})
        last_data_row = number
    if not records:
        raise ValueError('No brand rows found')
    notes = [row['A']['value'] for number, row in rows.items()
             if number > last_data_row and isinstance(row.get('A', {}).get('value'), str)]
    signals = check_qualification_continuity(notes, scope, previous_snapshot)
    if scope == 'yoy-v2':
        revised_group = {'J.Crew', 'Christian Louboutin', 'PacSun', 'Jacquemus', 'Lafayette 148',
                         'Exemplar Luxury Group', 'Macys', 'Belmont Park Village', 'Aman',
                         'David Yurman', 'Target', 'Caleres', 'LAGOS'}
        source_flags_empty_2026 = signals['unavailable2026Conflict']
        source_flags_belmont = signals['belmontTinyDenominator']
        if source_flags_empty_2026:
            require_qualified_brands(revised_group, records)
        if source_flags_belmont:
            require_qualified_brands({'Belmont Park Village'}, records)
        for record in records:
            qualifications = []
            if record['sourceBrand'] == 'Belmont Park Village' and source_flags_belmont:
                qualifications.append('Source flags Q4 2023 revenue of USD 0.25 (0.00000025m); review the tiny denominator before analysis.')
            if record['sourceBrand'] in revised_group and source_flags_empty_2026 and record['values']['q4VsBaseline2026YoyV2'] is not None:
                qualifications.append('The closing source note says Q4 2026 is unavailable for this group, but a cached projection ratio is present; review.')
            record['reviewNotes'] = qualifications
        return {
            'source': {'fileName': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                       'sheet': sheet_name, 'receivedDate': received_date or date.today().isoformat(),
                       'notes': notes, 'qualificationSignals': signals, 'importScope': 'Three YoY v2 columns from Sales & Social only',
                       'valuesBasis': 'Cached source snapshot; source formulas retained as provenance only'},
            'columns': columns,
            'definitions': {
                'comparison2024': 'Q4 2024 sales / Q4 2023 sales − 1. The supplied header says vs Baseline, but the source formula compares prior-year sales.',
                'comparison2025': 'Q4 2025 sales / Q4 2024 sales − 1; year-over-year sales growth, separate from the existing actual-versus-baseline column.',
                'comparison2026': 'Source Q4 2026 projection / Q4 2025 sales − 1. This is a forecast comparison; available cached values are imported as provided, with missing results left blank.',
                'periods': 'Retain source period qualifications: calendar Q4 by default; the updated source explicitly uses fiscal Q4 for Macys, Target and Caleres. No exact dates are inferred.',
                'missing': 'N/D, empty source cells and explicit cached empty-string formula results become null/blank. Numeric zero stays zero; an absent formula cache fails the import.',
                'scope': 'Only the three YoY v2 fields are imported. Existing baseline/social/insight columns retain their previous snapshot; source FMI is not imported and these fields do not affect scoring or rankings.',
                'qualifications': 'Belmont’s tiny 2023 denominator is flagged by the source. For some revised companies, numeric cached 2026 projections conflict with the closing note saying 2026 sales are unavailable; row-level review notes retain this conflict.',
            },
            'usedForScoring': False, 'records': records,
        }
    actual_light_periods = any(note.startswith('Q4 ’24/’25 usa registros Actual de Light.') for note in notes)
    expanded_periods = signals['mixedAnnualSocialPeriods']
    if expanded_periods:
        annual_brands = {
            'J.Crew', 'Christian Louboutin', 'PacSun', 'Jacquemus', 'Lafayette 148',
            'Exemplar Luxury Group', 'Macys', 'Belmont Park Village', 'Aman',
            'David Yurman', 'Target', 'Caleres', 'LAGOS', 'GAP Inc', 'Coach',
            "Victoria's Secret & Co.", 'DKNY', 'Calvin Klein', "Kohl's",
            'Ulta Beauty', 'Tommy Hilfiger', 'G-III Apparel Group',
        }
        fiscal_brands = {'Macys', 'Target', 'Caleres', 'GAP Inc',
                         "Victoria's Secret & Co.", "Kohl's", 'Ulta Beauty', 'G-III Apparel Group'}
        parent_only = {'Coach', 'DKNY', 'Calvin Klein', 'Tommy Hilfiger'}
        require_qualified_brands(annual_brands | fiscal_brands | parent_only | {'Ralph Lauren'}, records)
        for record in records:
            brand, values = record['prospect'] or record['sourceBrand'], record['values']
            review = []
            if brand in annual_brands:
                review.append('Source SM columns use annual median captured likes YoY over common months, superseding the show-week definition; Feb headers are retained.')
            if brand == 'Ralph Lauren':
                review.append('Source narrative describes annual social figures for 2024/2025 and a show-week measure for 2026; these windows are not directly comparable.')
            if brand in fiscal_brands:
                review.append('Source uses fiscal Q4 ending January/early February of the following year, not calendar October–December; exact dates are not inferred.')
            if brand in parent_only:
                review.append('Source has parent-group revenue only; standalone-brand sales are left unfilled.')
            if brand == 'G-III Apparel Group':
                review.append('Source year mapping: 2024 = FY2025, 2025 = FY2026, 2026 = FY2027.')
            if brand in {'GAP Inc', "Victoria's Secret & Co."}:
                review.append('Source social measures the brand account, not consolidated group activity.')
            if brand in {'PacSun', 'Jacquemus', 'DKNY', 'Ulta Beauty'}:
                review.append('Source flags sparse social samples: PacSun 2024/2025, Jacquemus 2024, DKNY 2025/2026, Ulta 2024. Supplied values remain descriptive context, unused for scoring.')
            if values['insightsDescriptive'] is not None or values['insightsStatistics'] is not None:
                review.append('Source notes say narrative/social copy was not recalculated from the new actuals/baselines; verify claims against current cells before display.')
            if values['q4VsBaseline2026'] is not None:
                review.append('2026 is an FMI-derived source projection, not actual sales; source notes saying no actuals do not make this observed revenue.')
            record['reviewNotes'] = review
    sales_definition = (
        'Q4 sales divided by the source-provided same-year baseline minus 1. Source labels include Light Actual and WWD Actual; they are not independent disclosure verification. '
        'Calendar/fiscal periods and source scope vary by row; source notes and row qualifications identify fiscal Q4 proxies, parent-only gaps and G-III year mappings. Historical forecasts have no version timestamp, so differences do not establish ex-ante accuracy.'
        if expanded_periods else
        'Q4 sales divided by the source-provided same-year sales baseline minus 1. '
        'The source labels Q4 ’24/’25 as Light Actual records; this does not establish official publication. '
        'Burberry and Ralph Lauren use fiscal Q4 ending in March; Q4 ’26 is a calendar-year forecast. '
        'Moncler/TOM FORD differences are referenced in the source’s Fuentes tab, which is not imported.'
        if actual_light_periods else
        'Q4 sales divided by the source-provided same-year sales baseline minus 1. Ralph Lauren Q4 is fiscal and ends in March; Moncler and TOM FORD Fashion use October–December.'
    )
    return {
        'source': {'fileName': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'sheet': sheet_name, 'receivedDate': received_date or date.today().isoformat(),
                   'notes': notes, 'qualificationSignals': signals, 'importScope': 'Eight requested columns from Sales & Social only',
                   'valuesBasis': 'Cached source snapshot; source formulas retained as provenance only'},
        'columns': COLUMNS,
        'definitions': {
            'social': ('Mixed source social windows: show-week versus combined ±30-day baseline for show rows; annual median captured likes YoY over common months for the source-identified annual rows. Source Feb labels are retained. For the nine latest annual additions, both 2026 and its comparator end 28 October. See row qualifications/source notes; likes are accumulated snapshots.'
                       if expanded_periods else 'Median-likes change for collection posts: show day through day +7 versus the combined day −30 to −1 and day +8 to +37 baseline. Source Feb labels also include March shows in the same year; likes are accumulated snapshots.'),
            'sales': sales_definition,
            'forecast2026': 'Q4 ’26 is a forecast computed in the uploaded workbook from its own FMI. Imported as a source snapshot; not recomputed from the delivery index and not observed revenue.' + (' The updated source specifies calendar-year Q4.' if actual_light_periods else ''),
            'missing': 'N/D and empty source cells become null/blank. Raw markers are retained; a numeric zero remains zero.',
            'insights': ('Import supplied descriptive/statistical insights verbatim; blank source cells stay blank and superseded text remains in history. The source says narrative/social copy was not recalculated with the new actuals/baselines; it may conflict with current numeric cells. Existing core/component insights are separate.'
                         if expanded_periods else 'Import the supplied descriptive/statistical insights verbatim; blank source insights stay blank. Existing core/component insights are separate.'),
        },
        'usedForScoring': False, 'records': records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    parser.add_argument('--inputs', type=Path, default=ROOT / 'weighted-delivery-inputs.json')
    parser.add_argument('--sheet', default='Sales & Social')
    parser.add_argument('--scope', choices=('sales-social', 'yoy-v2'), default='sales-social',
                        help='Refresh only the requested field group; the other snapshot remains unchanged')
    parser.add_argument('--received-date', default=date.today().isoformat())
    args = parser.parse_args()
    date.fromisoformat(args.received_date)
    delivery = json.loads((args.inputs.parent / 'weighted-delivery.json').read_text())
    inputs = json.loads(args.inputs.read_text())
    key = 'salesYoyV2Supplement' if args.scope == 'yoy-v2' else 'salesSocialSupplement'
    previous = inputs.get(key)
    supplement = extract(args.workbook, delivery['deliveryRows'], args.sheet, args.received_date,
                         args.scope, previous_snapshot=previous)
    if previous and previous['source']['sha256'] != supplement['source']['sha256']:
        inputs.setdefault(key + 'History', []).append(previous)
    inputs[key] = supplement
    args.inputs.write_text(json.dumps(inputs, indent=2, ensure_ascii=False) + '\n')
    matched = [r['prospect'] for r in supplement['records'] if r['prospect']]
    unmatched = [r['sourceBrand'] for r in supplement['records'] if not r['prospect']]
    print(json.dumps({'matched': matched, 'unmatched': unmatched,
                      'scoringChanged': False, 'next': 'Run refresh-delivery.py to regenerate outputs'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
