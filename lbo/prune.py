# research/lbo/prune.py
"""Remove runs that measured the harness rather than the arm.

    python3 -m lbo.prune --tasks r_like_for_like --ended-by max_budget,error

A run cut off by the budget, or one whose task has since been reworded, is not evidence
about the arm that produced it, and leaving it in the result set quietly lowers that
arm's pass rate for a reason the paper would have to explain. Deleting it is honest only
because the harness is idempotent by (task, arm, ablation, seed): what is removed here is
simply run again.

Nothing is removed unless a filter is given, so the command cannot empty the result set
by being run with no arguments.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .harness import RESULTS_DIR
from .trajectory import LOGS_DIR


def _kinds_by_task() -> dict[str, str]:
    from . import tasks as tk
    return {t.id: t.kind for t in tk.TASKS}


def prune(results_dir: Path | str = RESULTS_DIR, logs_dir: Path | str = LOGS_DIR, *,
          tasks: tuple[str, ...] = (), ended_by: tuple[str, ...] = (),
          arms: tuple[str, ...] = (), kinds: tuple[str, ...] = (),
          dry_run: bool = False) -> dict:
    """Delete the records these filters name, and their logs.

    Two kinds of filter, and the difference matters. `tasks` and `ended_by` SELECT: a
    record matching either is a candidate. `arms` and `kinds` RESTRICT: a candidate is
    only removed if it is also on one of those arms and of one of those kinds. With no
    selector, every record is a candidate and the restrictions do the choosing, which is
    what `--arms A B --kinds action,refusal` means.
    """
    if not (tasks or ended_by or arms or kinds):
        return {'removed': [], 'kept': 0, 'error': 'no filter given; nothing was removed'}
    runs = Path(results_dir) / 'runs'
    paths = sorted(runs.glob('*.json')) if runs.is_dir() else []
    kind_of = _kinds_by_task() if kinds else {}
    removed, kept = [], 0
    for p in paths:
        rec = json.loads(p.read_text(encoding='utf-8'))
        why = ''
        if rec.get('task') in tasks:
            why = f'task {rec["task"]}'
        elif rec.get('ended_by') in ended_by:
            why = f'ended_by {rec["ended_by"]}'
        elif not tasks and not ended_by:
            why = 'every record'                      # the restrictions below decide
        if why and arms and rec.get('arm') not in arms:
            why = ''
        if why and kinds:
            kind = kind_of.get(rec.get('task'))
            # a task the suite no longer carries has no kind, so it is not swept up by one
            why = f'{why}, arm {rec.get("arm")} kind {kind}' if kind in kinds else ''
        if not why:
            kept += 1
            continue
        log = Path(logs_dir) / f'{rec["hash"]}.json'
        removed.append({'hash': rec['hash'], 'task': rec.get('task'), 'arm': rec.get('arm'),
                        'ablation': rec.get('ablation'), 'seed_index': rec.get('seed_index'),
                        'why': why, 'had_log': log.is_file()})
        if not dry_run:
            p.unlink()
            if log.is_file():
                log.unlink()
    return {'removed': removed, 'kept': kept, 'error': '', 'dry_run': dry_run}


def _split(s: str) -> tuple[str, ...]:
    return tuple(x for x in (s or '').replace(',', ' ').split() if x)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='delete recorded runs by task or by how they ended')
    ap.add_argument('--tasks', default='', help='select: comma or space separated task ids')
    ap.add_argument('--ended-by', default='', help='select: any of completed, max_turns, '
                                                   'max_budget, error')
    ap.add_argument('--arms', nargs='+', default=[], help='restrict to these arms')
    ap.add_argument('--kinds', default='', help='restrict to these task kinds, for example '
                                                'action,refusal')
    ap.add_argument('--results-dir', default=str(RESULTS_DIR))
    ap.add_argument('--logs-dir', default=str(LOGS_DIR))
    ap.add_argument('--dry-run', action='store_true', help='report what would go, delete nothing')
    a = ap.parse_args(argv)
    out = prune(a.results_dir, a.logs_dir, tasks=_split(a.tasks), ended_by=_split(a.ended_by),
                arms=tuple(a.arms), kinds=_split(a.kinds), dry_run=a.dry_run)
    if out['error']:
        print(out['error'])
        return 2
    verb = 'would remove' if a.dry_run else 'removed'
    print(f'{verb} {len(out["removed"])}, kept {out["kept"]}')
    for r in out['removed']:
        log = '' if r['had_log'] else '  (no log on disk)'
        print(f'  {r["task"]:26s} {r["arm"]} {r["ablation"]:12s} seed{r["seed_index"]}  '
              f'{r["why"]}{log}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
