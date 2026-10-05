import json

import pytest

from lbo import harness as hz
from lbo import tasks as tk
from lbo.firms import FIRMS
from lbo.ingest import ingest


@pytest.fixture(scope='module')
def builds():
    return {s: ingest(FIRMS[s][0]()) for s in FIRMS}


def test_prepare_gives_each_arm_its_tools_and_a_private_store(builds):
    ctx, tools = hz.prepare(hz.RunSpec('r_price_ok', 'C'), builds)
    assert {t.name for t in tools} >= {'propose_action', 'execute_action'}
    assert ctx.store is not builds['retail'].store
    ctx2, _ = hz.prepare(hz.RunSpec('r_absent_supplier', 'C', ablation='no_identity'), builds)
    assert ctx2.store.count('retail') != builds['retail'].store.count('retail')


def test_prepare_gives_the_sql_arms_their_own_connection(builds):
    for arm, expected in (('A', 'describe_tables'), ('B', 'compute_metric')):
        ctx, tools = hz.prepare(hz.RunSpec('r_price_ok', arm), builds)
        assert expected in {t.name for t in tools}
        assert ctx.conn is not None


def test_run_key_is_idempotent():
    assert hz.run_key(hz.RunSpec('x', 'A', 'none', seed_index=2)) == ('x', 'A', 'none', 2)


def test_allowed_tools_are_all_prefixed(builds):
    _, tools = hz.prepare(hz.RunSpec('r_price_ok', 'C'), builds)
    allowed = hz.allowed_tools(tools)
    assert allowed and all(a.startswith('mcp__lbo__') for a in allowed)
    assert len(allowed) == len(tools)


def test_the_plan_of_runs_puts_ablations_on_arm_c_only():
    plan = hz.plan(arms=('A', 'B', 'C'), k=2, task_ids=None,
                   ablations=('none', 'no_authority'), model='m')
    assert all(s.arm == 'C' for s in plan if s.ablation != 'none')
    targets = {t.id for t in tk.TASKS if 'no_authority' in t.targets}
    assert {s.task_id for s in plan if s.ablation == 'no_authority'} == targets
    assert {s.seed_index for s in plan} == {0, 1}


def test_save_run_writes_a_result_record_and_a_trajectory(tmp_path, builds):
    from dataclasses import asdict
    from lbo.score import Score
    from lbo.trajectory import Trajectory, Turn
    traj = Trajectory(firm='retail', arm='C', task='r_price_ok', model='m', date='2026-09-28',
                      turns=[Turn(role='agent', kind='message', text='ANSWER: done')],
                      meta={'cost_usd': 0.02, 'num_turns': 3, 'seed_index': 0, 'ablation': 'none'})
    s = Score(1, 1, 1, 1, 1)
    p = hz.save_run(traj, s, tmp_path, logs_dir=tmp_path / 'logs')
    rec = json.loads(p.read_text())
    assert rec['task'] == 'r_price_ok' and rec['arm'] == 'C' and rec['score'] == asdict(s)
    assert rec['cost_usd'] == 0.02 and rec['hash'] == traj.hash()
    assert (tmp_path / 'logs' / f'{traj.hash()}.json').exists()
    assert hz.done_keys(tmp_path) == {('r_price_ok', 'C', 'none', 0)}


@pytest.mark.live
def test_one_live_run_on_the_cheapest_task(builds, tmp_path):
    traj, score = hz.run(hz.RunSpec('r_missing_manager', 'C', max_turns=12), builds)
    assert any(t.role == 'tool' for t in traj.turns)
    assert traj.meta['cost_usd'] < 0.5
    p = hz.save_run(traj, score, tmp_path, logs_dir=tmp_path / 'logs')
    assert p.exists()
    print('\nlive run:', json.dumps({'R': score.R, 'S': score.S, 'P': score.P, 'E': score.E, 'C': score.C,
                                     'failure': score.failure, 'cost_usd': traj.meta['cost_usd'],
                                     'num_turns': traj.meta['num_turns'],
                                     'turns_recorded': len(traj.turns)}, indent=1))
    print('final message:\n' + next(t.text for t in reversed(traj.turns)
                                    if t.role == 'agent' and t.kind == 'message'))
    print('notes:', score.notes)


def test_the_default_turn_cap_is_forty_everywhere():
    # The pilot's credit-hold run used all thirty turns and still answered correctly, so
    # the cap was measuring the cap, not the arm.
    assert hz.RunSpec('x', 'C').max_turns == 40
    assert all(s.max_turns == 40 for s in hz.plan(arms=('C',), k=1, task_ids=('r_price_ok',),
                                                  ablations=('none',), model='m'))


