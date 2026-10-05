import json
from pathlib import Path

from lbo.firms import FIRMS, common as cm

DATA = Path(__file__).resolve().parents[1] / 'firms' / 'data'


def test_committed_fingerprints_match_the_generators():
    pins = json.loads((DATA / 'fingerprints.json').read_text())
    for slug, (build, _, _) in FIRMS.items():
        assert pins[slug] == cm.fingerprint(build()), f'{slug}: regenerate with python3 -m lbo.build_firms'


def test_every_firm_has_its_files_on_disk():
    for slug in FIRMS:
        d = DATA / slug
        assert (d / 'answer_key.json').exists() and (d / 'policy.md').exists() and (d / 'build.json').exists()
        assert any(p.suffix == '.json' and p.stem not in ('answer_key', 'build') for p in d.iterdir())
