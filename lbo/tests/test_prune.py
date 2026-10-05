import json

from lbo import prune as pr


def _record(tmp_path, h, task, ended_by, arm='C', seed=0, with_log=True):
    runs = tmp_path / 'runs'
    logs = tmp_path / 'logs'
    runs.mkdir(exist_ok=True)
    logs.mkdir(exist_ok=True)
    (runs / f'{h}.json').write_text(json.dumps({
        'hash': h, 'task': task, 'firm': 'retail', 'arm': arm, 'ablation': 'none', 'model': 'm',
        'seed_index': seed, 'ended_by': ended_by, 'cost_usd': 0.1, 'num_turns': 9,
        'score': {'S': 1, 'P': 1, 'E': 1, 'C': 1, 'R': 1, 'failure': '', 'notes': []},
        'date': '2026-09-28'}))
    if with_log:
        (logs / f'{h}.json').write_text(json.dumps({'firm': 'retail', 'turns': []}))


def _names(tmp_path, sub):
    return sorted(p.stem for p in (tmp_path / sub).glob('*.json'))


def test_prune_removes_by_task_and_by_ending_and_leaves_the_rest(tmp_path):
    _record(tmp_path, 'a' * 12, 'r_like_for_like', 'completed')
    _record(tmp_path, 'b' * 12, 'r_price_ok', 'max_budget')
    _record(tmp_path, 'c' * 12, 'r_price_ok', 'error')
    _record(tmp_path, 'd' * 12, 'r_price_ok', 'completed')
    _record(tmp_path, 'e' * 12, 'd_concentration', 'max_turns')
    out = pr.prune(tmp_path, tmp_path / 'logs', tasks=('r_like_for_like',),
                   ended_by=('max_budget', 'error'))
    assert len(out['removed']) == 3 and out['kept'] == 2
    assert _names(tmp_path, 'runs') == ['d' * 12, 'e' * 12]
    assert _names(tmp_path, 'logs') == ['d' * 12, 'e' * 12]
    assert {r['why'] for r in out['removed']} == {'task r_like_for_like', 'ended_by max_budget',
                                                  'ended_by error'}


def test_prune_with_no_filter_removes_nothing(tmp_path):
    # the command must not be able to empty the result set by being run bare
    _record(tmp_path, 'a' * 12, 'r_price_ok', 'completed')
    out = pr.prune(tmp_path, tmp_path / 'logs')
    assert out['removed'] == [] and out['error']
    assert _names(tmp_path, 'runs') == ['a' * 12]
    assert pr.main(['--results-dir', str(tmp_path), '--logs-dir', str(tmp_path / 'logs')]) == 2


def test_a_dry_run_reports_without_deleting(tmp_path):
    _record(tmp_path, 'a' * 12, 'r_like_for_like', 'completed')
    out = pr.prune(tmp_path, tmp_path / 'logs', tasks=('r_like_for_like',), dry_run=True)
    assert len(out['removed']) == 1
    assert _names(tmp_path, 'runs') == ['a' * 12] and _names(tmp_path, 'logs') == ['a' * 12]


def test_a_record_whose_log_is_gone_is_still_removed_and_said_so(tmp_path):
    _record(tmp_path, 'a' * 12, 'r_like_for_like', 'completed', with_log=False)
    out = pr.prune(tmp_path, tmp_path / 'logs', tasks=('r_like_for_like',))
    assert out['removed'][0]['had_log'] is False
    assert _names(tmp_path, 'runs') == []


def test_the_cli_parses_comma_and_space_separated_filters(tmp_path):
    _record(tmp_path, 'a' * 12, 'r_like_for_like', 'completed')
    _record(tmp_path, 'b' * 12, 'r_price_ok', 'max_budget')
    assert pr.main(['--tasks', 'r_like_for_like', '--ended-by', 'max_budget,error',
                    '--results-dir', str(tmp_path), '--logs-dir', str(tmp_path / 'logs')]) == 0
    assert _names(tmp_path, 'runs') == []


def test_arms_and_kinds_restrict_rather_than_select(tmp_path):
    # `--arms A B --kinds action,refusal` means runs on those arms of those kinds, not
    # every run on those arms and every run of those kinds.
    _record(tmp_path, 'a' * 12, 'r_price_ok', 'completed', arm='A')          # action
    _record(tmp_path, 'b' * 12, 'r_price_refusal', 'completed', arm='B')     # refusal
    _record(tmp_path, 'c' * 12, 'r_margin_two_hops', 'completed', arm='A')   # question, stays
    _record(tmp_path, 'd' * 12, 'r_price_ok', 'completed', arm='C')          # arm C, stays
    out = pr.prune(tmp_path, tmp_path / 'logs', arms=('A', 'B'), kinds=('action', 'refusal'))
    assert len(out['removed']) == 2 and out['kept'] == 2
    assert _names(tmp_path, 'runs') == ['c' * 12, 'd' * 12]
    assert _names(tmp_path, 'logs') == ['c' * 12, 'd' * 12]


def test_a_restriction_narrows_a_selection(tmp_path):
    _record(tmp_path, 'a' * 12, 'r_price_ok', 'max_budget', arm='A')
    _record(tmp_path, 'b' * 12, 'r_price_ok', 'max_budget', arm='C')
    out = pr.prune(tmp_path, tmp_path / 'logs', ended_by=('max_budget',), arms=('A',))
    assert len(out['removed']) == 1 and _names(tmp_path, 'runs') == ['b' * 12]


def test_a_task_the_suite_no_longer_carries_is_not_swept_up_by_a_kind(tmp_path):
    _record(tmp_path, 'a' * 12, 'retired_task', 'completed', arm='A')
    out = pr.prune(tmp_path, tmp_path / 'logs', arms=('A',), kinds=('action',))
    assert out['removed'] == [] and _names(tmp_path, 'runs') == ['a' * 12]


def test_the_cli_takes_arms_and_kinds(tmp_path):
    _record(tmp_path, 'a' * 12, 'r_price_ok', 'completed', arm='A')
    _record(tmp_path, 'b' * 12, 'r_margin_two_hops', 'completed', arm='A')
    assert pr.main(['--arms', 'A', 'B', '--kinds', 'action,refusal',
                    '--results-dir', str(tmp_path), '--logs-dir', str(tmp_path / 'logs')]) == 0
    assert _names(tmp_path, 'runs') == ['b' * 12]