def test_the_default_budget_is_a_dollar_everywhere():
    # Two arm C margin runs ended on the budget at 25 and 41 turns, which measured the cap.
    assert hz.RunSpec('x', 'C').max_budget_usd == 1.0
    assert all(s.max_budget_usd == 1.0 for s in hz.plan(arms=('C',), k=1, task_ids=('r_price_ok',),
                                                        ablations=('none',), model='m'))


def test_ended_by_separates_a_finished_run_from_a_capped_one():
    assert hz._ended_by('success', 12, 40) == 'completed'
    assert hz._ended_by('success', 40, 40) == 'completed'      # the count is not the cap
    assert hz._ended_by('success', 66, 40) == 'completed'
    assert hz._ended_by('error_max_turns', 40, 40) == 'max_turns'
    assert hz._ended_by('error_max_budget', 9, 40) == 'max_budget'
    assert hz._ended_by('error_during_execution', 9, 40) == 'error'
    assert hz._ended_by('', 0, 40) == 'error'
    assert set(hz.ENDINGS) == {'completed', 'max_turns', 'max_budget', 'error'}


def test_the_run_record_carries_how_the_run_ended(tmp_path):
    from lbo.score import Score
    from lbo.trajectory import Trajectory, Turn
    traj = Trajectory(firm='retail', arm='C', task='r_price_ok', model='m', date='2026-09-28',
                      turns=[Turn(role='agent', kind='message', text='ANSWER: done')],
                      meta={'cost_usd': 0.02, 'num_turns': 40, 'seed_index': 0, 'ablation': 'none',
                            'ended_by': 'max_turns'})
    p = hz.save_run(traj, Score(1, 1, 1, 1, 1), tmp_path, logs_dir=tmp_path / 'logs')
    assert json.loads(p.read_text())['ended_by'] == 'max_turns'


def test_scrub_removes_local_paths_and_the_company_name():
    company = ''.join(chr(c) for c in (107, 105, 120, 105, 107))
    text = (f'Result written to /Users/someone/{company}/{company}-research-papers/research/lbo/x.json '
            f'(2,100 lines); see /home/ci/{company}-research-papers/out.txt too.')
    out = hz.scrub(text)
    assert '/Users/' not in out and '/home/' not in out
    assert company not in out.lower()
    assert out.count('<local path>') == 2
    assert hz.scrub('nothing to remove here') == 'nothing to remove here'


def test_a_saved_run_carries_no_local_path_and_hashes_what_was_saved(tmp_path):
    from lbo.score import Score
    from lbo.trajectory import Trajectory, Turn
    company = ''.join(chr(c) for c in (107, 105, 120, 105, 107))
    leaked = f'preview: /Users/someone/{company}/{company}-research-papers/research/lbo/big.json'
    traj = Trajectory(firm='retail', arm='C', task='r_price_ok', model='m', date='2026-09-28',
                      turns=[Turn(role='tool', kind='tool_result', name='run_sql', text=leaked),
                             Turn(role='agent', kind='message', text='ANSWER: done')],
                      meta={'cost_usd': 0.02, 'num_turns': 4, 'seed_index': 0, 'ablation': 'none',
                            'ended_by': 'completed',
                            'error': f'FileNotFoundError: /Users/someone/{company}/x'})
    p = hz.save_run(traj, Score(1, 1, 1, 1, 1), tmp_path, logs_dir=tmp_path / 'logs')
    saved = (tmp_path / 'logs' / f'{traj.hash()}.json').read_text()
    assert saved, 'the log is named by the hash of the scrubbed turns'
    for blob in (saved, p.read_text()):
        assert '/Users/' not in blob and company not in blob.lower()
    assert '<local path>' in saved
    assert json.loads(saved)['meta']['error'] == 'FileNotFoundError: <local path>'
    # the record and the log agree on identity, which only holds if both saw the scrub
    assert json.loads(p.read_text())['hash'] == traj.hash()


def test_every_saved_run_passes_the_company_sweep_the_package_is_held_to(tmp_path):
    import re as _re
    from lbo.score import Score
    from lbo.trajectory import Trajectory, Turn
    company = _re.compile(''.join(chr(c) for c in (107, 105, 120, 105, 107)), _re.I)
    traj = Trajectory(firm='retail', arm='C', task='r_price_ok', model='m', date='2026-09-28',
                      turns=[Turn(role='agent', kind='message',
                                  text=f'I read /Users/a/{company.pattern.upper()}-research-papers/f '
                                       f'and the {company.pattern.capitalize()} notes.')],
                      meta={'seed_index': 0, 'ablation': 'none', 'ended_by': 'completed'})
    hz.save_run(traj, Score(0, 1, 1, 1, 0, 'no_answer'), tmp_path, logs_dir=tmp_path / 'logs')
    for f in (tmp_path / 'logs').glob('*.json'):
        assert not company.search(f.read_text())
