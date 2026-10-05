# research/lbo/report.py
"""Every table and chart the paper reads, computed from the run records.

    python3 -m lbo.report

Nothing here is typed by hand. `results/summary.json` is the flat list of every number
the prose is allowed to quote, so a figure in the text that has drifted from the runs
can be caught by comparison rather than by reading.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import palette as pal
from . import score as sc
from . import tasks as tk

RESULTS_DIR = Path(__file__).resolve().parent / 'results'
CHARTS_DIR = Path(__file__).resolve().parent / 'charts'

ARMS = ('A', 'B', 'C')
ARM_LABEL = {'A': 'A: tables', 'B': 'B: metric layer', 'C': 'C: ontology'}
ARM_COLOUR = {'A': pal.ROLE['tool'], 'B': pal.ROLE['monitor'], 'C': pal.ROLE['agent']}
FIRM_LABEL = {'retail': 'Retail', 'fieldservice': 'Field service', 'distributor': 'Distributor'}
ABLATIONS = ('none',) + tk.ABLATIONS
ABLATION_LABEL = {'none': 'none (full model)', 'no_time': 'no time', 'no_evidence': 'no evidence',
                  'no_identity': 'no identity', 'no_authority': 'no authority'}
FAILURE_COLOUR = {
    'wrong_number': pal.ROLE['fail'], 'wrong_entity': pal.ROLE['owner'],
    'unauthorised_write': pal.LAYER['meaning'], 'missing_action': pal.LAYER['control'],
    'missing_communication': pal.ROLE['reflect'], 'invented_number': pal.LAYER['extension'],
    'timeout': pal.GREY, 'no_answer': pal.FAINT,
}


# ---- reading the runs -----------------------------------------------------------------

def load_runs(results_dir: Path | str = RESULTS_DIR) -> tuple[list[dict], int]:
    """Every run record, one per (task, arm, ablation, seed), and how many were dropped.

    A re-run writes a new file rather than replacing the old one, because the name is the
    hash of the turns and a second attempt has different turns. Counting both would let
    one task vote twice, so the newest file wins and the count of what it displaced is
    returned rather than swallowed.
    """
    runs = Path(results_dir) / 'runs'
    if not runs.is_dir():
        return [], 0
    by_key: dict[tuple, tuple[float, dict]] = {}
    total = 0
    for p in sorted(runs.glob('*.json')):
        rec = json.loads(p.read_text(encoding='utf-8'))
        total += 1
        key = (rec.get('task'), rec.get('arm'), rec.get('ablation'), rec.get('seed_index'))
        stamp = p.stat().st_mtime
        if key not in by_key or stamp > by_key[key][0]:
            by_key[key] = (stamp, rec)
    return [r for _, r in by_key.values()], total - len(by_key)


def _trials(rows: list[dict]) -> int:
    """The k these runs can actually support: the fewest trials any of their tasks had."""
    by_task: dict[str, int] = {}
    for r in rows:
        by_task[r['task']] = by_task.get(r['task'], 0) + 1
    return min(by_task.values()) if by_task else 0


def _pick(rows: list[dict], **where) -> list[dict]:
    return [r for r in rows if all(r.get(k) == v for k, v in where.items())]


def _pass(rows: list[dict], k: int) -> float | None:
    """pass^k over these runs: the mean over their tasks of each task's pass^k."""
    if not rows:
        return None
    by_task: dict[str, list[bool]] = {}
    for r in rows:
        by_task.setdefault(r['task'], []).append(bool(r['score'].get('R')))
    return round(100.0 * sum(sc.pass_hat_k(v, k) for v in by_task.values()) / len(by_task), 2)


def _fmt(v, suffix: str = '') -> str:
    return '' if v is None else f'{v:g}{suffix}'


def _bold_best(rows: list[list], cols: list[int], want_max: bool = True) -> list[list[int]]:
    """The winning cell in each named column, read back off the rendered strings."""
    out = []
    for c in cols:
        vals = []
        for r, row in enumerate(rows):
            m = re.search(r'-?\d+(?:\.\d+)?', str(row[c]))
            if m:
                vals.append((float(m.group(0)), r))
        if not vals:
            continue
        best = (max if want_max else min)(vals)[0]
        out += [[r, c] for v, r in vals if v == best]
    return out


