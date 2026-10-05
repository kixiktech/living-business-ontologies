# research/lbo/tests/test_actions.py
from datetime import date, datetime
from lbo.store import Store
from lbo import actions as ac
from lbo import authority as au

D, T = date, datetime


def _setup():
    s = Store(); c = 'c1'
    s.assert_(c, 'product:a', 'product.list_price', 30.0, D(2026, 1, 1), evidence='pos')
    s.assert_(c, 'product:a', 'product.supplied_by', 'supplier:s1', D(2026, 1, 1), evidence='terms')
    reg = ac.Registry(); reg.register(ac.change_price_contract()); reg.register(ac.place_order_contract())
    mon = au.Monitor([au.Grant('agent', 'change_price', {}, {}, D(2026, 1, 1)),
                      au.Grant('agent', 'place_order', {}, {'max_amount': 2000.0}, D(2026, 1, 1))],
                     [au.price_change_rule(5.0)])
    return s, c, reg, mon


def test_a_compliant_price_change_executes_and_is_journaled():
    s, c, reg, mon = _setup()
    p = ac.propose(reg.get('change_price'), {'product': 'product:a', 'old': 30.0, 'new': 31.5},
                   {'gross_profit': 'v1'}, created_at=T(2026, 7, 1))
    ex = ac.execute(p, registry=reg, store=s, client=c, monitor=mon, principal='agent',
                    at=D(2026, 7, 1), now=T(2026, 7, 1, 9))
    assert ex.status == 'executed', ex.reason
    assert s.query(c, 'product:a', 'product.list_price', as_of=D(2026, 7, 2))[0].value == 31.5
    assert s.query(c, 'product:a', 'product.list_price', as_of=D(2026, 6, 30))[0].value == 30.0
    st = s.query(c, f'action:{p.hash()}', 'action.status')
    assert st and st[0].value == 'executed'


def test_over_limit_is_blocked_without_approval_and_executes_with_it():
    s, c, reg, mon = _setup()
    p = ac.propose(reg.get('change_price'), {'product': 'product:a', 'old': 30.0, 'new': 32.0}, {},
                   created_at=T(2026, 7, 1))
    ex = ac.execute(p, registry=reg, store=s, client=c, monitor=mon, principal='agent',
                    at=D(2026, 7, 1), now=T(2026, 7, 1, 9))
    assert ex.status == 'blocked' and '6.67%' in ex.reason
    assert s.query(c, 'product:a', 'product.list_price', as_of=D(2026, 7, 2))[0].value == 30.0
    ok = ac.execute(p, registry=reg, store=s, client=c, monitor=mon, principal='agent',
                    at=D(2026, 7, 1), now=T(2026, 7, 1, 10),
                    approval=ac.Approval(p.hash(), 'owner', T(2026, 7, 1, 9, 30)))
    assert ok.status == 'executed'


def test_editing_the_payload_after_approval_invalidates_it():
    s, c, reg, mon = _setup()
    p = ac.propose(reg.get('change_price'), {'product': 'product:a', 'old': 30.0, 'new': 32.0}, {},
                   created_at=T(2026, 7, 1))
    appr = ac.Approval(p.hash(), 'owner', T(2026, 7, 1))
    p2 = ac.propose(reg.get('change_price'), {'product': 'product:a', 'old': 30.0, 'new': 33.0}, {},
                    created_at=T(2026, 7, 1))
    ex = ac.execute(p2, registry=reg, store=s, client=c, monitor=mon, principal='agent',
                    at=D(2026, 7, 1), now=T(2026, 7, 1, 10), approval=appr)
    assert ex.status == 'blocked' and 'approval' in ex.reason


def test_no_grant_is_refused_and_a_stale_precondition_fails():
    s, c, reg, mon = _setup()
    p = ac.propose(reg.get('change_price'), {'product': 'product:a', 'old': 30.0, 'new': 31.0}, {})
    ex = ac.execute(p, registry=reg, store=s, client=c, monitor=mon, principal='intern',
                    at=D(2026, 7, 1), now=T(2026, 7, 1))
    assert ex.status == 'refused' and 'no grant' in ex.reason
    stale = ac.propose(reg.get('change_price'), {'product': 'product:a', 'old': 29.0, 'new': 30.0}, {})
    ex2 = ac.execute(stale, registry=reg, store=s, client=c, monitor=mon, principal='agent',
                     at=D(2026, 7, 1), now=T(2026, 7, 1))
    assert ex2.status == 'failed' and 'precondition' in ex2.reason


def test_place_order_within_limits_creates_the_order():
    s, c, reg, mon = _setup()
    p = ac.propose(reg.get('place_order'), {'supplier': 'supplier:s1', 'product': 'product:a',
                                            'qty': 30, 'amount': 540.0}, {})
    ex = ac.execute(p, registry=reg, store=s, client=c, monitor=mon, principal='agent',
                    at=D(2026, 7, 1), now=T(2026, 7, 1))
    assert ex.status == 'executed'
    assert s.query(c, f'purchase_order:{p.hash()}', 'purchase_order.qty')[0].value == 30
    # a second, different proposal executes independently and creates its own subject
    p2 = ac.propose(reg.get('place_order'), {'supplier': 'supplier:s1', 'product': 'product:a',
                                             'qty': 12, 'amount': 216.0}, {})
    assert p2.hash() != p.hash()
    ex2 = ac.execute(p2, registry=reg, store=s, client=c, monitor=mon, principal='agent',
                     at=D(2026, 7, 1), now=T(2026, 7, 1))
    assert ex2.status == 'executed'
    assert s.query(c, f'purchase_order:{p2.hash()}', 'purchase_order.qty')[0].value == 12
    assert s.query(c, f'purchase_order:{p.hash()}', 'purchase_order.qty')[0].value == 30
