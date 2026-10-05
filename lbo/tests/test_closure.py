# research/lbo/tests/test_closure.py
from datetime import date, datetime
from lbo.store import Store
from lbo import closure as cl
from lbo import definitions as df

D, T = date, datetime
W = (D(2026, 4, 1), D(2026, 7, 1))


def _q():
    return cl.CompetencyQuestion(
        'margin_q2', 'What happened to gross margin in Q2, and why?',
        (cl.Requirement('assertion', predicate='order_line.sold_at'),
         cl.Requirement('assertion', predicate='product.unit_cost', subject='product:a', covers=W),
         cl.Requirement('assertion', predicate='product.supplied_by', subject='product:a'),
         cl.Requirement('definition', definition='gross_profit')))


def test_absent_and_stale_are_named_not_filled():
    s = Store()
    s.assert_('c1', 'order_line:1', 'order_line.sold_at', '2026-04-10', D(2026, 4, 10), evidence='pos')
    s.assert_('c1', 'product:a', 'product.unit_cost', 15.0, D(2026, 1, 1), D(2026, 5, 1), evidence='inv1')
    sat = cl.satisfies(_q(), s, 'c1', as_of=D(2026, 6, 30), registry=df.core_registry())
    assert not sat.ok
    absent = {r.predicate for r in sat.absent}
    assert 'product.supplied_by' in absent
    assert 'product.unit_cost' in absent            # covers only to 2026-05-01, window runs to 07-01
    assert any('2026-05-01' in g for g in sat.gaps)


def test_fully_covered_question_is_satisfied_and_closure_lists_its_inputs():
    s = Store()
    s.assert_('c1', 'order_line:1', 'order_line.sold_at', '2026-04-10', D(2026, 4, 10), evidence='pos')
    s.assert_('c1', 'order_line:1', 'order_line.of_product', 'product:a', D(2026, 4, 10), evidence='pos')
    s.assert_('c1', 'order_line:1', 'order_line.qty', 4, D(2026, 4, 10), evidence='pos')
    s.assert_('c1', 'order_line:1', 'order_line.unit_price', 30.0, D(2026, 4, 10), evidence='pos')
    c1 = s.assert_('c1', 'product:a', 'product.unit_cost', 15.0, D(2026, 1, 1), D(2026, 5, 1), evidence='inv1')
    c2 = s.assert_('c1', 'product:a', 'product.unit_cost', 18.0, D(2026, 5, 1), evidence='inv2')
    sup = s.assert_('c1', 'product:a', 'product.supplied_by', 'supplier:s1', D(2020, 1, 1), evidence='terms')
    sat = cl.satisfies(_q(), s, 'c1', as_of=D(2026, 6, 30), registry=df.core_registry())
    assert sat.ok, (sat.absent, sat.stale, sat.gaps)
    ids = cl.dependency_closure(_q(), s, 'c1', as_of=D(2026, 6, 30), registry=df.core_registry())
    assert {c1, c2, sup} <= ids


def test_stale_is_about_knowledge_age():
    s = Store()
    q = cl.CompetencyQuestion('terms', 'Are the supplier terms current?',
                              (cl.Requirement('assertion', predicate='supplier.terms', max_age_days=90),))
    s.assert_('c1', 'supplier:s1', 'supplier.terms', {'break': 500}, D(2025, 1, 1), evidence='pdf',
              recorded_at=T(2025, 1, 5))
    sat = cl.satisfies(q, s, 'c1', as_of=D(2026, 6, 30), known_at=T(2026, 6, 30))
    assert sat.stale and not sat.absent and not sat.ok


def test_grant_requirement_consults_the_monitor():
    # A grant requirement asks whether the verb is delegated, so the monitor is asked
    # `has_grant` and never `check`: `check` judges one payload, and the empty payload a
    # question has to offer is outside every scope and trips every rule needing a value.
    class Allow:
        def has_grant(self, principal, action, at=None):
            return principal == 'agent'

        def check(self, principal, action, payload, at=None):
            raise AssertionError('a grant requirement must not be judged on a payload')
    s = Store()
    q = cl.CompetencyQuestion('reorder', 'Can we place the reorder?',
                              (cl.Requirement('grant', action='place_order'),))
    assert cl.satisfies(q, s, 'c1', as_of=D(2026, 1, 1), monitor=Allow(), principal='agent').ok
    assert not cl.satisfies(q, s, 'c1', as_of=D(2026, 1, 1), monitor=Allow(), principal='nobody').ok


def test_has_grant_ignores_scope_limits_and_rules():
    from lbo.authority import Grant, Monitor, price_change_rule
    m = Monitor([Grant('agent', 'place_order', {'supplier': 'supplier:x'}, {'max_amount': 2000.0},
                       D(2026, 1, 1)),
                 Grant('agent', 'change_price', {}, {}, D(2026, 1, 1), D(2026, 3, 1))],
                [price_change_rule(5.0)])
    assert m.has_grant('agent', 'place_order', D(2026, 6, 1))
    assert not m.has_grant('agent', 'place_order', D(2025, 6, 1))     # before it was granted
    assert not m.has_grant('nobody', 'place_order', D(2026, 6, 1))
    assert not m.has_grant('agent', 'hold_order', D(2026, 6, 1))      # never granted
    assert not m.has_grant('agent', 'change_price', D(2026, 6, 1))    # expired
    # the payload an empty check would fail on says nothing about whether the grant exists
    assert not m.check('agent', 'place_order', {}, at=D(2026, 6, 1)).allowed


def test_a_requirement_without_a_window_is_read_as_of_the_question_date():
    # the certification was valid through 2025 and the question is asked in 2026: the fact
    # exists in the store and does not hold on the day asked, and the gap says which
    s = Store()
    s.assert_('c1', 'person:t5', 'person.holds_certification', 'certification:backflow',
              D(2024, 1, 1), D(2026, 1, 1), evidence='sheet')
    q = cl.CompetencyQuestion('who', 'Who can do backflow jobs?',
                              (cl.Requirement('assertion', predicate='person.holds_certification'),))
    assert cl.satisfies(q, s, 'c1', as_of=D(2025, 6, 1)).ok
    sat = cl.satisfies(q, s, 'c1', as_of=D(2026, 6, 1))
    assert not sat.ok and any('nothing valid on 2026-06-01' in g for g in sat.gaps), sat.gaps
    assert cl.dependency_closure(q, s, 'c1', as_of=D(2026, 6, 1)) == set()
    assert len(cl.dependency_closure(q, s, 'c1', as_of=D(2025, 6, 1))) == 1


def test_knowledge_age_is_measured_from_the_question_not_the_machine():
    s = Store()
    q = cl.CompetencyQuestion('terms', 'Are the supplier terms current?',
                              (cl.Requirement('assertion', predicate='supplier.terms', max_age_days=90),))
    s.assert_('c1', 'supplier:s1', 'supplier.terms', {'break': 500}, D(2025, 1, 1), evidence='pdf',
              recorded_at=T(2025, 1, 5))
    # asked two weeks after it was recorded, with no knowledge clock given: fresh, whatever
    # the machine's calendar says today
    assert cl.satisfies(q, s, 'c1', as_of=D(2025, 1, 20)).ok
    assert cl.satisfies(q, s, 'c1', as_of=D(2026, 6, 30)).stale
