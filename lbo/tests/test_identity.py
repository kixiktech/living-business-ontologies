# research/lbo/tests/test_identity.py
from datetime import date, datetime
from lbo.store import Store
from lbo.identity import Resolver, Candidate

D, T = date, datetime


def test_same_email_from_two_sources_is_one_party():
    s = Store(); r = Resolver(s, 'c1')
    a = r.register('pos', 'cust_1', 'party', {'name': 'Ana Ruiz', 'email': 'ana@x.com'}, D(2026, 1, 1))
    b = r.register('crm', 'C-77', 'party', {'name': 'A. Ruiz', 'email': 'ANA@x.com'}, D(2026, 1, 2))
    assert a == b
    assert r.lookup('crm', 'C-77') == a
    assert r.review_queue() == []


def test_same_name_different_email_is_two_parties_and_a_candidate():
    s = Store(); r = Resolver(s, 'c1')
    a = r.register('pos', 'cust_1', 'party', {'name': 'Ana Ruiz', 'email': 'ana@x.com'}, D(2026, 1, 1))
    b = r.register('web', 'u9', 'party', {'name': 'ana ruiz', 'email': 'ruiz@y.com'}, D(2026, 1, 2))
    assert a != b
    q = r.review_queue()
    assert len(q) == 1 and {q[0].a, q[0].b} == {a, b} and 'name' in q[0].reason


def test_merge_is_recorded_not_destructive_and_split_reverses_it():
    s = Store(); r = Resolver(s, 'c1')
    a = r.register('pos', 'cust_1', 'party', {'name': 'Ana Ruiz', 'email': 'ana@x.com'}, D(2026, 1, 1))
    b = r.register('web', 'u9', 'party', {'name': 'Ana Ruiz', 'email': 'ruiz@y.com'}, D(2026, 1, 2))
    s.assert_('c1', 'order:o1', 'order.placed_by', b, D(2026, 2, 1), evidence='pos')
    r.merge(a, b, reason='owner confirmed same customer', evidence='email from owner 2026-03-01',
            recorded_at=T(2026, 3, 1))
    assert r.canonical(b) == a and r.canonical(a) == a
    assert r.review_queue() == []
    assert any(x.subject == 'order:o1' for x in r.dependents(b))
    assert r.canonical(b, known_at=T(2026, 2, 15)) == b       # replay before the merge
    r.split(b, reason='two people after all', evidence='owner 2026-04-01', recorded_at=T(2026, 4, 1))
    assert r.canonical(b) == b
    assert r.canonical(b, known_at=T(2026, 3, 15)) == a       # the merge still happened then


def test_a_matched_source_also_asserts_its_attrs_but_never_a_repeat_value():
    s = Store(); r = Resolver(s, 'c1')
    a = r.register('pos', 'cust_1', 'party', {'name': 'Ana Ruiz', 'email': 'ana@x.com'}, D(2026, 1, 1),
                   evidence='pos export 2026-01-01')
    b = r.register('crm', 'C-77', 'party', {'name': 'A. Ruiz', 'email': 'ANA@x.com'}, D(2026, 1, 2),
                   evidence='crm export 2026-01-02')
    assert a == b
    names = s.query('c1', a, 'party.name')
    assert {n.value for n in names} == {'Ana Ruiz', 'A. Ruiz'}
    assert {n.evidence for n in names} == {'pos export 2026-01-01', 'crm export 2026-01-02'}
    # a third source agreeing with an already-recorded name adds nothing
    r.register('web', 'w9', 'party', {'name': 'A. Ruiz', 'email': 'ana@x.com'}, D(2026, 1, 3),
               evidence='web export 2026-01-03')
    assert len(s.query('c1', a, 'party.name')) == 2


def test_products_resolve_on_sku_and_attrs_are_asserted_with_evidence():
    s = Store(); r = Resolver(s, 'c1')
    p = r.register('pos', 'item_44', 'product', {'sku': 'AB-1', 'name': 'Bottle', 'unit_cost': 15.0},
                   D(2026, 1, 1), evidence='pos export 2026-01-01')
    assert p.startswith('product:')
    cost = s.query('c1', p, 'product.unit_cost')
    assert cost and cost[0].value == 15.0 and cost[0].evidence == 'pos export 2026-01-01'