def _write_table(results_dir: Path, name: str, spec: dict) -> None:
    d = Path(results_dir) / 'tables'
    d.mkdir(parents=True, exist_ok=True)
    (d / f'{name}.json').write_text(json.dumps(spec, indent=1) + '\n', encoding='utf-8')


# ---- the tables --------------------------------------------------------------------------

def _all_trials_label(k: int) -> str:
    """With n trials per task and k = n, pass^k is not an estimator of anything: it is the
    share of tasks that passed every trial, a count. The column is named for what it is."""
    return 'Both trials passed' if k == 2 else f'All {k} trials passed'


def main_results(rows: list[dict]) -> dict:
    ks = {arm: _trials(_pick(rows, arm=arm, ablation='none')) for arm in ARMS}
    seen = sorted({k for k in ks.values() if k})
    k_label = _all_trials_label(seen[0]) if len(seen) == 1 else 'All trials passed'
    cols = ['Arm', 'Retail pass^1', 'Field service pass^1', 'Distributor pass^1', 'All pass^1',
            k_label, 'Mean cost ($)']
    out = []
    for arm in ARMS:
        live = _pick(rows, arm=arm, ablation='none')
        k = ks[arm]
        costs = [float(r.get('cost_usd') or 0.0) for r in live]
        out.append([ARM_LABEL[arm]]
                   + [_fmt(_pass(_pick(live, firm=f), 1)) for f in FIRM_LABEL]
                   + [_fmt(_pass(live, 1)), _fmt(_pass(live, k) if k else None),
                      f'{sum(costs) / len(costs):.3f}' if costs else ''])
    bold = _bold_best(out, [1, 2, 3, 4, 5]) + _bold_best(out, [6], want_max=False)
    if len(seen) == 1:
        says = f'every task ran {seen[0]} times per arm'
    elif seen:
        says = 'trials per task: ' + ', '.join(f'{ks[a]} for arm {a}' for a in ARMS if ks[a])
    else:
        says = 'no arm has been run yet'
    return {'columns': cols, 'rows': out, 'bold': bold,
            'align': ['l', 'r', 'r', 'r', 'r', 'r', 'r'],
            'caption': 'Pass rates by arm and firm, over the tasks with no ablation. pass^1 is the share '
                       f'of trials that pass. The next column is the share of tasks that passed on every '
                       f'trial ({says}); with as many trials as tasks have, that is a count and not an '
                       'estimate of reliability. Mean cost is dollars per run.'}


def by_kind(rows: list[dict]) -> dict:
    kinds = sorted({t.kind for t in tk.TASKS})
    cols = ['Task kind', 'Tasks'] + [f'{ARM_LABEL[a]} pass^1' for a in ARMS]
    out = []
    for kind in kinds:
        ids = {t.id for t in tk.TASKS if t.kind == kind}
        live = [r for r in rows if r['ablation'] == 'none' and r['task'] in ids]
        out.append([kind.replace('_', ' '), len(ids)]
                   + [_fmt(_pass(_pick(live, arm=a), 1)) for a in ARMS])
    return {'columns': cols, 'rows': out, 'bold': _bold_best(out, [2, 3, 4]),
            'align': ['l', 'r', 'r', 'r', 'r'],
            'caption': 'pass^1 by the kind of thing the owner asked for. A refusal task passes only when '
                       'the run declines the write and says why; an action task only when the write lands.'}


def _top_failure(live: list[dict], empty: str = 'none') -> str:
    hist: dict[str, int] = {}
    for r in live:
        f = r['score'].get('failure') or ''
        if f:
            hist[f] = hist.get(f, 0) + 1
    return max(hist.items(), key=lambda kv: (kv[1], kv[0]))[0].replace('_', ' ') if hist else empty


