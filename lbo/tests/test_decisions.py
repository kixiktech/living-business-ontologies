# research/lbo/tests/test_decisions.py
from datetime import datetime

from lbo import actions as ac, decisions as dc
from lbo.store import Store

NOW = datetime(2026, 7, 1, 8)


def _proposal(new=33.0):
    return ac.Proposal('change_price', {'product': 'product:x', 'old': 30.0, 'new': new, 'reason': 'summer'},
                       {'schema': 's'}, NOW)


def test_the_gap_is_the_owner_minus_the_agent_per_numeric_field():
    assert dc.gap({'new': 33.0, 'old': 30.0, 'reason': 'summer'}, {'new': 31.0, 'old': 30.0, 'reason': 'summer'}) \
        == {'new': -2.0, 'old': 0.0}
    assert dc.gap({'hours': 10}, {'hours': 8, 'day': '2026-07-03'}) == {'hours': -2.0, 'changed': ['day']}
    assert dc.gap({'new': 33.0}, None) == {'declined': True}


def test_a_decision_is_recorded_with_both_payloads_and_the_conditions():
    s = Store()
    p = _proposal()
    subj = dc.record_decision(s, 'c1', p, 'amend', dict(p.payload, new=31.0), 'Keep it to a dollar.', NOW,
                              rationale='raise for the summer')
    assert subj == f'decision:{p.hash()}'
    rows = {a.predicate: a.value for a in s.query('c1', subj)}
    assert rows['decision.proposed']['new'] == 33.0 and rows['decision.decided']['new'] == 31.0
    assert rows['decision.gap'] == {'new': -2.0, 'old': 0.0}
    assert rows['decision.conditions'] == 'Keep it to a dollar.' and rows['decision.kind'] == 'amend'
    link = s.query('c1', f'action:{p.hash()}', 'action.of_decision')
    assert link and link[0].value == subj


def test_a_declined_decision_leaves_the_same_shape_of_record():
    s = Store()
    p = _proposal()
    dc.record_decision(s, 'c1', p, 'decline', None, 'Never without a call.', NOW)
    rows = {a.predicate: a.value for a in s.query('c1', f'decision:{p.hash()}')}
    assert rows['decision.decided'] is None and rows['decision.gap'] == {'declined': True}


def test_decisions_for_an_action_come_back_oldest_first():
    s = Store()
    dc.record_decision(s, 'c1', _proposal(33.0), 'amend', {'new': 31.0}, 'a', NOW)
    dc.record_decision(s, 'c1', _proposal(32.0), 'approve', {'new': 32.0}, 'b', datetime(2026, 7, 15, 8))
    out = dc.decisions_for(s, 'c1', 'change_price')
    assert [d['conditions'] for d in out] == ['a', 'b'] and out[0]['gap']['new'] == -2.0
    assert dc.decisions_for(s, 'c1', 'change_price', known_at=NOW)[-1]['conditions'] == 'a'


def test_the_question_carries_the_contract_first_so_a_declined_proposal_is_still_findable():
    s = Store()
    p = _proposal()
    subj = dc.record_decision(s, 'c1', p, 'decline', None, 'No.', NOW, rationale='raise for the summer')
    rows = {a.predicate: a.value for a in s.query('c1', subj)}
    assert rows['decision.question'] == 'change_price: raise for the summer'
    assert dc.decisions_for(s, 'c1', 'change_price')[0]['kind'] == 'decline'
    assert dc.decisions_for(s, 'c1', 'place_order') == []


def test_the_decision_predicates_are_in_the_core_schema():
    from lbo.schema import core
    s = core()
    for p in ('decision.question', 'decision.taken_at'):
        assert p.split('.')[0] in s.entities
    assert 'action.of_decision' in s.relations


def test_the_validator_accepts_every_predicate_the_record_writes():
    from lbo.schema import core
    s = Store()
    p = _proposal()
    dc.record_decision(s, 'c1', p, 'amend', dict(p.payload, new=31.0), 'Keep it to a dollar.', NOW)
    assert core().validate(s, 'c1') == []
