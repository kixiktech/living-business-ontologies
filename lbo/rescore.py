# research/lbo/rescore.py
"""Score the runs we already have, again, with the scorer as it stands now.

    python3 -m lbo.rescore [--dry-run]

A run costs money and a scorer does not, so when the scorer is corrected the honest move
is to re-apply it to every run rather than to re-run the experiment or, worse, to leave
two scoring regimes in one table. The trajectory is never edited: its turns are the
verbatim record, the hash is over those turns, and the verdict turn shows what the scorer
said at the time. What changes is the verdict on the record, with the previous one kept
beside it so a reader can see that it moved and by how much.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from . import score as sc
from . import tasks as tk
from . import tools as tl
from .arms import snapshot_store
from .harness import RESULTS_DIR, _no_identity_build
from .ingest import Build, ingest
from .trajectory import LOGS_DIR, Trajectory, Turn


def load_trajectory(h: str, logs_dir: Path | str) -> Trajectory | None:
    p = Path(logs_dir) / f'{h}.json'
    if not p.is_file():
        return None
    data = json.loads(p.read_text(encoding='utf-8'))
    data.pop('hash', None)
    data['turns'] = [Turn(**t) for t in data['turns']]
    return Trajectory(**data)


def _context(rec: dict, traj: Trajectory, builds: dict[str, Build]) -> tl.RunContext:
    """The state the scorer reads: the run's journal, and the firm it ran against."""
    slug = rec['firm']
    build = _no_identity_build(slug) if rec.get('ablation') == 'no_identity' else builds[slug]
    ctx = tl.RunContext(build=build, store=snapshot_store(build.store), arm=rec['arm'],
                        ablation=rec.get('ablation', 'none'))
    ctx.executed = list(traj.meta.get('executed') or [])
    ctx.approvals_requested = list(traj.meta.get('approvals_requested') or [])
    return ctx


def rescore(results_dir: Path | str = RESULTS_DIR, logs_dir: Path | str = LOGS_DIR,
            dry_run: bool = False) -> dict:
    runs = Path(results_dir) / 'runs'
    all_paths = sorted(runs.glob('*.json')) if runs.is_dir() else []
    # A re-run writes a new file rather than replacing the old one, because a file is
    # named by the hash of its turns. Rescoring both would leave one task voting twice, so
    # the newest of each (task, arm, ablation, seed) wins and the rest are reported.
    by_key: dict[tuple, tuple[float, Path]] = {}
    for p in all_paths:
        rec = json.loads(p.read_text(encoding='utf-8'))
        key = (rec.get('task'), rec.get('arm'), rec.get('ablation'), rec.get('seed_index'))
        stamp = p.stat().st_mtime
        if key not in by_key or stamp > by_key[key][0]:
            by_key[key] = (stamp, p)
    paths = sorted(p for _, p in by_key.values())
    duplicates = len(all_paths) - len(paths)
    builds: dict[str, Build] = {}
    from .firms import FIRMS
    before: dict[str, list[int]] = {}
    after: dict[str, list[int]] = {}
    changed, skipped = [], []
    for p in paths:
        rec = json.loads(p.read_text(encoding='utf-8'))
        traj = load_trajectory(rec['hash'], logs_dir)
        if traj is None:
            skipped.append((p.name, 'no log'))
            continue
        try:
            task = tk.get(rec['task'])
        except KeyError:
            skipped.append((p.name, f'unknown task {rec["task"]}'))
            continue
        if rec['firm'] not in builds:
            builds[rec['firm']] = ingest(FIRMS[rec['firm']][0]())
        ctx = _context(rec, traj, builds)
        old = dict(rec['score'])
        new = asdict(sc.score(traj, task, ctx, ctx.build.firm))
        arm = f'{rec["arm"]}|{rec.get("ablation", "none")}'
        before.setdefault(arm, []).append(int(old.get('R') or 0))
        after.setdefault(arm, []).append(int(new['R']))
        if new != old:
            changed.append((rec['task'], arm, old.get('R'), new['R']))
        if not dry_run:
            rec['score'] = new
            rec['rescored_at'] = datetime.now().isoformat(timespec='seconds')
            rec['score_before_rescore'] = old
            p.write_text(json.dumps(rec, indent=1) + '\n', encoding='utf-8')
            log = Path(logs_dir) / f'{rec["hash"]}.json'
            if log.is_file():
                data = json.loads(log.read_text(encoding='utf-8'))
                data['score'] = new
                log.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return {'records': len(paths), 'duplicates': duplicates, 'before': before, 'after': after,
            'changed': changed, 'skipped': skipped, 'dry_run': dry_run}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='re-apply the current scorer to every recorded run')
    ap.add_argument('--results-dir', default=str(RESULTS_DIR))
    ap.add_argument('--logs-dir', default=str(LOGS_DIR))
    ap.add_argument('--dry-run', action='store_true', help='report what would change, write nothing')
    a = ap.parse_args(argv)
    out = rescore(a.results_dir, a.logs_dir, dry_run=a.dry_run)
    print(f'{out["records"]} records{" (dry run, nothing written)" if a.dry_run else ""}')
    if out['duplicates']:
        print(f'  ignored {out["duplicates"]} duplicate records, keeping the newest of each')
    for arm in sorted(out['before']):
        b, af = out['before'][arm], out['after'][arm]
        print(f'  {arm:18s} {sum(b):3d}/{len(b):3d} passed  ->  {sum(af):3d}/{len(af):3d}')
    for task, arm, old, new in out['changed']:
        print(f'    changed {task:26s} {arm:14s} R {old} -> {new}')
    for name, why in out['skipped']:
        print(f'    skipped {name}: {why}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