def _ablation_rows(rows: list[dict]) -> list[dict]:
    """One record per ablation: the ablated pass^1 on its probe tasks, the full model's
    pass^1 on the same tasks (the matched comparison, since the probe sets differ), and
    the difference. The full model's own row covers the whole suite."""
    out = []
    for ab in ABLATIONS:
        ids = ({t.id for t in tk.TASKS} if ab == 'none'
               else {t.id for t in tk.TASKS if ab in t.targets})
        live = [r for r in rows if r['arm'] == 'C' and r['ablation'] == ab and r['task'] in ids]
        full = [r for r in rows if r['arm'] == 'C' and r['ablation'] == 'none' and r['task'] in ids]
        got, base = _pass(live, 1), _pass(full, 1)
        # scored/target while a result set is partial, so a row cannot read as though the
        # whole probe set had been run when only part of it has.
        scored = len({r['task'] for r in live})
        out.append({'ablation': ab, 'targets': len(ids), 'scored': scored,
                    'covered': str(len(ids)) if scored == len(ids) else f'{scored}/{len(ids)}',
                    'pass1': got, 'baseline': base,
                    'delta': None if got is None or base is None else round(got - base, 2),
                    'runs': len(live), 'top': _top_failure(live)})
    # the full model first, then the removals ordered by what they cost, largest loss
    # first; an ablation not yet run keeps its declared place at the end
    head, rest = out[:1], out[1:]
    rest.sort(key=lambda d: (d['delta'] is None, d['delta'] if d['delta'] is not None else 0.0))
    return head + rest


def ablations(rows: list[dict]) -> dict:
    cols = ['Ablation', 'Target tasks', 'Ablated pass^1', 'Full model, same tasks', 'Delta',
            'Main failure']
    out = []
    for d in _ablation_rows(rows):
        if d['ablation'] == 'none':
            out.append([ABLATION_LABEL['none'], d['covered'], _fmt(d['pass1']), '', '', d['top']])
        else:
            out.append([ABLATION_LABEL[d['ablation']], d['covered'], _fmt(d['pass1']),
                        _fmt(d['baseline']),
                        '' if d['delta'] is None else f'{d["delta"]:+g}', d['top']])
    return {'columns': cols, 'rows': out, 'bold': [], 'align': ['l', 'r', 'r', 'r', 'r', 'l'],
            'caption': 'Arm C with one part of the model removed, one trial per task. Each removal is '
                       'scored only on the tasks that probe it, so the matched column is the full model '
                       'on those same tasks and the delta is the like-for-like difference; rows are '
                       'ordered by that difference. The first row is the full model over the whole '
                       'suite. At two to six runs a row, a difference of one run is the whole delta.'}


def _failures_by_arm(live: list[dict]) -> str:
    """'A, B: wrong number; C: missing communication', naming only the arms that lost."""
    tops: dict[str, list[str]] = {}
    for arm in ARMS:
        top = _top_failure(_pick(live, arm=arm), empty='')
        if top:
            tops.setdefault(top, []).append(arm)
    return '; '.join(f'{", ".join(arms)}: {top}' for top, arms in tops.items())


def per_task(rows: list[dict]) -> dict:
    cols = ['Task', 'Firm', 'Kind'] + [f'{a} pass^1' for a in ARMS] + ['Dominant failure, by arm']
    out = []
    for t in tk.TASKS:
        live = [r for r in rows if r['task'] == t.id and r['ablation'] == 'none']
        out.append([t.id, FIRM_LABEL[t.firm], t.kind.replace('_', ' ')]
                   + [_fmt(_pass(_pick(live, arm=a), 1)) for a in ARMS] + [_failures_by_arm(live)])
    return {'columns': cols, 'rows': out, 'bold': [], 'align': ['l', 'l', 'l', 'r', 'r', 'r', 'l'],
            'caption': 'Every task in the suite, pass^1 per arm, and for each arm that lost a trial the '
                       'failure class that accounted for most of its losses. A run fails on the first '
                       'dimension it loses.'}


