"""Replay the saved research snapshot offline and emit portable review artifacts."""
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
inputs = json.loads((ROOT / 'prospect-inputs.json').read_text())
assert len(inputs['brandContent']) == 18
assert len(inputs['environments']) == 26
assert len({e['company'] for e in inputs['environments']}) == 25
(ROOT / 'prospects.json').write_text(json.dumps(inputs, indent=2, ensure_ascii=False) + '\n')

runpy.run_path(str(ROOT / 'build-public-presence-pilot.py'), run_name='__main__')
runpy.run_path(str(ROOT / 'build-score-results.py'), run_name='__main__')
runpy.run_path(str(ROOT / 'build-delivery-table.py'), run_name='__main__')
runpy.run_path(str(ROOT / 'build-weighted-delivery.py'), run_name='__main__')

# The original desktop handoff used absolute paths for the app's file links.
# GitHub and other checkouts need relative links instead. Keep this conversion
# in the entry point so source builders and all generated prompts remain aligned.
for path in sorted(ROOT.rglob('*')):
    if path.is_file() and path.suffix in {'.json', '.md'}:
        path.write_text(path.read_text().replace(str(ROOT) + '/', ''))

packages = json.loads((ROOT / 'prospect-packages.json').read_text())
scores = json.loads((ROOT / 'score-results.json').read_text())
presence = json.loads((ROOT / 'public-presence-review.json').read_text())
for package in packages['packages']:
    assert (ROOT / package['promptFile']).read_text() == package['researchPrompt']
    assert package['customerContent']['cta'] == 'Unlock November signal'
    assert not package['publicPresenceReview']['eligibleForMomentumFormula']
    if package['type'] == 'Retailer':
        assert package['customerContent']['score'] is None
assert presence['counts']['matchedProfiles'] == 27
assert presence['counts']['postsInspected'] == 78
assert {b['company']: b['index'] for b in scores['brands'] if b['index'] is not None} == {
    'Coach': 75, 'Fendi': 69, 'Ralph Lauren': 68, 'Burberry': 64, 'Calvin Klein': 62,
}
print('Offline rebuild complete; 25 prompts, 26 mappings and unchanged score states verified.')
