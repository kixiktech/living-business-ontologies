# research/lbo/tests/test_store.py
from datetime import date, datetime
import pytest
from lbo.store import Store, Assertion, STATUSES

D = date
T = datetime


def test_assert_returns_an_id_and_round_trips():
    s = Store()
    i = s.assert_('c1', 'product:p1', 'product.unit_cost', 15.0, D(2026, 1, 1),
                  evidence='supplier invoice 1001', recorded_at=T(2026, 1, 3, 9))
    a = s.get(i)
    assert isinstance(a, Assertion)
    assert a.value == 15.0 and a.valid_to is None and a.recorded_until is None
    assert a.status == 'observed' and a.evidence == 'supplier invoice 1001'


def test_evidence_is_required_and_status_is_checked():
    s = Store()
    with pytest.raises(ValueError):
        s.assert_('c1', 'x:1', 'x.f', 1, D(2026, 1, 1), evidence='')
    with pytest.raises(ValueError):
        s.assert_('c1', 'x:1', 'x.f', 1, D(2026, 1, 1), evidence='e', status='guess')
    assert 'superseded' in STATUSES


def test_query_filters_by_business_time():
    s = Store()
    s.assert_('c1', 'product:p1', 'product.unit_cost', 15.0, D(2026, 1, 1), D(2026, 4, 1),
              evidence='inv 1', recorded_at=T(2026, 1, 3))
    s.assert_('c1', 'product:p1', 'product.unit_cost', 18.0, D(2026, 4, 1),
              evidence='inv 2', recorded_at=T(2026, 4, 6))
    assert [a.value for a in s.query('c1', 'product:p1', 'product.unit_cost', as_of=D(2026, 3, 15))] == [15.0]
    assert [a.value for a in s.query('c1', 'product:p1', 'product.unit_cost', as_of=D(2026, 4, 1))] == [18.0]
    assert len(s.query('c1', 'product:p1', 'product.unit_cost')) == 2


def test_query_filters_by_knowledge_time():
    """The cost took effect on the 1st; the invoice arrived on the 6th. On the 3rd we
    could not have known it."""
    s = Store()
    s.assert_('c1', 'product:p1', 'product.unit_cost', 18.0, D(2026, 4, 1),
              evidence='inv 2', recorded_at=T(2026, 4, 6, 10))
    assert s.query('c1', 'product:p1', 'product.unit_cost', as_of=D(2026, 4, 2),
                   known_at=T(2026, 4, 3)) == []
    assert len(s.query('c1', 'product:p1', 'product.unit_cost', as_of=D(2026, 4, 2),
                       known_at=T(2026, 4, 7))) == 1


def test_supersede_closes_the_old_row_and_links_the_new_one():
    s = Store()
    old = s.assert_('c1', 'tech:t1', 'tech.certified_in', 'service:hvac', D(2024, 5, 1),
                    evidence='cert scan', recorded_at=T(2024, 5, 2))
    new = s.supersede(old, valid_to=D(2026, 6, 30), evidence='ops manager email 2026-07-02',
                      recorded_at=T(2026, 7, 2, 9))
    o, n = s.get(old), s.get(new)
    assert o.status == 'superseded' and o.recorded_until == T(2026, 7, 2, 9)
    assert n.supersedes == old and n.valid_to == D(2026, 6, 30) and n.value == 'service:hvac'
    # current knowledge sees only the new row; a replay at 2026-06-01 knowledge sees the old
    assert [a.id for a in s.query('c1', 'tech:t1', 'tech.certified_in')] == [new]
    assert [a.id for a in s.query('c1', 'tech:t1', 'tech.certified_in', known_at=T(2026, 6, 1))] == [old]
    assert [a.id for a in s.history('c1', 'tech:t1', 'tech.certified_in')] == [old, new]


def test_nothing_is_deleted_and_superseded_rows_are_still_readable():
    s = Store()
    old = s.assert_('c1', 'x:1', 'x.f', 1, D(2026, 1, 1), evidence='e', recorded_at=T(2026, 1, 1))
    s.supersede(old, value=2, evidence='e2', recorded_at=T(2026, 2, 1))
    assert s.count('c1') == 2
    assert {a.value for a in s.query('c1', 'x:1', 'x.f', include_superseded=True)} == {1, 2}


def test_relation_query_by_value_finds_reverse_direction():
    s = Store()
    s.assert_('c1', 'job:j1', 'job.performed_by', 'crew:c1', D(2026, 5, 1), evidence='sched')
    s.assert_('c1', 'job:j2', 'job.performed_by', 'crew:c1', D(2026, 5, 2), evidence='sched')
    assert {a.subject for a in s.query('c1', predicate='job.performed_by', value='crew:c1')} == {'job:j1', 'job:j2'}


def test_contradictions_accumulate_against_edges():
    s = Store()
    a = s.assert_('c1', 'x:1', 'x.f', 1, D(2026, 1, 1), evidence='e')
    b = s.assert_('c1', 'x:2', 'x.f', 1, D(2026, 1, 1), evidence='e')
    s.record_contradiction([a, b], run_id='r1', note='reconciliation failed to tie out')
    s.record_contradiction([a], run_id='r2', note='constraint rejected')
    assert s.contradiction_counts('c1') == {a: 2, b: 1}


def test_values_survive_json_round_trip():
    s = Store()
    i = s.assert_('c1', 'x:1', 'x.f', {'k': [1, 2.5, 'z']}, D(2026, 1, 1), evidence='e')
    assert s.get(i).value == {'k': [1, 2.5, 'z']}


def test_query_by_value_matches_int_and_float_encodings_of_the_same_number():
    s = Store()
    i1 = s.assert_('c1', 'x:1', 'x.qty', 15, D(2026, 1, 1), evidence='e')
    i2 = s.assert_('c1', 'x:2', 'x.qty', 15.0, D(2026, 1, 1), evidence='e')
    assert {a.id for a in s.query('c1', predicate='x.qty', value=15)} == {i1, i2}
    assert {a.id for a in s.query('c1', predicate='x.qty', value=15.0)} == {i1, i2}
    # a non-integral float only matches its own encoding
    i3 = s.assert_('c1', 'x:3', 'x.qty', 15.5, D(2026, 1, 1), evidence='e')
    assert {a.id for a in s.query('c1', predicate='x.qty', value=15.5)} == {i3}
