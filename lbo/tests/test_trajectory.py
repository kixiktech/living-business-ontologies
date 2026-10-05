import json
from pathlib import Path
from lbo import trajectory as tj


def _traj():
    return tj.Trajectory(
        firm='retail', arm='C', task='margin_two_hops', model='claude-x', date='2026-09-28',
        turns=[
            tj.Turn(role='owner', kind='message', text='Why did margin fall?'),
            tj.Turn(role='agent', kind='tool_call', name='get_supplier_terms',
                    text='{"supplier": "sup:01", "as_of": "2026-06-30"}'),
            tj.Turn(role='tool', kind='tool_result', name='get_supplier_terms',
                    text='{"break_units": 500}'),
            tj.Turn(role='monitor', kind='refusal', text='exceeds 5% limit'),
            tj.Turn(role='agent', kind='message', text='The tier was lost.'),
        ],
        score={'S': 1, 'P': 1, 'E': 1, 'C': 1, 'R': 1},
    )


def test_hash_is_stable_and_depends_only_on_turns():
    a, b = _traj(), _traj()
    b.score = {}
    assert a.hash() == b.hash()
    assert len(a.hash()) == 12
    b.turns[0].text += '!'
    assert a.hash() != b.hash()


def test_save_and_load_round_trip(tmp_path):
    t = _traj()
    p = tj.save(t, tmp_path)
    assert p.name == t.hash() + '.json'
    back = tj.load(t.hash(), tmp_path)
    assert back == t
    assert json.loads(p.read_text())['hash'] == t.hash()


def test_render_marks_roles_and_kinds_and_escapes():
    t = _traj()
    t.turns[0].text = 'a < b'
    html = tj.render_html(t)
    assert '<div class="traj">' in html
    assert 'class="turn owner message"' in html
    assert 'class="turn monitor refusal"' in html
    assert 'a &lt; b' in html
    assert 'get_supplier_terms' in html


def test_render_slice_is_one_based_inclusive():
    html = tj.render_html(_traj(), turns=(2, 3))
    assert 'Why did margin fall' not in html
    assert 'break_units' in html
    assert 'The tier was lost' not in html


def test_render_elides_a_long_id_list_but_leaves_a_short_one_and_the_hash_alone():
    long_ids = list(range(48812, 48812 + 12))
    t = tj.Trajectory(firm='retail', arm='C', task='t', model='m', date='d', turns=[
        tj.Turn(role='tool', kind='tool_result', name='get_rows',
                text=json.dumps({'ids': long_ids})),
        tj.Turn(role='tool', kind='tool_result', name='get_rows',
                text=json.dumps({'ids': [1, 2, 3, 4, 5]})),
    ])
    before = t.hash()
    html = tj.render_html(t)

    assert f'[{long_ids[0]}, {long_ids[1]}, {long_ids[2]}, {long_ids[3]}, ... 12 ids]' in html
    assert str(long_ids[4]) not in html, 'the elided ids must not survive into the print'

    assert '[1, 2, 3, 4, 5]' in html, 'a five-item array is not long enough to elide'

    assert t.hash() == before, 'rendering must not change the identity of the run'
    assert json.loads(t.turns[0].text)['ids'] == long_ids, 'render must not mutate the stored turn'


def test_render_compacts_a_long_turn_and_leaves_the_hash_alone():
    text = 'a' * 600
    t = tj.Trajectory(firm='retail', arm='C', task='t', model='m', date='d', turns=[
        tj.Turn(role='agent', kind='message', text=text),
    ])
    before = t.hash()
    html = tj.render_html(t, compact=240)

    assert '[+' in html
    assert '[+360 chars]' in html, 'a 600-char turn cut at 240 removes 360 characters'
    assert 'a' * 241 not in html

    assert t.hash() == before, 'compacting must not change the identity of the run'
    assert t.turns[0].text == text, 'compacting must not mutate the stored turn'


def test_render_compact_leaves_a_short_turn_untouched():
    text = 'b' * 100
    t = tj.Trajectory(firm='retail', arm='C', task='t', model='m', date='d', turns=[
        tj.Turn(role='agent', kind='message', text=text),
    ])
    html = tj.render_html(t, compact=240)
    assert text in html
    assert '[+' not in html


def test_render_compact_cuts_at_a_whitespace_boundary_not_mid_word():
    text = 'supplier_terms ' * 40
    t = tj.Trajectory(firm='retail', arm='C', task='t', model='m', date='d', turns=[
        tj.Turn(role='agent', kind='message', text=text),
    ])
    html = tj.render_html(t, compact=100)
    assert 'supplier_terms [+511 chars]' in html
    assert 'supp [+' not in html, 'the cut must land on a whitespace boundary, not mid-word'


def test_invalid_role_is_refused():
    import pytest
    with pytest.raises(ValueError):
        tj.Turn(role='user', kind='message', text='x')


def test_has_dashes_counts_what_the_paper_may_not_print():
    clean = tj.Trajectory(firm='retail', arm='C', task='t', model='m', date='d', turns=[
        tj.Turn(role='agent', kind='message', text='Eastgate has no manager on record.')])
    assert tj.has_dashes(clean) == 0
    dirty = tj.Trajectory(firm='retail', arm='C', task='t', model='m', date='d', turns=[
        tj.Turn(role='agent', kind='message', text='Eastgate \u2014 no manager \u2014 on record'),
        tj.Turn(role='tool', kind='tool_result', name='x', text='2026 \u2013 2027')])
    assert tj.has_dashes(dirty) == 3


def test_compact_tools_trims_tool_results_and_never_the_agent():
    from lbo.trajectory import Trajectory, Turn, render_html
    long = 'x ' * 400
    t = Trajectory(firm='f', arm='C', task='t', model='m', date='d', turns=[
        Turn(role='tool', kind='tool_result', name='q', text=long),
        Turn(role='agent', kind='message', text=long)])
    html = render_html(t, compact_tools=100)
    blocks = html.split('<div class="turn ')[1:]
    assert '[+' in blocks[0] and '[+' not in blocks[1]
    assert len(blocks[1]) > len(blocks[0])
