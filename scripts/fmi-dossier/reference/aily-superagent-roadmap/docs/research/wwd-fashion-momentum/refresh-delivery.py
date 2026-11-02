#!/usr/bin/env python3
"""Rebuild and check the versioned weighted delivery using the Codex artifact runtime."""
import argparse
import hashlib
import json
import math
import os
import posixpath
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
SOURCES = (
    'weighted-delivery-inputs.json', 'prospect-inputs.json', 'prospect-packages.json',
    'arceo-enablement-inputs.json', 'build-weighted-delivery.py',
    'build-weighted-workbook.mjs', 'refresh-delivery.py', 'import-sales-social.py',
)
OUTPUTS = ('weighted-delivery.json', 'weighted-delivery.md', 'weighted-delivery.xlsx')
MANIFEST = 'delivery-build.json'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
FIELDS = (
    'prospect', 'coreInsight', 'overallScore', 'overallSentiment', 'momentumScore',
    'momentumSentiment', 'socialScore', 'socialSentiment', 'strengthScore',
    'strengthSentiment', 'emailDomains', 'companyCodes', 'momentumDescriptor',
    'momentumInsight', 'socialDescriptor', 'socialInsight', 'strengthDescriptor',
    'strengthInsight', 'normalizedFashionMomentumIndex', 'momentumKpiValue',
    'momentumKpiLabel', 'socialKpiValue', 'socialKpiLabel', 'strengthKpiValue',
    'strengthKpiLabel', 'leaderboardCategory', 'leaderboardRank',
    'smFeb2024', 'q4VsBaseline2024', 'smFeb2025', 'q4VsBaseline2025',
    'smFeb2026', 'q4VsBaseline2026', 'insightsDescriptive', 'insightsStatistics',
    'q4VsBaseline2024YoyV2', 'q4VsBaseline2025YoyV2', 'q4VsBaseline2026YoyV2',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def excel_column(number):
    letters = ''
    while number:
        number, digit = divmod(number - 1, 26)
        letters = chr(65 + digit) + letters
    return letters


def validate_workbook(folder):
    """Check exported caches, blanks, live score formulas and native delivery table."""
    data = json.loads((folder / OUTPUTS[0]).read_text())
    with zipfile.ZipFile(folder / OUTPUTS[2]) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(si.itertext()) for si in ET.fromstring(
                archive.read('xl/sharedStrings.xml'))]
        book = ET.fromstring(archive.read('xl/workbook.xml'))
        sheets = book.find('s:sheets', NS)
        revision_records = [r for r in data['records'] if r.get('scoreRevision')]
        display_override_records = [r for r in data['records'] if r.get('normalizedDisplayOverride')]
        expected_sheets = ['Delivery', 'Details', 'Cycles', 'Peers', 'Campaigns', 'Method',
                           'Enablement', 'Brand social', 'Revenue proxies']
        if revision_records or display_override_records:
            expected_sheets.append('Score revisions')
        if data.get('salesSocialSupplement'):
            expected_sheets.append('Sales and social')
        if data.get('salesYoyV2Supplement'):
            expected_sheets.append('YoY v2')
        require([s.attrib['name'] for s in sheets] == expected_sheets, 'Unexpected workbook sheets')
        rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        rel_targets = {r.attrib['Id']: r.attrib['Target'] for r in rels}
        relationship_id = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
        target = rel_targets[sheets[0].attrib[relationship_id]]
        delivery_path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        sheet = ET.fromstring(archive.read(delivery_path))
        cells = {c.attrib['r']: c for c in sheet.findall('.//s:sheetData/s:row/s:c', NS)}
        for name in archive.namelist():
            if name.startswith('xl/worksheets/sheet') and name.endswith('.xml'):
                xml = ET.fromstring(archive.read(name))
                errors = [c.attrib['r'] for c in xml.findall('.//s:c', NS) if c.get('t') == 'e']
                require(not errors, f'Formula errors in {name}: {errors}')

        def value(cell):
            if cell is None:
                return None
            v = cell.find('s:v', NS)
            if cell.get('t') == 'inlineStr':
                return ''.join(cell.find('s:is', NS).itertext())
            if v is None or v.text is None:
                return None
            if cell.get('t') == 's':
                return strings[int(v.text)]
            if cell.get('t') in ('str', 'e'):
                return v.text
            return float(v.text)

        # Table XML column names must match their worksheet header cells (Excel repair risk).
        for workbook_sheet in sheets:
            target = rel_targets[workbook_sheet.attrib[relationship_id]]
            sheet_path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            xml = ET.fromstring(archive.read(sheet_path))
            parts = xml.find('s:tableParts', NS)
            if parts is None:
                continue
            directory, filename = posixpath.split(sheet_path)
            relationships = ET.fromstring(archive.read(f'{directory}/_rels/{filename}.rels'))
            table_targets = {r.attrib['Id']: r.attrib['Target'] for r in relationships}
            sheet_cells = {c.attrib['r']: c for c in xml.findall('.//s:sheetData/s:row/s:c', NS)}
            for part in parts:
                target = table_targets[part.attrib[relationship_id]]
                table_path = target.lstrip('/') if target.startswith('/') else posixpath.normpath(f'{directory}/{target}')
                table_xml = ET.fromstring(archive.read(table_path))
                first_cell = table_xml.attrib['ref'].split(':')[0]
                first_letters = ''.join(c for c in first_cell if c.isalpha())
                row_number = ''.join(c for c in first_cell if c.isdigit())
                column_number = 0
                for letter in first_letters:
                    column_number = column_number * 26 + ord(letter) - 64
                for offset, column in enumerate(table_xml.find('s:tableColumns', NS)):
                    number, letters = column_number + offset, ''
                    while number:
                        number, digit = divmod(number - 1, 26)
                        letters = chr(65 + digit) + letters
                    address = letters + row_number
                    require(value(sheet_cells.get(address)) == column.attrib['name'],
                            f'{workbook_sheet.attrib["name"]}!{address}: table/header mismatch')

        if revision_records:
            revision_sheet = next(s for s in sheets if s.attrib['name'] == 'Score revisions')
            target = rel_targets[revision_sheet.attrib[relationship_id]]
            revision_path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            xml = ET.fromstring(archive.read(revision_path))
            revision_cells = {c.attrib['r']: c for c in xml.findall('.//s:sheetData/s:row/s:c', NS)}
            for number, record in enumerate(revision_records, 7):
                revision = record['scoreRevision']
                expected = {
                    'A': record['prospectName'], 'B': revision['overallScore'], 'C': revision['overallSentiment'],
                    'D': record['page1']['normalizedFashionMomentumIndex'] if revision.get('normalizationPolicy') == 'cohort-min-max' else revision['normalizedFashionMomentumIndex'],
                    'E': revision['components']['momentum']['score'], 'F': revision['components']['momentum']['sentiment'],
                    'G': revision['components']['momentum']['descriptor'],
                    'H': revision['components']['social']['score'], 'I': revision['components']['social']['sentiment'],
                    'J': revision['components']['social']['descriptor'],
                    'K': revision['components']['strength']['score'], 'L': revision['components']['strength']['sentiment'],
                    'M': revision['components']['strength']['descriptor'],
                    'N': revision['authority'], 'O': revision['receivedDate'],
                    'P': 'Supplied' if revision['supportingDataSupplied'] else 'Not supplied',
                    'Q': record['selectedCycleKey'],
                    'R': revision['reconciliation']['componentWeightedOverall'],
                    'S': revision['reconciliation']['suppliedOverallMinusWeighted'],
                    'T': revision['reconciliation']['standardNormalizedIndexForSuppliedOverall'],
                    'U': revision['reconciliation']['standardComponentSentiments']['momentum'],
                    'V': revision['revisionId'],
                }
                for column, expected_value in expected.items():
                    address = f'{column}{number}'
                    actual = value(revision_cells.get(address))
                    if isinstance(expected_value, (int, float)):
                        require(isinstance(actual, (int, float)) and math.isclose(actual, expected_value, abs_tol=1e-9),
                                f'Score revisions!{address}: numeric revision differs from JSON')
                    else:
                        require(actual == expected_value, f'Score revisions!{address}: revision metadata differs from JSON')

        if display_override_records:
            revision_sheet = next(s for s in sheets if s.attrib['name'] == 'Score revisions')
            target = rel_targets[revision_sheet.attrib[relationship_id]]
            revision_path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            xml = ET.fromstring(archive.read(revision_path))
            override_cells = {c.attrib['r']: c for c in xml.findall('.//s:sheetData/s:row/s:c', NS)}
            for number, record in enumerate(display_override_records, 12 + len(revision_records)):
                override = record['normalizedDisplayOverride']
                expected_values = {
                    'A': record['prospectName'], 'B': override['value'],
                    'C': override['standardNormalizedIndex'], 'D': override['suppliedMinusStandard'],
                    'N': override['authority'], 'O': override['receivedDate'],
                    'P': 'Supplied' if override['supportingDataSupplied'] else 'Not supplied',
                }
                for column, expected in expected_values.items():
                    actual = value(override_cells.get(f'{column}{number}'))
                    if isinstance(expected, (int, float)):
                        require(isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=1e-9),
                                f'Normalized display override {column}{number}: numeric value differs from JSON')
                    else:
                        require(actual == expected, f'Normalized display override {column}{number}: metadata differs from JSON')
                for column in ('C', 'D'):
                    require(override_cells[f'{column}{number}'].find('s:f', NS) is not None,
                            f'Normalized display override {column}{number}: missing reconciliation formula')

        supplement = data.get('salesSocialSupplement')
        if supplement:
            source_sheet = next(s for s in sheets if s.attrib['name'] == 'Sales and social')
            target = rel_targets[source_sheet.attrib[relationship_id]]
            source_path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            source_xml = ET.fromstring(archive.read(source_path))
            source_cells = {c.attrib['r']: c for c in source_xml.findall('.//s:sheetData/s:row/s:c', NS)}
            for number, record in enumerate(supplement['records'], 7):
                expected = [record['sourceBrand'], record['prospect'],
                            *(record['values'][c['field']] for c in supplement['columns']),
                            record['sourceRow'], record['matchStatus']]
                for index, expected_value in enumerate(expected, 1):
                    address = f'{excel_column(index)}{number}'
                    actual = value(source_cells.get(address))
                    if expected_value in (None, ''):
                        require(actual in (None, ''), f'Sales and social!{address}: must remain blank')
                    elif isinstance(expected_value, (int, float)):
                        require(isinstance(actual, (int, float)) and math.isclose(actual, expected_value, abs_tol=1e-9),
                                f'Sales and social!{address}: source value differs from JSON')
                    else:
                        require(actual == expected_value, f'Sales and social!{address}: metadata differs from JSON')

        yoy_v2 = data.get('salesYoyV2Supplement')
        if yoy_v2:
            source_sheet = next(s for s in sheets if s.attrib['name'] == 'YoY v2')
            target = rel_targets[source_sheet.attrib[relationship_id]]
            source_path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            source_xml = ET.fromstring(archive.read(source_path))
            source_cells = {c.attrib['r']: c for c in source_xml.findall('.//s:sheetData/s:row/s:c', NS)}
            for number, record in enumerate(yoy_v2['records'], 7):
                expected = [record['sourceBrand'], record['prospect'],
                            *(record['values'][c['field']] for c in yoy_v2['columns']),
                            record['sourceRow'], record['matchStatus'], ' '.join(record.get('reviewNotes', []))]
                for index, expected_value in enumerate(expected, 1):
                    address = f'{excel_column(index)}{number}'
                    actual = value(source_cells.get(address))
                    if expected_value in (None, ''):
                        require(actual in (None, ''), f'YoY v2!{address}: must remain blank')
                    elif isinstance(expected_value, (int, float)):
                        require(isinstance(actual, (int, float)) and math.isclose(actual, expected_value, abs_tol=1e-9),
                                f'YoY v2!{address}: source value differs from JSON')
                    else:
                        require(actual == expected_value, f'YoY v2!{address}: metadata differs from JSON')

        expected_names = {r['prospect'] for r in data['deliveryRows']}
        actual_names = {value(c) for a, c in cells.items() if a.startswith('A') and a[1:].isdigit()
                        and int(a[1:]) >= 7 and value(c) not in (None, '')}
        require(expected_names == actual_names, 'Delivery identities differ from JSON')
        require(len(expected_names) == len(data['deliveryRows']), 'Duplicate delivery identity')
        for row_number, row in enumerate(data['deliveryRows'], 7):
            for index, field in enumerate(FIELDS):
                address = f'{excel_column(index + 1)}{row_number}'
                expected = row[field]
                if isinstance(expected, list):
                    expected = '; '.join(expected)
                actual = value(cells.get(address))
                if expected in (None, ''):
                    require(actual in (None, ''), f'{address} must remain blank')
                elif isinstance(expected, (int, float)):
                    require(isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=1e-9),
                            f'{address}: {actual} differs from {expected}')
                else:
                    require(actual == expected, f'{address}: exported text differs from {field}')
            live_columns = ('C', 'E', 'G', 'I', 'S', 'AA') + (tuple(excel_column(n) for n in range(28, 36)) if supplement else ()) + (('AJ', 'AK', 'AL') if yoy_v2 else ())
            for column in live_columns:
                require(cells.get(f'{column}{row_number}') is not None and
                        cells[f'{column}{row_number}'].find('s:f', NS) is not None,
                        f'{column}{row_number}: missing live score formula')
        delivery_tables = [ET.fromstring(archive.read(n)) for n in archive.namelist()
                           if n.startswith('xl/tables/') and n.endswith('.xml')]
        require(any(t.get('ref') == f'A6:{excel_column(len(FIELDS))}{6 + len(data["deliveryRows"])}' for t in delivery_tables),
                'Missing native 38-column Delivery table')