def firm_stats() -> dict:
    from .firms import FIRMS
    from .ingest import ingest
    cols = ['Firm', 'Industry', 'Sources', 'Records', 'Entities', 'Assertions', 'Relation types in use',
            'Tasks']
    out = []
    for slug in FIRM_LABEL:
        b = ingest(FIRMS[slug][0]())
        entities = b.store.db.execute('SELECT COUNT(DISTINCT subject) FROM assertions WHERE client=?',
                                      (slug,)).fetchone()[0]
        out.append([b.firm.name, b.firm.industry, b.stats['sources'],
                    sum(b.stats['records_per_source'].values()), int(entities), b.stats['assertions'],
                    b.stats['relation_types_used'], len(tk.by_firm(slug))])
    return {'columns': cols, 'rows': out, 'bold': [],
            'align': ['l', 'l', 'r', 'r', 'r', 'r', 'r', 'r'],
            'caption': 'The three firms as they arrive: source exports in, entities and assertions out. '
                       'Entities can outnumber records because one record can mint two: a customer row '
                       'is a party and its credit terms, a product row is a product and its stock '
                       'position, a sale is an order and its line. Relation types in use counts the '
                       'relation predicates that carry at least one edge. Every record is generated by '
                       'a seeded script and every figure here is computed from the build, not recorded '
                       'by hand.'}


def schema_counts() -> dict:
    from .firms import FIRMS
    from .schema import core, shared_and_local
    cols = ['Firm', 'Core entity types', 'Core relation types', 'Extension entity types',
            'Extension relation types']
    schemas, out = [], []
    for slug in FIRM_LABEL:
        s = FIRMS[slug][1](core())
        schemas.append(s)
        c = s.counts()
        ext = {k: v for k, v in c.items() if k != 'core'}
        out.append([FIRM_LABEL[slug], c.get('core', {}).get('entities', 0),
                    c.get('core', {}).get('relations', 0),
                    sum(v['entities'] for v in ext.values()),
                    sum(v['relations'] for v in ext.values())])
    sl = shared_and_local(schemas)
    out.append(['All three: core shared, extensions summed', sl['shared_entities'],
                sl['shared_relations'], sl['local_entities'], sl['local_relations']])
    return {'columns': cols, 'rows': out, 'bold': [], 'align': ['l', 'r', 'r', 'r', 'r'],
            'caption': 'The schema each firm was built with: the core every firm starts from, and the '
                       'types its industry extension added. In the last row the core columns count the '
                       'types present in all three schemas and the extension columns sum the three '
                       'extensions. The core is shared by construction, since one function emits it for '
                       'every firm.'}


# ---- the charts ------------------------------------------------------------------------

def _rc():
    import matplotlib
    matplotlib.use('svg')
    rc = matplotlib.rcParams
    rc['svg.fonttype'] = 'none'
    rc['font.family'] = 'sans-serif'
    rc['font.sans-serif'] = ['Helvetica', 'Arial', 'DejaVu Sans']
    rc['font.size'] = 8.5
    rc['text.color'] = pal.INK
    rc['axes.labelcolor'] = pal.INK
    rc['axes.edgecolor'] = pal.GREY
    rc['axes.titlecolor'] = pal.INK
    rc['xtick.color'] = pal.INK
    rc['ytick.color'] = pal.INK
    rc['xtick.labelcolor'] = pal.INK
    rc['ytick.labelcolor'] = pal.INK
    rc['axes.facecolor'] = pal.PAPER
    rc['figure.facecolor'] = pal.PAPER
    rc['figure.edgecolor'] = pal.PAPER
    rc['savefig.facecolor'] = pal.PAPER
    rc['savefig.edgecolor'] = pal.PAPER
    rc['axes.grid'] = False
    rc['legend.frameon'] = False
    rc['legend.labelcolor'] = pal.INK
    rc['patch.edgecolor'] = pal.PAPER
    rc['lines.color'] = pal.INK
    rc['hatch.color'] = pal.INK
    return matplotlib


def _fig(width: float = 5.6, height: float = 2.4):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(width, height), dpi=100)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(pal.GREY)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(length=2.5, width=0.8, colors=pal.INK)
    return fig, ax


_HEX = re.compile(r'#[0-9a-fA-F]{6}')


