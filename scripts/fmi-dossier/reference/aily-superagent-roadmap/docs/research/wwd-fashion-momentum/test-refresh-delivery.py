"""Meaningful freshness/failure tests; temporary copies only, no artifact runtime required."""
import importlib.util
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('refresh_delivery', PACKAGE / 'refresh-delivery.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)

import_spec = importlib.util.spec_from_file_location('import_sales_social', PACKAGE / 'import-sales-social.py')
sales_social = importlib.util.module_from_spec(import_spec)
import_spec.loader.exec_module(sales_social)


class DeliveryFreshness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='wwd-test-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        for name in (*refresh.SOURCES, *refresh.OUTPUTS, refresh.MANIFEST):
            (self.folder / name).write_bytes((PACKAGE / name).read_bytes())
        self.root_patch = patch.object(refresh, 'ROOT', self.folder)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def test_committed_snapshot_reproduces_and_workbook_agrees(self):
        refresh.check()

    def test_changed_report_input_is_stale(self):
        file = self.folder / 'weighted-delivery-inputs.json'
        data = json.loads(file.read_text())
        data['cycles'][0]['baselineMedianLikes'] += 1
        file.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Stale delivery: weighted-delivery-inputs.json'):
            refresh.check()

    def test_omitted_optional_reported_components_use_derived_scores(self):
        file = self.folder / 'weighted-delivery-inputs.json'
        inputs = json.loads(file.read_text())
        expected = json.loads((self.folder / 'weighted-delivery.json').read_text())
        removed = 0
        for cycle in inputs['cycles']:
            for field in ('reportedIrSubscore', 'reportedSocialSubscore', 'reportedStrengthSubscore'):
                if cycle.get(field) is None and field in cycle:
                    cycle.pop(field)
                    removed += 1
        self.assertGreater(removed, 0)
        file.write_text(json.dumps(inputs))
        result = subprocess.run([sys.executable, str(self.folder / 'build-weighted-delivery.py')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads((self.folder / 'weighted-delivery.json').read_text())
        self.assertEqual(actual['deliveryRows'], expected['deliveryRows'])
        for row in actual['records']:
            self.assertEqual([row['page2'][k]['weight'] for k in ('momentum', 'social', 'strength')],
                             [inputs['weights'][k] for k in ('ir', 'social', 'trend')])

    def assert_revision_bounds(self, score, expected_min, expected_max, fendi_display, elc_audit_display):
        file = self.folder / 'weighted-delivery-inputs.json'
        inputs = json.loads(file.read_text())
        extra = deepcopy(inputs['scoreRevisions']['Estée Lauder'])
        extra.update({'revisionId': 'regression-fixture-burberry', 'authority': 'Regression fixture only',
                      'overallScore': score, 'normalizedFashionMomentumIndex': 90,
                      'overallSentiment': 'Good' if score >= 70 else 'Needs improvement'})
        inputs['scoreRevisions']['Burberry'] = extra
        file.write_text(json.dumps(inputs))
        result = subprocess.run([sys.executable, str(self.folder / 'build-weighted-delivery.py')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.folder / 'weighted-delivery.json').read_text())
        bounds = data['overallDisplayNormalization']
        self.assertEqual((bounds['observedMinimum'], bounds['observedMaximum']), (expected_min, expected_max))
        rows = {r['prospect']: r for r in data['deliveryRows']}
        self.assertEqual(rows['Burberry']['normalizedFashionMomentumIndex'], 90)
        self.assertEqual(rows['Fendi']['overallScore'], 47.3)
        self.assertEqual(rows['Fendi']['normalizedFashionMomentumIndex'], fendi_display)
        self.assertEqual(rows['Estée Lauder']['normalizedFashionMomentumIndex'], 86.5)
        self.assertEqual(rows['NORDSTROM']['normalizedFashionMomentumIndex'],
                         round(70 + (60.7 - expected_min) / (expected_max - expected_min) * 28, 1))
        record = next(r for r in data['records'] if r['prospectName'] == 'Estée Lauder')
        self.assertEqual(record['scoreRevision']['reconciliation']['standardNormalizedIndexForSuppliedOverall'], elc_audit_display)
        self.assertEqual(record['page2']['momentum']['sentiment'], 'High')
        self.assertEqual(record['page2']['strength']['sentiment'], 'Strong')
        self.assertEqual(record['page2']['momentum']['categoryPolicy'], 'preserve-supplied')
        self.assertEqual(record['page2']['strength']['categoryPolicy'], 'preserve-supplied')

    def test_revision_above_old_maximum_rescales_other_rows(self):
        self.assert_revision_bounds(99, 20, 99, 79.7, 90.7)

    def test_revision_zero_sets_new_minimum_without_replacing_supplied_display(self):
        self.assert_revision_bounds(0, 0, 96, 83.8, 92.8)

    def rebuild_with_inputs(self, inputs):
        (self.folder / 'weighted-delivery-inputs.json').write_text(json.dumps(inputs))
        return subprocess.run([sys.executable, str(self.folder / 'build-weighted-delivery.py')],
                              capture_output=True, text=True)

    def test_category_leaderboards_use_supplied_display_not_underlying(self):
        data = json.loads((self.folder / 'weighted-delivery.json').read_text())
        rows = {r['prospect']: r for r in data['deliveryRows']}
        self.assertGreater(rows['Estée Lauder']['overallScore'], rows['Coach']['overallScore'])
        self.assertEqual(rows['Estée Lauder']['normalizedFashionMomentumIndex'], 86.5)
        self.assertEqual(rows['Estée Lauder']['leaderboardRank'], 3)
        leaders = {b['category']: (b['members'][0]['prospect'], b['members'][0]['rank'])
                   for b in data['leaderboards'] if b['rankedCount']}
        self.assertEqual(leaders, {'LUXE': ('Coach', 1), 'FAST FOLLOWER': ('J.Crew', 1),
                                  'RETAILER': ('Ulta Beauty', 1)})
        self.assertTrue(all(not r['evidence']['productionReady'] and
                            not r['evidence']['leaderboardEligible'] for r in data['records']))

    def test_competition_ties_and_missing_ranks(self):
        data = json.loads((self.folder / 'weighted-delivery.json').read_text())
        rows = {r['prospect']: r for r in data['deliveryRows']}
        for name in ('Calvin Klein', 'VF Corporation'):
            self.assertEqual((rows[name]['normalizedFashionMomentumIndex'], rows[name]['leaderboardRank']), (76.8, 10))
        self.assertEqual(rows['G-III Apparel Group']['leaderboardRank'], 12)
        missing = [r for r in data['deliveryRows'] if r['normalizedFashionMomentumIndex'] is None]
        self.assertEqual(len(missing), 43)
        self.assertTrue(all(r['leaderboardCategory'] and r['leaderboardRank'] is None for r in missing))
        for record in data['records']:
            row = rows[record['prospectName']]
            self.assertEqual(record['page3']['rank'], row['leaderboardRank'])
            self.assertEqual(record['page3']['category'], row['leaderboardCategory'])

    def test_revised_display_recalculates_competition_ranks(self):
        inputs = json.loads((self.folder / 'weighted-delivery-inputs.json').read_text())
        revision = deepcopy(inputs['scoreRevisions']['Estée Lauder'])
        revision.update({'revisionId': 'regression-fixture-fendi', 'authority': 'Regression fixture only',
                         'overallScore': 47.3, 'overallSentiment': 'Neutral',
                         'normalizedFashionMomentumIndex': 86.5})
        inputs['scoreRevisions']['Fendi'] = revision
        result = self.rebuild_with_inputs(inputs)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.folder / 'weighted-delivery.json').read_text())
        rows = {r['prospect']: r for r in data['deliveryRows']}
        self.assertEqual(rows['Fendi']['leaderboardRank'], 3)
        self.assertEqual(rows['Estée Lauder']['leaderboardRank'], 3)
        self.assertEqual(rows['Moncler']['leaderboardRank'], 8)

    def test_normalized_only_override_preserves_original_and_components(self):
        data = json.loads((self.folder / 'weighted-delivery.json').read_text())
        row = next(r for r in data['deliveryRows'] if r['prospect'] == 'ME+EM')
        self.assertEqual((row['overallScore'], row['normalizedFashionMomentumIndex'], row['leaderboardRank']),
                         (86, 86.2, 3))
        self.assertEqual([row[k] for k in ('momentumScore', 'socialScore', 'strengthScore')], [100, 100, 30])
        record = next(r for r in data['records'] if r['prospectName'] == 'ME+EM')
        self.assertEqual(record['page1']['normalizationBasis'], 'explicit-user-display-override')
        self.assertEqual(record['normalizedDisplayOverride']['standardNormalizedIndex'], 94.3)
        self.assertEqual(record['normalizedDisplayOverride']['previousDeliveredNormalizedFashionMomentumIndex'], 94.3)
        inputs = json.loads((self.folder / 'weighted-delivery-inputs.json').read_text())
        inputs['normalizedDisplayOverrides'] = {}
        result = self.rebuild_with_inputs(inputs)
        self.assertEqual(result.returncode, 0, result.stderr)
        baseline = json.loads((self.folder / 'weighted-delivery.json').read_text())
        original = next(r for r in baseline['deliveryRows'] if r['prospect'] == 'ME+EM')
        self.assertEqual((original['normalizedFashionMomentumIndex'], original['leaderboardRank']), (94.3, 2))
        excluded = {'normalizedFashionMomentumIndex', 'leaderboardRank'}
        self.assertEqual({k:v for k,v in row.items() if k not in excluded},
                         {k:v for k,v in original.items() if k not in excluded})

    def test_nordstrom_accepted_proxy_keeps_standard_gaps_and_assumption(self):
        data = json.loads((self.folder / 'weighted-delivery.json').read_text())
        row = next(r for r in data['deliveryRows'] if r['prospect'] == 'NORDSTROM')
        self.assertEqual((row['overallScore'], row['overallSentiment'],
                          row['normalizedFashionMomentumIndex'], row['leaderboardRank']), (60.7, 'Neutral', 85.0, 2))
        self.assertEqual([row[k] for k in ('momentumScore','socialScore','strengthScore')], [80.6,34.8,50])
        self.assertEqual(row['strengthDescriptor'], 'Neutral (assumed)')
        context = data['sourceContext']['nordstromMixedPeriod']
        self.assertFalse(context['strengthIsObserved'])
        self.assertFalse(context['usedForStandardDelivery'])
        self.assertIsNone(context['standardOverallScore'])
        record = next(r for r in data['records'] if r['prospectName'] == 'NORDSTROM')
        self.assertTrue(record['scoreRevision']['acceptedMixedPeriodProxy'])
        self.assertIsNone(record['scoreRevision']['normalizedFashionMomentumIndex'])
        self.assertIsNone(record['scoreRevision']['previousCalculatedDeliveryRow']['overallScore'])
        self.assertEqual(record['page1']['normalizationBasis'], 'min-max-of-approved-report-proxy')
        self.assertFalse(record['page2']['strength']['scoreIsObserved'])
        self.assertFalse(record['evidence']['productionReady'])

    def test_removing_proxy_acceptance_restores_missing_current_total(self):
        inputs = json.loads((self.folder / 'weighted-delivery-inputs.json').read_text())
        inputs['scoreRevisions'].pop('NORDSTROM')
        result = self.rebuild_with_inputs(inputs)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.folder / 'weighted-delivery.json').read_text())
        row = next(r for r in data['deliveryRows'] if r['prospect'] == 'NORDSTROM')
        self.assertTrue(all(row[k] is None for k in
                            ('overallScore','normalizedFashionMomentumIndex','leaderboardRank',
                             'momentumScore','strengthScore')))
        self.assertEqual(row['socialScore'], 34.8)

    def test_normalized_override_cannot_fill_a_missing_underlying_total(self):
        inputs = json.loads((self.folder / 'weighted-delivery-inputs.json').read_text())
        inputs['scoreRevisions'].pop('NORDSTROM')
        inputs['normalizedDisplayOverrides']['NORDSTROM'] = deepcopy(inputs['normalizedDisplayOverrides']['ME+EM'])
        result = self.rebuild_with_inputs(inputs)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requires a complete underlying overall score', result.stderr)

    def test_duplicate_category_membership_is_rejected(self):
        inputs = json.loads((self.folder / 'weighted-delivery-inputs.json').read_text())
        inputs['leaderboardCategories']['OTHER'].append('Coach')
        result = self.rebuild_with_inputs(inputs)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('exactly one leaderboard category', result.stderr)

    def test_unassigned_category_is_rejected(self):
        inputs = json.loads((self.folder / 'weighted-delivery-inputs.json').read_text())
        inputs['leaderboardCategories']['LUXE'].remove('Coach')
        result = self.rebuild_with_inputs(inputs)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cover the exact delivery companies', result.stderr)

    def test_changed_excel_is_stale(self):
        file = self.folder / 'weighted-delivery.xlsx'
        file.write_bytes(file.read_bytes() + b'changed-workbook')
        with self.assertRaisesRegex(ValueError, 'Stale delivery: weighted-delivery.xlsx'):
            refresh.check()

    def test_rehashing_an_edited_generated_json_does_not_certify_it(self):
        file = self.folder / 'weighted-delivery.json'
        data = json.loads(file.read_text())
        data['deliveryRows'][0]['overallScore'] = 99
        file.write_text(json.dumps(data))
        manifest_file = self.folder / refresh.MANIFEST
        manifest = json.loads(manifest_file.read_text())
        manifest['outputs'][file.name] = refresh.sha(file)
        manifest_file.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'does not reproduce'):
            refresh.check()


    def test_supplement_changes_only_requested_fields_and_preserves_missing_zero(self):
        inputs = json.loads((self.folder / 'weighted-delivery-inputs.json').read_text())
        before = json.loads((self.folder / 'weighted-delivery.json').read_text())
        item = next(r for r in inputs['salesSocialSupplement']['records'] if r['prospect'] == 'Burberry')
        item['values'].update({'smFeb2024': 0, 'smFeb2025': None,
                              'insightsDescriptive': 'FY2026 forecast versus source baseline.',
                              'insightsStatistics': 'Show-window median likes versus ±30-day baseline.'})
        result = self.rebuild_with_inputs(inputs)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = json.loads((self.folder / 'weighted-delivery.json').read_text())
        fields = {c['field'] for c in inputs['salesSocialSupplement']['columns']}
        for old, new in zip(before['deliveryRows'], after['deliveryRows']):
            self.assertEqual({k:v for k,v in old.items() if k not in fields},
                             {k:v for k,v in new.items() if k not in fields})
        for old, new in zip(before['records'], after['records']):
            self.assertEqual({k:v for k,v in old.items() if k != 'salesSocialSupplement'},
                             {k:v for k,v in new.items() if k != 'salesSocialSupplement'})
        row = next(r for r in after['deliveryRows'] if r['prospect'] == 'Burberry')
        self.assertEqual(row['smFeb2024'], 0)
        self.assertIsNone(row['smFeb2025'])
        self.assertEqual(row['insightsDescriptive'], item['values']['insightsDescriptive'])
        self.assertEqual(before['cycles'], after['cycles'])
        self.assertEqual(before['leaderboards'], after['leaderboards'])

    def test_supplement_retains_unmatched_rows_without_creating_prospects(self):
        data = json.loads((self.folder / 'weighted-delivery.json').read_text())
        source = data['salesSocialSupplement']
        self.assertEqual(source['summary'], {'sourceRows': 75, 'matchedRows': 74, 'unmatchedBrands': ['Tory Burch']})
        self.assertFalse(source['usedForScoring'])
        self.assertNotIn('Tory Burch', {r['prospect'] for r in data['deliveryRows']})
        tory = next(r for r in source['records'] if r['sourceBrand'] == 'Tory Burch')
        self.assertIsNone(tory['prospect'])
        self.assertAlmostEqual(tory['values']['smFeb2025'], -0.08598130841121499)
        self.assertEqual(sum(r['insightsDescriptive'] is not None for r in data['deliveryRows']), 25)
        self.assertTrue(all(r['insightsStatistics'] is None for r in data['deliveryRows']))
        burberry = next(r for r in data['deliveryRows'] if r['prospect'] == 'Burberry')
        self.assertAlmostEqual(burberry['q4VsBaseline2024'], -0.0067226355658285275)
        self.assertAlmostEqual(burberry['q4VsBaseline2025'], 0.04591659609982446)
        self.assertIn('Light Actual', source['definitions']['sales'])
        self.assertIn('Mixed source social windows', source['definitions']['social'])
        self.assertIn('not observed revenue', source['definitions']['forecast2026'])
        self.assertEqual(data['salesSocialSupplementHistory'][0]['source']['fileName'], 'seven_brands_sales_social_2024_2026.xlsx')
        previous = data['salesSocialSupplementHistory'][-1]
        self.assertEqual(previous['source']['fileName'], 'seven_brands_sales_social_2024_2026_v3.xlsx')
        self.assertEqual(len(previous['records']), 7)
        old_burberry = next(r for r in previous['records'] if r['sourceBrand'] == 'Burberry')
        self.assertIsNotNone(old_burberry['values']['insightsStatistics'])
        moncler = next(r for r in data['deliveryRows'] if r['prospect'] == 'Moncler')
        self.assertAlmostEqual(moncler['smFeb2026'], 3.6090482287665386)
        louboutin = next(r for r in data['deliveryRows'] if r['prospect'] == 'Christian Louboutin')
        self.assertEqual(louboutin['q4VsBaseline2024'], 0)
        self.assertAlmostEqual(louboutin['q4VsBaseline2025'], -2.0821913471191777e-7)
        self.assertTrue(all(louboutin[k] is None for k in ('smFeb2024', 'smFeb2025', 'smFeb2026', 'q4VsBaseline2026', 'insightsDescriptive', 'insightsStatistics')))
        coach = next(r for r in source['records'] if r['prospect'] == 'Coach')
        self.assertTrue(any('annual median' in note for note in coach['reviewNotes']))
        self.assertTrue(any('parent-group' in note for note in coach['reviewNotes']))
        gap = next(r for r in source['records'] if r['prospect'] == 'GAP Inc')
        self.assertTrue(any('fiscal Q4' in note for note in gap['reviewNotes']))

    def test_duplicate_supplement_matches_are_rejected(self):
        inputs = json.loads((self.folder / 'weighted-delivery-inputs.json').read_text())
        inputs['salesSocialSupplement']['records'][1]['prospect'] = 'Burberry'
        result = self.rebuild_with_inputs(inputs)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Duplicate supplement match', result.stderr)

    def make_sales_social_fixture(self, brands=('Tom Ford', 'Unmatched brand'), bad_cache=False, yoy_v2=False, notes=()):
        path = self.folder / 'source.xlsx'
        sheet = ET.Element('worksheet')
        sheet_data = ET.SubElement(sheet, 'sheetData')
        def append_row(number, values):
            row = ET.SubElement(sheet_data, 'row', {'r': str(number)})
            for index, value in enumerate(values, 1):
                address = refresh.excel_column(index) + str(number)
                attrs = {'r': address}
                if isinstance(value, str):
                    attrs['t'] = 'inlineStr'
                cell = ET.SubElement(row, 'c', attrs)
                if isinstance(value, str):
                    ET.SubElement(ET.SubElement(cell, 'is'), 't').text = value
                elif value is not None:
                    ET.SubElement(cell, 'v').text = str(value)
        append_row(1, ['Brand'] + [c['label'] for c in (sales_social.YOY_V2_COLUMNS if yoy_v2 else sales_social.COLUMNS)])
        for number, brand in enumerate(brands, 2):
            append_row(number, [brand, 0, 'N/D', 0.0195] if yoy_v2 else [brand, 0, 'N/D', -0.25, 0.02, 2.5, 0.0195, None, 'Source insight'])
        forecast = sheet_data.find("row[@r='2']/c[@r='D2']" if yoy_v2 else "row[@r='2']/c[@r='G2']")
        ET.SubElement(forecast, 'f').text = 'FMI_DERIVED_SOURCE_FORMULA'
        if yoy_v2:
            forecast.set('t', 'str')
            forecast.find('v').text = None  # Cached empty string from IF(..., "").
        if bad_cache:
            forecast.remove(forecast.find('v'))
        for number, note in enumerate(notes, len(brands) + 3):
            append_row(number, [note])
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sales &amp; Social" sheetId="1" r:id="r1"/><sheet name="Fuentes" sheetId="2" r:id="r2"/></sheets></workbook>')
            archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/><Relationship Id="r2" Target="worksheets/sheet2.xml"/></Relationships>')
            sheet.set('xmlns', sales_social.NS['s'])
            archive.writestr('xl/worksheets/sheet1.xml', ET.tostring(sheet))
            # Deliberately invalid irrelevant tab proves it is not read by the importer.
            archive.writestr('xl/worksheets/sheet2.xml', 'not parsed')
        return path

    def test_importer_reads_only_requested_tab_and_preserves_units_and_unmatched(self):
        path = self.make_sales_social_fixture()
        snapshot = sales_social.extract(path, [{'prospect': 'TOM FORD'}], received_date='2026-10-28')
        matched, unmatched = snapshot['records']
        self.assertEqual(matched['prospect'], 'TOM FORD')
        self.assertIsNone(unmatched['prospect'])
        self.assertEqual(matched['values']['smFeb2024'], 0)
        self.assertIsNone(matched['values']['q4VsBaseline2024'])
        self.assertEqual(matched['rawValues']['q4VsBaseline2024'], 'N/D')
        self.assertEqual(matched['values']['smFeb2026'], 2.5)
        self.assertIsNone(matched['values']['insightsDescriptive'])
        self.assertEqual(matched['values']['insightsStatistics'], 'Source insight')
        self.assertEqual(matched['sourceFormulas']['q4VsBaseline2026'], '=FMI_DERIVED_SOURCE_FORMULA')
        self.assertFalse(snapshot['usedForScoring'])

    def test_importer_rejects_duplicate_brands_and_missing_formula_cache(self):
        path = self.make_sales_social_fixture(brands=('Tom Ford', 'tom ford'))
        with self.assertRaisesRegex(ValueError, 'Duplicate source brand'):
            sales_social.extract(path, [{'prospect': 'TOM FORD'}])
        path = self.make_sales_social_fixture(bad_cache=True)
        with self.assertRaisesRegex(ValueError, 'missing formula cache'):
            sales_social.extract(path, [{'prospect': 'TOM FORD'}])

    def test_reimport_is_idempotent_and_preserves_all_scoring_inputs(self):
        inputs_path = self.folder / 'weighted-delivery-inputs.json'
        original = json.loads(inputs_path.read_text())
        previous = original['salesSocialSupplement']
        path = self.make_sales_social_fixture(brands=tuple(r['sourceBrand'] for r in previous['records']), notes=previous['source']['notes'])
        command = [sys.executable, str(self.folder / 'import-sales-social.py'), str(path),
                   '--inputs', str(inputs_path), '--received-date', '2026-10-28']
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        first_inputs = inputs_path.read_bytes()
        second = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first_inputs, inputs_path.read_bytes())
        updated = json.loads(inputs_path.read_text())
        excluded = {'salesSocialSupplement', 'salesSocialSupplementHistory'}
        self.assertEqual({k:v for k,v in original.items() if k not in excluded},
                         {k:v for k,v in updated.items() if k not in excluded})
        self.assertEqual(updated['salesSocialSupplementHistory'], original.get('salesSocialSupplementHistory', []) + [original['salesSocialSupplement']])

    def test_yoy_import_accepts_explicit_empty_cache_but_rejects_absent_cache(self):
        path = self.make_sales_social_fixture(yoy_v2=True)
        snapshot = sales_social.extract(path, [{'prospect': 'TOM FORD'}], scope='yoy-v2')
        matched = snapshot['records'][0]
        self.assertEqual(matched['values']['q4VsBaseline2024YoyV2'], 0)
        self.assertIsNone(matched['values']['q4VsBaseline2025YoyV2'])
        self.assertIsNone(matched['values']['q4VsBaseline2026YoyV2'])
        self.assertEqual(matched['rawValues']['q4VsBaseline2026YoyV2'], '')
        self.assertEqual(matched['sourceFormulas']['q4VsBaseline2026YoyV2'], '=FMI_DERIVED_SOURCE_FORMULA')
        path = self.make_sales_social_fixture(yoy_v2=True, bad_cache=True)
        with self.assertRaisesRegex(ValueError, 'missing formula cache'):
            sales_social.extract(path, [{'prospect': 'TOM FORD'}], scope='yoy-v2')

    def test_yoy_scoped_reimport_preserves_legacy_snapshot_and_all_scoring_inputs(self):
        inputs_path = self.folder / 'weighted-delivery-inputs.json'
        original = json.loads(inputs_path.read_text())
        previous = original['salesYoyV2Supplement']
        path = self.make_sales_social_fixture(brands=tuple(r['sourceBrand'] for r in previous['records']), notes=previous['source']['notes'], yoy_v2=True)
        command = [sys.executable, str(self.folder / 'import-sales-social.py'), str(path),
                   '--inputs', str(inputs_path), '--scope', 'yoy-v2', '--received-date', '2026-10-28']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        updated = json.loads(inputs_path.read_text())
        excluded = {'salesYoyV2Supplement', 'salesYoyV2SupplementHistory'}
        self.assertEqual({k:v for k,v in original.items() if k not in excluded},
                         {k:v for k,v in updated.items() if k not in excluded})
        self.assertEqual(updated['salesYoyV2SupplementHistory'],
                         original.get('salesYoyV2SupplementHistory', []) + [original['salesYoyV2Supplement']])
        first_bytes = inputs_path.read_bytes()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(inputs_path.read_bytes(), first_bytes)

    def test_source_revision_cannot_silently_drop_accepted_qualifications(self):
        inputs = json.loads((self.folder / 'weighted-delivery-inputs.json').read_text())
        for key, scope, phrase in [('salesSocialSupplement', 'sales-social', 'annual median captured likes YoY'),
                                   ('salesYoyV2Supplement', 'yoy-v2', 'Sales Q4 2026 vacío')]:
            previous = inputs[key]
            notes = [note.replace(phrase, 'reworded source qualification') for note in previous['source']['notes']]
            path = self.make_sales_social_fixture(brands=tuple(r['sourceBrand'] for r in previous['records']),
                                                 notes=notes, yoy_v2=scope == 'yoy-v2')
            with self.assertRaisesRegex(ValueError, 'Source qualifications changed or removed'):
                sales_social.extract(path, [], scope=scope, previous_snapshot=previous)

    def test_recognized_qualification_profiles_reject_renamed_brands(self):
        inputs = json.loads((self.folder / 'weighted-delivery-inputs.json').read_text())
        for key, scope, brand in [('salesSocialSupplement', 'sales-social', 'Coach'),
                                  ('salesYoyV2Supplement', 'yoy-v2', 'Belmont Park Village')]:
            previous = inputs[key]
            brands = tuple('Renamed source brand' if r['sourceBrand'] == brand else r['sourceBrand'] for r in previous['records'])
            path = self.make_sales_social_fixture(brands=brands, notes=previous['source']['notes'],
                                                 yoy_v2=scope == 'yoy-v2')
            with self.assertRaisesRegex(ValueError, 'Qualified source brands missing or renamed'):
                sales_social.extract(path, [], scope=scope, previous_snapshot=previous)

    def test_failed_qualification_validation_preserves_canonical_inputs(self):
        inputs_path = self.folder / 'weighted-delivery-inputs.json'
        original = inputs_path.read_bytes()
        path = self.make_sales_social_fixture()
        result = subprocess.run([sys.executable, str(self.folder / 'import-sales-social.py'), str(path),
                                 '--inputs', str(inputs_path), '--received-date', '2026-10-28'],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Source qualifications changed or removed', result.stderr)
        self.assertEqual(inputs_path.read_bytes(), original)

    def test_yoy_changes_preserve_all_35_previous_fields_records_and_boards(self):
        inputs = json.loads((self.folder / 'weighted-delivery-inputs.json').read_text())
        before = json.loads((self.folder / 'weighted-delivery.json').read_text())
        item = next(r for r in inputs['salesYoyV2Supplement']['records'] if r['prospect'] == 'Burberry')
        item['values'].update({'q4VsBaseline2024YoyV2': 0, 'q4VsBaseline2025YoyV2': None,
                              'q4VsBaseline2026YoyV2': 9})
        result = self.rebuild_with_inputs(inputs)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = json.loads((self.folder / 'weighted-delivery.json').read_text())
        fields = {c['field'] for c in inputs['salesYoyV2Supplement']['columns']}
        for old, new in zip(before['deliveryRows'], after['deliveryRows']):
            self.assertEqual({k:v for k,v in old.items() if k not in fields},
                             {k:v for k,v in new.items() if k not in fields})
        for old, new in zip(before['records'], after['records']):
            self.assertEqual({k:v for k,v in old.items() if k != 'salesYoyV2Supplement'},
                             {k:v for k,v in new.items() if k != 'salesYoyV2Supplement'})
        excluded = {'deliveryRows', 'records', 'salesYoyV2Supplement'}
        self.assertEqual({k:v for k,v in before.items() if k not in excluded},
                         {k:v for k,v in after.items() if k not in excluded})
        row = next(r for r in after['deliveryRows'] if r['prospect'] == 'Burberry')
        self.assertEqual(row['q4VsBaseline2024YoyV2'], 0)
        self.assertIsNone(row['q4VsBaseline2025YoyV2'])

    def test_yoy_source_coverage_and_qualifications_are_retained(self):
        data = json.loads((self.folder / 'weighted-delivery.json').read_text())
        source = data['salesYoyV2Supplement']
        self.assertEqual(source['summary']['sourceRows'], 75)
        self.assertEqual(source['summary']['matchedRows'], 74)
        self.assertEqual(source['summary']['unmatchedBrands'], ['Tory Burch'])
        self.assertEqual(list(source['summary']['numericMatchedValuesByYear'].values()), [33, 36, 28])
        self.assertFalse(source['usedForScoring'])
        by_name = {r['sourceBrand']: r for r in source['records']}
        self.assertEqual(by_name['Belmont Park Village']['values']['q4VsBaseline2024YoyV2'], 1049999)
        self.assertIn('tiny denominator', by_name['Belmont Park Village']['reviewNotes'][0])
        self.assertEqual(by_name['Christian Louboutin']['values']['q4VsBaseline2024YoyV2'], 0)
        self.assertIsNone(by_name['Christian Louboutin']['values']['q4VsBaseline2026YoyV2'])
        conflicts = {r['sourceBrand'] for r in source['records']
                     if any('closing source note' in note for note in r['reviewNotes'])}
        self.assertEqual(conflicts, {'J.Crew', 'Lafayette 148', 'PacSun', 'David Yurman'})
        self.assertNotIn('Tory Burch', {r['prospect'] for r in data['deliveryRows']})

    def test_duplicate_yoy_matches_are_rejected(self):
        inputs = json.loads((self.folder / 'weighted-delivery-inputs.json').read_text())
        inputs['salesYoyV2Supplement']['records'][1]['prospect'] = inputs['salesYoyV2Supplement']['records'][0]['prospect']
        result = self.rebuild_with_inputs(inputs)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Duplicate YoY v2 match', result.stderr)


    def test_five_annual_reports_apply_agreed_rule_and_keep_source_alternatives(self):
        data = json.loads((self.folder / 'weighted-delivery.json').read_text())
        rows = {r['prospect']:r for r in data['deliveryRows']}
        expected = {'PacSun':(40.4,77.5,30),'Lafayette 148':(59.3,84.5,80),
                    'Jacquemus':(26.1,72.2,30),'J.Crew':(96,98,80),'David Yurman':(40.9,77.7,30)}
        context = data['sourceContext']['annualReports20261028']
        for name, values in expected.items():
            row=rows[name]
            self.assertEqual(tuple(row[k] for k in ('overallScore','normalizedFashionMomentumIndex','strengthScore')),values)
            record=next(r for r in data['records'] if r['prospectName']==name)
            self.assertFalse(record['evidence']['productionReady'])
            self.assertIn(record['page1']['coreInsightSourceCycleKey'], {c['cycleKey'] for c in data['cycles']})
            self.assertEqual(record['page2']['strength']['cardKpi']['unit'],'%')
            self.assertIn('WWD FY',record['page2']['strength']['cardInsight'])
            self.assertEqual(record['page2']['social']['cardKpi']['unit'],'%')
            self.assertIn('2026 vs 2025',record['page2']['social']['cardInsight'])
            self.assertTrue(all(len(record['page2'][component]['cardInsight'])<=160 for component in ('momentum','social','strength')))
            self.assertFalse(context['companies'][name]['usedSourceOverallForDelivery'])
        self.assertEqual(context['companies']['J.Crew']['reportedOverall'],94)
        self.assertEqual(context['companies']['Lafayette 148']['reportedOverall'],57.3)
        self.assertEqual(data['receivedSourceReportCount'],51)
        self.assertEqual(data['overallDisplayNormalization']['observedMaximum'],96)

    def test_annual_social_sample_boundary_and_zero_are_distinct(self):
        inputs=json.loads((self.folder / 'weighted-delivery-inputs.json').read_text())
        cycle=next(c for c in inputs['cycles'] if c['cycleKey']==inputs['selectedCycles']['PacSun'])
        cycle['baselinePostCount']=19
        result=self.rebuild_with_inputs(inputs)
        self.assertEqual(result.returncode,0,result.stderr)
        after=json.loads((self.folder / 'weighted-delivery.json').read_text())
        row=next(r for r in after['deliveryRows'] if r['prospect']=='PacSun')
        self.assertIsNone(row['socialScore']);self.assertIsNone(row['overallScore'])
        self.assertEqual(row['momentumScore'],45.2)
        cycle['baselinePostCount']=20;cycle['showMedianLikes']=0
        result=self.rebuild_with_inputs(inputs)
        self.assertEqual(result.returncode,0,result.stderr)
        after=json.loads((self.folder / 'weighted-delivery.json').read_text())
        row=next(r for r in after['deliveryRows'] if r['prospect']=='PacSun')
        self.assertEqual(row['socialScore'],0);self.assertEqual(row['overallScore'],28.6)
        cycle['showMedianLikes']=574;cycle['socialIncludedCalendarMonths']=[1,3]
        result=self.rebuild_with_inputs(inputs)
        self.assertEqual(result.returncode,0,result.stderr)
        after=json.loads((self.folder / 'weighted-delivery.json').read_text())
        self.assertIsNone(next(r for r in after['deliveryRows'] if r['prospect']=='PacSun')['overallScore'])

    def test_runtime_failure_preserves_previous_delivery(self):
        names = (*refresh.OUTPUTS, refresh.MANIFEST)
        before = {name: (self.folder / name).read_bytes() for name in names}
        result = subprocess.run([sys.executable, str(self.folder / 'refresh-delivery.py'),
                                 '--node', str(self.folder / 'missing-node')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('runtime unavailable', result.stderr)
        self.assertEqual(before, {name: (self.folder / name).read_bytes() for name in names})


if __name__ == '__main__':
    unittest.main()