def stage_sources(folder):
    for name in SOURCES:
        shutil.copy2(ROOT / name, folder / name)


def check():
    require((ROOT / MANIFEST).exists(), 'Missing delivery-build.json; run the full refresh')
    manifest = json.loads((ROOT / MANIFEST).read_text())
    require(manifest.get('version') == 1, 'Unknown delivery manifest version')
    for group, names in [('sources', SOURCES), ('outputs', OUTPUTS)]:
        require(set(manifest[group]) == set(names), f'Incomplete {group} manifest')
        for name in names:
            require(sha(ROOT / name) == manifest[group][name], f'Stale delivery: {name}; run the full refresh')
    with tempfile.TemporaryDirectory(prefix='wwd-check-') as temp:
        folder = Path(temp)
        stage_sources(folder)
        subprocess.run([sys.executable, str(folder / 'build-weighted-delivery.py')], check=True,
                       stdout=subprocess.DEVNULL)
        for name in OUTPUTS[:2]:
            require((folder / name).read_bytes() == (ROOT / name).read_bytes(),
                    f'{name} does not reproduce from canonical inputs')
    validate_workbook(ROOT)
    print('Delivery current: canonical inputs reproduce JSON/Markdown; Excel hashes, cells, blanks and formulas agree.')


def refresh(args):
    runtime = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node'
    node = Path(args.node or os.environ.get('WWD_NODE', runtime / 'bin/node'))
    modules = Path(args.node_modules or os.environ.get('WWD_NODE_MODULES', runtime / 'node_modules'))
    require(node.is_file() and (modules / '@oai/artifact-tool').exists(),
            'Codex artifact runtime unavailable. Load workspace dependencies and pass --node and --node-modules.')
    output = Path(args.output_dir).resolve() if args.output_dir else None
    with tempfile.TemporaryDirectory(prefix='wwd-refresh-') as temp:
        folder = Path(temp)
        stage_sources(folder)
        (folder / 'node_modules').symlink_to(modules.resolve(), target_is_directory=True)
        subprocess.run([sys.executable, str(folder / 'build-weighted-delivery.py')], check=True)
        env = dict(os.environ)
        if args.previews:
            env['WWD_PREVIEW_FILES'] = args.previews
        subprocess.run([str(node), str(folder / 'build-weighted-workbook.mjs'),
                        str(folder / OUTPUTS[0]), str(folder / 'export')], check=True, env=env)
        shutil.copy2(folder / 'export/fashion-momentum-delivery.xlsx', folder / OUTPUTS[2])
        validate_workbook(folder)
        manifest = {'version': 1, 'sources': {n: sha(ROOT / n) for n in SOURCES},
                    'outputs': {n: sha(folder / n) for n in OUTPUTS}}
        if output:
            output.mkdir(parents=True, exist_ok=True)
            for file in (folder / 'export').iterdir():
                shutil.copy2(file, output / file.name)
        # Publish only after both builders and export validation succeed; manifest goes last.
        for name in OUTPUTS:
            pending = ROOT / (name + '.refresh-tmp')
            shutil.copy2(folder / name, pending)
            os.replace(pending, ROOT / name)
        pending = ROOT / (MANIFEST + '.refresh-tmp')
        pending.write_text(json.dumps(manifest, indent=2) + '\n')
        os.replace(pending, ROOT / MANIFEST)
    check()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Read-only freshness check; Python stdlib only')
    parser.add_argument('--node', help='Node executable returned by load_workspace_dependencies')
    parser.add_argument('--node-modules', help='Bundled package directory returned by load_workspace_dependencies')
    parser.add_argument('--output-dir', help='Optional local copy of the validated workbook and rendered previews')
    parser.add_argument('--previews', help='Comma-separated preview names; omit to render all existing views')
    args = parser.parse_args()
    try:
        check() if args.check else refresh(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'Delivery refresh failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