def _save(fig, charts_dir: Path, name: str, caption: str) -> Path:
    import matplotlib.pyplot as plt
    charts_dir = Path(charts_dir)
    charts_dir.mkdir(parents=True, exist_ok=True)
    p = charts_dir / f'{name}.svg'
    fig.savefig(p, format='svg', bbox_inches='tight', metadata={'Date': None})
    plt.close(fig)
    svg = p.read_text(encoding='utf-8')
    svg = re.sub(r'<\?xml[^>]*\?>\s*', '', svg)
    svg = re.sub(r'<!DOCTYPE[^>]*>\s*', '', svg)
    svg = re.sub(r'<metadata>.*?</metadata>\s*', '', svg, flags=re.S)
    svg = _HEX.sub(lambda m: m.group(0).lower(), svg).strip()
    for c in set(_HEX.findall(svg)):
        if c not in pal.ALL:
            raise ValueError(f'{name}.svg: colour {c} is not in the palette')
    p.write_text(svg + '\n', encoding='utf-8')
    (charts_dir / f'{name}.caption.txt').write_text(caption.strip() + '\n', encoding='utf-8')
    return p


def _bar_labels(ax, bars, suffix=''):
    for b in bars:
        h = b.get_height()
        if h is None:
            continue
        ax.text(b.get_x() + b.get_width() / 2, h + 1.5, f'{h:g}{suffix}', ha='center', va='bottom',
                fontsize=7.5, color=pal.INK)


def _legend(ax, pairs: list[tuple[str, str]], **kw) -> None:
    """A legend built from explicit swatches. matplotlib takes a legend entry's colour
    from a patch, so a series with nothing to draw is given its default blue instead of
    ours; with an absent arm that is exactly the case, and the palette gate then fails."""
    from matplotlib.patches import Patch
    if not pairs:
        return
    handles = [Patch(facecolor=colour, edgecolor=pal.PAPER, label=label) for label, colour in pairs]
    ax.legend(handles=handles, **kw)


def chart_pass_by_arm(rows: list[dict], charts_dir: Path) -> None:
    _rc()
    import numpy as np
    fig, ax = _fig()
    firms = list(FIRM_LABEL)
    x = np.arange(len(firms))
    width = 0.26
    for i, arm in enumerate(ARMS):
        # A firm with no runs is left out of the row rather than drawn at zero: an
        # absence and a total failure are different facts and must not look alike.
        vals = [_pass(_pick(rows, arm=arm, ablation='none', firm=f), 1) for f in firms]
        keep = [j for j, v in enumerate(vals) if v is not None]
        if not keep:
            continue
        bars = ax.bar([x[j] + (i - 1) * width for j in keep], [vals[j] for j in keep], width,
                      color=ARM_COLOUR[arm], edgecolor=pal.PAPER, linewidth=0.5)
        _bar_labels(ax, bars)
    ax.set_xticks(x, [FIRM_LABEL[f] for f in firms])
    ax.set_ylabel('pass^1 (%)')
    ax.set_ylim(0, 108)
    _legend(ax, [(ARM_LABEL[a], ARM_COLOUR[a]) for a in ARMS],
            loc='upper center', bbox_to_anchor=(0.5, 1.18), ncol=3, fontsize=8)
    got = {a: _pass(_pick(rows, arm=a, ablation='none'), 1) for a in ARMS}
    if all(v is not None for v in got.values()):
        tail = (f'Over the whole suite the raw tables pass {got["A"]:g}% of trials, the metric layer '
                f'{got["B"]:g}% and the ontology {got["C"]:g}%.')
    else:
        tail = ('Arms with no runs in this result set are left out rather than drawn at zero: '
                + ', '.join(ARM_LABEL[a] for a, v in got.items() if v is None) + ' not yet run.')
    _save(fig, charts_dir, 'pass_by_arm', 'pass^1 by arm for each firm. ' + tail)


