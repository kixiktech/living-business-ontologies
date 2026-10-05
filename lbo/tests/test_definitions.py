# research/lbo/tests/test_definitions.py
from datetime import date, datetime
import pytest
from lbo.store import Store
from lbo import definitions as df

D, T = date, datetime


def _retail_store():
    # Product A's cost history is built the way ingestion actually learns it: the $15
    # row starts open-ended (no one yet knows it will ever change), and only when the
    # 2026-04-06 invoice arrives do we learn, in the same moment, both that it closed on
    # 2026-04-01 and what replaced it. Nothing here is known in advance of when it was
    # actually recorded.
    s = Store(); c = 'c1'
    old = s.assert_(c, 'product:a', 'product.unit_cost', 15.0, D(2026, 1, 1),
                    evidence='inv1', recorded_at=T(2026, 1, 2))
    s.supersede(old, valid_to=D(2026, 4, 1), evidence='inv2', recorded_at=T(2026, 4, 6))
    s.assert_(c, 'product:a', 'product.unit_cost', 18.0, D(2026, 4, 1), evidence='inv2', recorded_at=T(2026, 4, 6))
    s.assert_(c, 'product:b', 'product.unit_cost', 30.0, D(2026, 1, 1), evidence='inv1', recorded_at=T(2026, 1, 2))
    # Both sales happen, and are entered, on 2026-04-02: before the 04-06 invoice update,
    # so a replay from 2026-04-03 sees them (their own knowledge time has passed) while
    # the cost correction (knowledge time 04-06) has not arrived yet.
    for i, (p, q, price, day) in enumerate([('product:a', 400, 30.0, D(2026, 4, 2)),
                                            ('product:b', 200, 50.0, D(2026, 4, 2))]):
        ln = f'order_line:{i}'
        rec = T(day.year, day.month, day.day, 18)          # entered the day of the sale
        s.assert_(c, ln, 'order_line.of_product', p, day, evidence='pos', recorded_at=rec)
        s.assert_(c, ln, 'order_line.qty', q, day, evidence='pos', recorded_at=rec)
        s.assert_(c, ln, 'order_line.unit_price', price, day, evidence='pos', recorded_at=rec)
        s.assert_(c, ln, 'order_line.sold_at', day.isoformat(), day, evidence='pos', recorded_at=rec)
    return s


def test_gross_sales_and_profit_on_a_window():
    s = _retail_store(); r = df.core_registry()
    w = (D(2026, 4, 1), D(2026, 7, 1))
    gs = r.compute('gross_sales', s, 'c1', w)
    gp = r.compute('gross_profit', s, 'c1', w)
    assert gs.value == 22000.0
    assert gp.value == 22000.0 - (400 * 18.0 + 200 * 30.0)
    assert gp.base == 'gross sales less cost of goods at the unit cost valid on the sale date'
    assert set(gp.inputs)  # it read something
    m = r.compute('gross_margin_pct', s, 'c1', w)
    assert m.value == round((22000 - 13200) / 22000 * 100, 2)


def test_knowledge_time_changes_the_cost_basis_honestly():
    """On 2026-04-03 the new invoice had not arrived: the replay must use 15.0."""
    s = _retail_store(); r = df.core_registry()
    w = (D(2026, 4, 1), D(2026, 7, 1))
    then = r.compute('gross_profit', s, 'c1', w, known_at=T(2026, 4, 3))
    now = r.compute('gross_profit', s, 'c1', w)
    assert then.value == 22000.0 - (400 * 15.0 + 200 * 30.0)
    assert now.value < then.value


def test_a_missing_cost_is_a_note_never_a_zero():
    s = _retail_store(); r = df.core_registry()
    s.assert_('c1', 'order_line:9', 'order_line.of_product', 'product:zzz', D(2026, 5, 1), evidence='pos')
    s.assert_('c1', 'order_line:9', 'order_line.qty', 10, D(2026, 5, 1), evidence='pos')
    s.assert_('c1', 'order_line:9', 'order_line.unit_price', 5.0, D(2026, 5, 1), evidence='pos')
    s.assert_('c1', 'order_line:9', 'order_line.sold_at', '2026-05-01', D(2026, 5, 1), evidence='pos')
    cogs = r.compute('cost_of_goods', s, 'c1', (D(2026, 4, 1), D(2026, 7, 1)))
    assert any('product:zzz' in n for n in cogs.notes)


def test_versions_are_selected_by_effective_date():
    r = df.Registry()
    r.register(df.MetricDefinition('x', 'v1', 'line', 'usd', 'gross', (), D(2026, 1, 1), lambda *a: (1.0, (), ())))
    r.register(df.MetricDefinition('x', 'v2', 'line', 'usd', 'net', (), D(2026, 6, 1), lambda *a: (2.0, (), ())))
    assert r.get('x', D(2026, 3, 1)).version == 'v1'
    assert r.get('x', D(2026, 6, 1)).version == 'v2'
    with pytest.raises(KeyError):
        r.get('x', D(2025, 1, 1))


def test_reconcile_names_every_difference():
    a = df.Measure('gross_profit', 100.0, (D(2026, 1, 1), D(2026, 4, 1)), 'gross', None, 'v1', ())
    b = df.Measure('gross_profit', 90.0, (D(2026, 1, 1), D(2026, 4, 1)), 'net of returns', None, 'v2', ())
    diffs = df.reconcile(a, b)
    assert any('base' in d for d in diffs) and any('version' in d for d in diffs) and any('value' in d for d in diffs)
    assert not any('window' in d for d in diffs)


def test_a_filter_narrows_a_measure_to_one_product():
    from lbo.firms import FIRMS
    from lbo.ingest import ingest
    b = ingest(FIRMS['retail'][0]())
    a = b.resolver.lookup('product_master', 'A-100')
    other = b.resolver.lookup('product_master', 'B-200')
    w = (D(2026, 1, 1), D(2026, 4, 1))
    # 400 bottles at a 30.00 price and a 15.00 cost
    one = b.registry.compute('gross_profit', b.store, 'retail', w,
                             filters={'order_line.of_product': a})
    assert one.value == 6000.0
    two = b.registry.compute('gross_profit', b.store, 'retail', w,
                             filters={'order_line.of_product': other})
    assert two.value == 4000.0
    # the two focal products together are the answer key's prior-quarter gross profit
    assert round(one.value + two.value, 2) == b.firm.answer_key['gp_prior']
    whole = b.registry.compute('gross_profit', b.store, 'retail', w)
    assert whole.value > one.value + two.value
    assert one.inputs and set(one.inputs) < set(whole.inputs)


def test_a_filter_nothing_matches_is_zero_not_an_error():
    from lbo.firms import FIRMS
    from lbo.ingest import ingest
    b = ingest(FIRMS['retail'][0]())
    m = b.registry.compute('gross_sales', b.store, 'retail', (D(2026, 1, 1), D(2026, 4, 1)),
                           filters={'order_line.of_product': 'product:nobody'})
    assert m.value == 0.0 and m.inputs == ()
