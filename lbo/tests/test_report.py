import json
import re

from lbo import report as rp
from lbo.palette import ALL

TASKS = (('r_price_ok', 'retail'), ('f_certified_techs', 'fieldservice'), ('d_losing_route', 'distributor'))


def _fake_runs(tmp_path):
    runs = tmp_path / 'runs'
    runs.mkdir()
    i = 0
    for arm in 'ABC':
        for task, firm in TASKS:
            for seed in range(3):
                i += 1
                ok = (arm == 'C') or (seed == 0)
                (runs / f'{i:03d}.json').write_text(json.dumps({
                    'hash': f'{i:012x}', 'task': task, 'firm': firm, 'arm': arm, 'ablation': 'none',
                    'model': 'm', 'seed_index': seed,
                    'score': {'S': int(ok), 'P': 1, 'E': 1, 'C': 1, 'R': int(ok),
                              'failure': '' if ok else 'wrong_number', 'notes': []},
                    'cost_usd': 0.05, 'num_turns': 6, 'date': '2026-09-28'}))
    return tmp_path


def test_report_writes_tables_charts_and_summary(tmp_path):
    root = _fake_runs(tmp_path)
    charts = tmp_path / 'charts'
    charts.mkdir()
    summary = rp.main(results_dir=root, charts_dir=charts)
    t = json.loads((root / 'tables' / 'main_results.json').read_text())
    assert t['columns'][0] == 'Arm' and len(t['rows']) == 3
    assert summary['pass1_C'] == 100.0 and summary['passk_C'] == 100.0
    assert summary['k'] == 3 and summary['k_C'] == 3
    assert (charts / 'pass_by_arm.svg').exists() and (charts / 'pass_by_arm.caption.txt').read_text().strip()
    svg = (charts / 'pass_by_arm.svg').read_text()
    for c in re.findall(r'#[0-9a-fA-F]{6}', svg):
        assert c.lower() in ALL, c


def test_every_table_and_chart_the_paper_reads_is_written(tmp_path):
    root = _fake_runs(tmp_path)
    charts = tmp_path / 'charts'
    charts.mkdir()
    rp.main(results_dir=root, charts_dir=charts)
    for name in ('main_results', 'by_kind', 'ablations', 'firm_stats', 'schema_counts', 'per_task'):
        spec = json.loads((root / 'tables' / f'{name}.json').read_text())
        assert spec['columns'] and spec['rows'] and spec['caption'], name
        assert all(len(r) == len(spec['columns']) for r in spec['rows']), name
        for r, c in spec.get('bold', []):
            assert 0 <= r < len(spec['rows']) and 0 <= c < len(spec['columns']), name
    for name in ('pass_by_arm', 'pass_hat_k', 'failures', 'ablations'):
        svg = (charts / f'{name}.svg').read_text()
        assert svg.startswith('<svg') and '<metadata' not in svg, name
        assert (charts / f'{name}.caption.txt').read_text().strip(), name
        for c in re.findall(r'#[0-9a-fA-F]{6}', svg):
            assert c.lower() in ALL, (name, c)


def test_the_summary_carries_what_the_paper_quotes(tmp_path):
    root = _fake_runs(tmp_path)
    charts = tmp_path / 'charts'
    charts.mkdir()
    s = rp.main(results_dir=root, charts_dir=charts)
    for k in ('pass1_A', 'pass1_B', 'pass1_C', 'passk_A', 'passk_C', 'k_A', 'runs_total',
              'cost_total_usd', 'model', 'k', 'shared_core_pct', 'tasks_total', 'firms_total',
              'runs_capped', 'duplicate_records_dropped', 'runs_capped_A', 'runs_capped_C',
              'turns_mean_A', 'turns_mean_C', 'cost_ratio_C_over_A', 'fail_A_wrong_number',
              'runs_failed_A', 'runs_calendar_date_A'):
        assert k in s, k
    assert s['runs_capped'] == 0 and s['runs_capped_A'] == 0
    assert s['turns_mean_A'] == 6.0 and s['cost_ratio_C_over_A'] == 1.0
    assert s['fail_A_wrong_number'] == 6 and s['runs_failed_A'] == 6 and s['fail_C_wrong_number'] == 0
    assert s['runs_calendar_date_A'] is None, 'no logs on disk for a synthetic record'
    assert s['runs_total'] == 27 and s['k'] == 3 and s['model'] == 'm'
    assert round(s['pass1_A'], 2) == 33.33 and s['passk_A'] == 0.0
    assert s['cost_total_usd'] == round(27 * 0.05, 4)
    assert json.loads((root / 'summary.json').read_text()) == s
    assert all(not isinstance(v, (dict, list)) for v in s.values()), 'summary keys must be flat'