def chart_pass_hat_k(rows: list[dict], charts_dir: Path) -> None:
    _rc()
    fig, ax = _fig(5.6, 2.2)
    kmax = max((_trials(_pick(rows, arm=a, ablation='none')) for a in ARMS), default=0)
    ks = list(range(1, max(kmax, 1) + 1))
    drawn = []
    for arm in ARMS:
        live = _pick(rows, arm=arm, ablation='none')
        vals = [_pass(live, k) for k in ks]
        if any(v is None for v in vals):
            continue
        ax.plot(ks, vals, marker='o', markersize=4, color=ARM_COLOUR[arm], linewidth=1.4)
        drawn.append(arm)
    ax.set_xticks(ks, [f'k={k}' for k in ks])
    ax.set_ylabel('pass^k (%)')
    ax.set_ylim(0, 105)
    _legend(ax, [(ARM_LABEL[a], ARM_COLOUR[a]) for a in drawn],
            loc='upper center', bbox_to_anchor=(0.5, 1.2), ncol=3, fontsize=8)
    last = ks[-1]
    drop = {a: round((_pass(_pick(rows, arm=a, ablation='none'), 1) or 0.0)
                     - (_pass(_pick(rows, arm=a, ablation='none'), last) or 0.0), 2) for a in drawn}
    tail = '; '.join(f'{drop[a]:g} points for arm {a}' for a in drawn) or 'no arm has been run yet'
    _save(fig, charts_dir, 'pass_hat_k',
          f'pass^k for k = 1 to {last}: the share of tasks that pass on every one of k independent '
          f'trials. The gap between k=1 and k={last} is the cost of inconsistency, {tail}.')


def chart_failures(rows: list[dict], charts_dir: Path) -> None:
    _rc()
    fig, ax = _fig(5.6, 2.2)
    classes = [c for c in FAILURE_COLOUR
               if any((r['score'].get('failure') or '') == c for r in rows if r['ablation'] == 'none')]
    y = list(range(len(ARMS)))
    left = [0.0] * len(ARMS)
    for c in classes:
        vals = []
        for arm in ARMS:
            live = _pick(rows, arm=arm, ablation='none')
            vals.append(sum(1 for r in live if (r['score'].get('failure') or '') == c))
        ax.barh(y, vals, left=left, height=0.5, color=FAILURE_COLOUR[c],
                edgecolor=pal.PAPER, linewidth=0.5)
        left = [a + b for a, b in zip(left, vals)]
    ax.set_yticks(y, [ARM_LABEL[a] for a in ARMS])
    ax.invert_yaxis()
    ax.set_xlabel('failed runs')
    _legend(ax, [(c.replace('_', ' '), FAILURE_COLOUR[c]) for c in classes],
            loc='upper center', bbox_to_anchor=(0.5, 1.28), ncol=min(4, max(1, len(classes))),
            fontsize=7.5)
    total = int(sum(left))
    _save(fig, charts_dir, 'failures',
          f'How the {total} failed runs failed, by arm. A run fails on the first dimension it loses, so each '
          'run appears once.')


def chart_ablations(rows: list[dict], charts_dir: Path) -> None:
    """Paired bars: for each removal, the ablated model and the full model on the same
    probe tasks, side by side, ordered by the difference. An unpaired bar would invite a
    comparison across rows that the differing task sets do not support."""
    _rc()
    import numpy as np
    fig, ax = _fig(5.6, 2.3)
    drawn = [d for d in _ablation_rows(rows)
             if d['ablation'] != 'none' and d['pass1'] is not None and d['baseline'] is not None]
    if drawn:
        x = np.arange(len(drawn))
        width = 0.36
        full = ax.bar(x - width / 2, [d['baseline'] for d in drawn], width, color=pal.ROLE['agent'],
                      edgecolor=pal.PAPER, linewidth=0.5)
        cut = ax.bar(x + width / 2, [d['pass1'] for d in drawn], width, color=pal.ROLE['fail'],
                     edgecolor=pal.PAPER, linewidth=0.5)
        _bar_labels(ax, full)
        _bar_labels(ax, cut)
        ax.set_xticks(x, [f'{ABLATION_LABEL[d["ablation"]]}\n({d["targets"]} tasks)' for d in drawn])
        _legend(ax, [('full model, same tasks', pal.ROLE['agent']), ('with the part removed', pal.ROLE['fail'])],
                loc='upper center', bbox_to_anchor=(0.5, 1.2), ncol=2, fontsize=8)
    ax.set_ylabel('pass^1 (%)')
    ax.set_ylim(0, 112)
    if drawn:
        worst = min(drawn, key=lambda d: d['delta'])
        tail = (f'The largest like-for-like loss is {ABLATION_LABEL[worst["ablation"]]}, '
                f'{worst["delta"]:+g} points on its {worst["targets"]} probe tasks; at one trial per task '
                'a single run moves a bar by a third or more, so the differences are reported as noise.')
    else:
        tail = 'No ablation has been run into this result set yet, so nothing is drawn.'
    _save(fig, charts_dir, 'ablations',
          'Arm C with one part of the model removed, each paired with the full model on the same '
          'probe tasks and ordered by the difference. ' + tail)


