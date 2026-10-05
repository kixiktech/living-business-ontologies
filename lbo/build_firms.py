# research/lbo/build_firms.py
"""Write the three firms to disk: sources, policy, answer key, and the build log.

    python3 -m lbo.build_firms          (from research/)

The generators are deterministic, so this is reproducible; the fingerprints file pins
what is committed to what the code produces, and a test refuses drift.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .firms import FIRMS, common as cm
from .ingest import ingest

DATA_DIR = Path(__file__).resolve().parent / 'firms' / 'data'


def main(out_dir: Path = DATA_DIR) -> dict:
    pins = {}
    for slug, (build, _, _) in FIRMS.items():
        firm = build()
        cm.write_sources(firm, out_dir)
        cm.write_answer_key(firm, out_dir)
        cm.write_policy(firm, out_dir)
        b = ingest(firm)
        d = out_dir / slug
        (d / 'build.json').write_text(
            json.dumps({**asdict(b.log), 'hash': b.log.hash(), 'stats': b.stats, 'problems': b.problems},
                       indent=1, default=str) + '\n', encoding='utf-8')
        pins[slug] = cm.fingerprint(firm)
        print(f'{slug}: {b.stats["assertions"]} assertions, {b.stats["review_queue"]} review candidates, '
              f'{len(b.problems)} problems, fingerprint {pins[slug]}')
    (out_dir / 'fingerprints.json').write_text(json.dumps(pins, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return pins


if __name__ == '__main__':
    main()