def test_an_unrun_ablation_is_blank_rather_than_zero(tmp_path):
    root = _fake_runs(tmp_path)
    charts = tmp_path / 'charts'
    charts.mkdir()
    s = rp.main(results_dir=root, charts_dir=charts)
    assert s['pass1_C_no_time'] is None and s['delta_no_time'] is None
    ab = json.loads((root / 'tables' / 'ablations.json').read_text())
    assert [r[2] for r in ab['rows'][1:]] == ['', '', '', '']
    assert 'No ablation has been run' in (charts / 'ablations.caption.txt').read_text()


def test_ablation_runs_land_in_the_table_the_chart_and_the_delta(tmp_path):
    root = _fake_runs(tmp_path)
    runs = root / 'runs'
    i = 900
    for seed in range(3):
        i += 1
        (runs / f'{i:03d}.json').write_text(json.dumps({
            'hash': f'{i:012x}', 'task': 'f_certified_techs', 'firm': 'fieldservice', 'arm': 'C',
            'ablation': 'no_time', 'model': 'm', 'seed_index': seed,
            'score': {'S': 0, 'P': 1, 'E': 1, 'C': 1, 'R': 0, 'failure': 'wrong_entity', 'notes': []},
            'cost_usd': 0.04, 'num_turns': 5, 'date': '2026-09-28'}))
    charts = tmp_path / 'charts'
    charts.mkdir()
    s = rp.main(results_dir=root, charts_dir=charts)
    assert s['pass1_C_no_time'] == 0.0 and s['pass1_C_no_time_baseline'] == 100.0
    assert s['delta_no_time'] == -100.0
    ab = json.loads((root / 'tables' / 'ablations.json').read_text())
    row = next(r for r in ab['rows'] if r[0] == 'no time')
    assert row[2] == '0' and row[3] == '100' and row[4] == '-100' and row[5] == 'wrong entity'
    assert 'largest like-for-like loss is no time' in (charts / 'ablations.caption.txt').read_text()


def test_a_partial_result_set_reports_absence_rather_than_zero(tmp_path):
    # One run, on one arm, on one firm: every other cell is an absence. Matplotlib gives
    # a series with nothing to draw its own default blue, which is how this was found.
    runs = tmp_path / 'runs'
    runs.mkdir()
    (runs / 'a.json').write_text(json.dumps({
        'hash': 'a' * 12, 'task': 'r_price_ok', 'firm': 'retail', 'arm': 'C', 'ablation': 'none',
        'model': 'm', 'seed_index': 0,
        'score': {'S': 1, 'P': 1, 'E': 1, 'C': 1, 'R': 1, 'failure': '', 'notes': []},
        'cost_usd': 0.05, 'num_turns': 4, 'date': '2026-09-28'}))
    charts = tmp_path / 'charts'
    charts.mkdir()
    s = rp.main(results_dir=tmp_path, charts_dir=charts)
    assert s['pass1_C'] == 100.0
    assert s['pass1_A'] is None and s['passk_A'] is None and s['cost_mean_A'] is None
    assert s['k_A'] is None and s['k_C'] == 1, 'k is what was actually run'
    assert s['pass1_C_fieldservice'] is None
    main = json.loads((tmp_path / 'tables' / 'main_results.json').read_text())
    assert main['rows'][0][1:] == [''] * 6
    ab = json.loads((tmp_path / 'tables' / 'ablations.json').read_text())
    assert ab['rows'][0][1] == '1/25'
    for name in ('pass_by_arm', 'pass_hat_k', 'failures', 'ablations'):
        for c in re.findall(r'#[0-9a-fA-F]{6}', (charts / f'{name}.svg').read_text()):
            assert c.lower() in ALL, (name, c)