# ---- the summary --------------------------------------------------------------------------

def _calendar_used(rec: dict) -> bool | None:
    """Did any tool call in this run carry the calendar date the run was made on?

    The runtime the agent ran under knows the machine's date; our prompt names the firm's.
    A run that wrote the machine's date into a query was reasoning on the wrong calendar,
    and the paper has to be able to count that rather than describe it. None when the
    run's log is not on disk (a synthetic record in a test)."""
    from . import trajectory as tj
    try:
        traj = tj.load(rec['hash'], tj.LOGS_DIR)
    except (FileNotFoundError, KeyError, ValueError):
        return None
    when = rec.get('date') or ''
    return bool(when) and any(when in t.text for t in traj.turns if t.kind == 'tool_call')


def _max_turns(rows: list[dict]) -> int | None:
    """The turn cap the runs were made under, read from their logs; None without logs."""
    from . import trajectory as tj
    caps = set()
    for r in rows:
        try:
            caps.add(int(tj.load(r['hash'], tj.LOGS_DIR).meta.get('max_turns') or 0))
        except (FileNotFoundError, KeyError, ValueError):
            return None
    return max(caps) if caps else None


def summary(rows: list[dict]) -> dict:
    from .firms import FIRMS
    from .schema import core, shared_and_local
    live = [r for r in rows if r['ablation'] == 'none']
    out: dict = {
        'runs_total': len(rows),
        'runs_unablated': len(live),
        'tasks_total': len(tk.TASKS),
        'firms_total': len(FIRM_LABEL),
        'cost_total_usd': round(sum(float(r.get('cost_usd') or 0.0) for r in rows), 4),
        'model': sorted({r['model'] for r in rows})[0] if rows else '',
        # A run cut off at the turn cap is a different fact from a run that reasoned
        # badly, so the paper can report cap hits rather than leave them inside the
        # failure rate looking like the arm's fault.
        'runs_ablation': len(rows) - len(live),
        'runs_failed': sum(1 for r in live if not r['score'].get('R')),
        'runs_capped': sum(1 for r in rows if r.get('ended_by') == 'max_turns'),
        'runs_capped_ablations': sum(1 for r in rows
                                     if r['ablation'] != 'none' and r.get('ended_by') == 'max_turns'),
        'max_turns': _max_turns(rows),
        'runs_long': sum(1 for r in rows if int(r.get('num_turns') or 0) >= (_max_turns(rows) or 40)),
        'runs_long_ablations': sum(1 for r in rows if r['ablation'] != 'none'
                                   and int(r.get('num_turns') or 0) >= (_max_turns(rows) or 40)),
        'run_dates': ', '.join(sorted({r.get('date') or '' for r in rows} - {''})),
    }
    ks = []
    for arm in ARMS:
        # None, never zero, for an arm or firm with no runs: the paper must not be able to
        # quote a pass rate for something nobody ran.
        a = _pick(live, arm=arm)
        k = _trials(a)
        if k:
            ks.append(k)
        out[f'k_{arm}'] = k or None
        out[f'pass1_{arm}'] = _pass(a, 1)
        out[f'passk_{arm}'] = _pass(a, k) if k else None
        costs = [float(r.get('cost_usd') or 0.0) for r in a]
        out[f'cost_mean_{arm}'] = round(sum(costs) / len(costs), 4) if costs else None
        turns = [int(r.get('num_turns') or 0) for r in a]
        out[f'turns_mean_{arm}'] = round(sum(turns) / len(turns), 2) if turns else None
        # attributed by arm, so a count of capped runs cannot be read as one arm's fault
        out[f'runs_capped_{arm}'] = sum(1 for r in a if r.get('ended_by') == 'max_turns')
        # runs whose turn count by the runtime's reckoning reached the cap and that the
        # runtime nonetheless reported as completed: a fact about the count, not the cap
        out[f'runs_long_{arm}'] = sum(1 for r in a if int(r.get('num_turns') or 0) >= (out.get('max_turns') or 40))
        out[f'runs_failed_{arm}'] = sum(1 for r in a if not r['score'].get('R'))
        for cls in sc.FAILURES[1:]:
            out[f'fail_{arm}_{cls}'] = sum(1 for r in a if (r['score'].get('failure') or '') == cls)
        used = [_calendar_used(r) for r in a]
        out[f'runs_calendar_date_{arm}'] = (sum(1 for u in used if u)
                                            if a and all(u is not None for u in used) else None)
        for f in FIRM_LABEL:
            out[f'pass1_{arm}_{f}'] = _pass(_pick(a, firm=f), 1)
    if out.get('cost_mean_A') and out.get('cost_mean_C'):
        out['cost_ratio_C_over_A'] = round(out['cost_mean_C'] / out['cost_mean_A'], 2)
        out['cost_ratio_C_over_B'] = round(out['cost_mean_C'] / out['cost_mean_B'], 2) if out.get('cost_mean_B') else None
    else:
        out['cost_ratio_C_over_A'] = out['cost_ratio_C_over_B'] = None
    if out.get('turns_mean_A') and out.get('turns_mean_C'):
        out['turns_ratio_C_over_A'] = round(out['turns_mean_C'] / out['turns_mean_A'], 2)
    else:
        out['turns_ratio_C_over_A'] = None
    # the k the whole table can support: no arm ran fewer trials than this
    out['k'] = min(ks) if ks else 0
    for ab in ABLATIONS[1:]:
        # None, not zero, when an ablation has not been run: the paper must not be able to
        # quote a pass rate for an experiment nobody performed.
        ids = {t.id for t in tk.TASKS if ab in t.targets}
        got = _pass([r for r in rows if r['arm'] == 'C' and r['ablation'] == ab and r['task'] in ids], 1)
        base = _pass([r for r in live if r['arm'] == 'C' and r['task'] in ids], 1)
        out[f'pass1_C_{ab}'] = got
        out[f'pass1_C_{ab}_baseline'] = base
        out[f'delta_{ab}'] = None if got is None or base is None else round(got - base, 2)
    schemas = [FIRMS[slug][1](core()) for slug in FIRM_LABEL]
    sl = shared_and_local(schemas)
    totals = [len(s.entities) + len(s.relations) for s in schemas]
    out['shared_core_types'] = sl['shared_entities'] + sl['shared_relations']
    out['shared_core_pct'] = round(100.0 * out['shared_core_types'] / (sum(totals) / len(totals)), 2)
    out['local_types_total'] = sl['local_entities'] + sl['local_relations']
    return out


def main(results_dir: Path | str = RESULTS_DIR, charts_dir: Path | str = CHARTS_DIR) -> dict:
    results_dir, charts_dir = Path(results_dir), Path(charts_dir)
    rows, duplicates = load_runs(results_dir)
    _write_table(results_dir, 'main_results', main_results(rows))
    _write_table(results_dir, 'by_kind', by_kind(rows))
    _write_table(results_dir, 'ablations', ablations(rows))
    _write_table(results_dir, 'per_task', per_task(rows))
    _write_table(results_dir, 'firm_stats', firm_stats())
    _write_table(results_dir, 'schema_counts', schema_counts())
    chart_pass_by_arm(rows, charts_dir)
    chart_pass_hat_k(rows, charts_dir)
    chart_failures(rows, charts_dir)
    chart_ablations(rows, charts_dir)
    s = summary(rows)
    s['duplicate_records_dropped'] = duplicates
    (results_dir / 'summary.json').write_text(json.dumps(s, indent=1, sort_keys=True) + '\n',
                                              encoding='utf-8')
    if duplicates:
        print(f'dropped {duplicates} duplicate run records, keeping the newest of each')
    return s


if __name__ == '__main__':
    out = main()
    print(json.dumps(out, indent=1, sort_keys=True))