def test_the_firm_and_schema_tables_describe_the_three_firms(tmp_path):
    root = _fake_runs(tmp_path)
    charts = tmp_path / 'charts'
    charts.mkdir()
    rp.main(results_dir=root, charts_dir=charts)
    firms = json.loads((root / 'tables' / 'firm_stats.json').read_text())
    assert len(firms['rows']) == 3
    assert all(isinstance(r[3], int) and r[3] > 0 for r in firms['rows'])
    schema = json.loads((root / 'tables' / 'schema_counts.json').read_text())
    assert len(schema['rows']) == 4 and 'core shared' in schema['rows'][-1][0]


def test_runs_cut_off_at_the_turn_cap_are_counted_separately(tmp_path):
    # A capped run and a badly reasoned run both show up as R=0; the paper has to be able
    # to tell them apart, so the count comes out of the records rather than the prose.
    root = _fake_runs(tmp_path)
    (root / 'runs' / '900.json').write_text(json.dumps({
        'hash': '9' * 12, 'task': 'r_price_ok', 'firm': 'retail', 'arm': 'A', 'ablation': 'none',
        'model': 'm', 'seed_index': 0, 'ended_by': 'max_turns',
        'score': {'S': 0, 'P': 1, 'E': 1, 'C': 1, 'R': 0, 'failure': 'no_answer', 'notes': []},
        'cost_usd': 0.5, 'num_turns': 40, 'date': '2026-09-28'}))
    charts = tmp_path / 'charts'
    charts.mkdir()
    s = rp.main(results_dir=root, charts_dir=charts)
    assert s['runs_capped'] == 1 and s['runs_capped_A'] == 1 and s['runs_capped_C'] == 0


def _rec(runs, name, task, arm, seed, r=1, ablation='none'):
    (runs / name).write_text(json.dumps({
        'hash': name[:-5], 'task': task, 'firm': 'retail', 'arm': arm, 'ablation': ablation,
        'model': 'm', 'seed_index': seed, 'ended_by': 'completed', 'cost_usd': 0.1, 'num_turns': 5,
        'score': {'S': r, 'P': 1, 'E': 1, 'C': 1, 'R': r, 'failure': '' if r else 'wrong_number',
                  'notes': []}, 'date': '2026-09-28'}))


def test_pass_k_is_labelled_by_the_trials_that_were_actually_run(tmp_path):
    # Two trials per task, not three: pass^k has to mean what was run, or the column is a
    # claim about an experiment nobody performed.
    runs = tmp_path / 'runs'
    runs.mkdir()
    for seed in (0, 1):
        _rec(runs, f'a{seed}.json', 'r_price_ok', 'C', seed, r=1)
        _rec(runs, f'b{seed}.json', 'r_price_ok', 'A', seed, r=1 if seed == 0 else 0)
    charts = tmp_path / 'charts'
    charts.mkdir()
    s = rp.main(results_dir=tmp_path, charts_dir=charts)
    assert s['k'] == 2 and s['k_C'] == 2 and s['k_A'] == 2
    assert s['passk_C'] == 100.0 and s['passk_A'] == 0.0
    t = json.loads((tmp_path / 'tables' / 'main_results.json').read_text())
    assert t['columns'][5] == 'Both trials passed' and 'every task ran 2 times' in t['caption']
    assert 'pass^3' not in json.dumps(t)


def test_a_rerun_does_not_let_one_task_vote_twice(tmp_path):
    # A second attempt writes a new file, because a file is named by the hash of its
    # turns. Counting both would weight that task double.
    import os
    import time
    runs = tmp_path / 'runs'
    runs.mkdir()
    _rec(runs, 'old.json', 'r_price_ok', 'C', 0, r=0)
    time.sleep(0.01)
    _rec(runs, 'new.json', 'r_price_ok', 'C', 0, r=1)
    os.utime(runs / 'new.json', (time.time() + 10, time.time() + 10))
    rows, dropped = rp.load_runs(tmp_path)
    assert dropped == 1 and len(rows) == 1 and rows[0]['score']['R'] == 1
    charts = tmp_path / 'charts'
    charts.mkdir()
    s = rp.main(results_dir=tmp_path, charts_dir=charts)
    assert s['duplicate_records_dropped'] == 1 and s['runs_total'] == 1 and s['pass1_C'] == 100.0
