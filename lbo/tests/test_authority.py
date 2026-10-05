# research/lbo/tests/test_authority.py
from datetime import date
from lbo.store import Store
from lbo import authority as au

D = date


def _monitor():
    grants = [au.Grant('agent', 'change_price', scope={}, limits={}, valid_from=D(2026, 1, 1)),
              au.Grant('agent', 'place_order', scope={'supplier': 'supplier:s1'},
                       limits={'max_amount': 2000.0}, valid_from=D(2026, 1, 1), valid_to=D(2026, 12, 31))]
    return au.Monitor(grants, [au.price_change_rule(5.0)])


def test_no_grant_means_refused_with_a_reason():
    d = _monitor().check('agent', 'send_message', {}, at=D(2026, 6, 1))
    assert not d.allowed and 'no grant' in d.reason


def test_scope_and_limits_bind():
    m = _monitor()
    ok = m.check('agent', 'place_order', {'supplier': 'supplier:s1', 'amount': 540.0}, at=D(2026, 6, 1))
    assert ok.allowed and not ok.requires_approval
    wrong_scope = m.check('agent', 'place_order', {'supplier': 'supplier:s9', 'amount': 5.0}, at=D(2026, 6, 1))
    assert not wrong_scope.allowed and 'supplier' in wrong_scope.reason
    too_big = m.check('agent', 'place_order', {'supplier': 'supplier:s1', 'amount': 2500.0}, at=D(2026, 6, 1))
    assert not too_big.allowed and 'max_amount' in too_big.reason
    expired = m.check('agent', 'place_order', {'supplier': 'supplier:s1', 'amount': 5.0}, at=D(2027, 1, 1))
    assert not expired.allowed


def test_price_rule_requires_approval_above_the_limit_and_not_at_it():
    m = _monitor()
    over = m.check('agent', 'change_price', {'product': 'product:a', 'old': 30.0, 'new': 32.0}, at=D(2026, 6, 1))
    assert over.allowed and over.requires_approval and '6.67%' in over.reason
    at_limit = m.check('agent', 'change_price', {'product': 'product:a', 'old': 30.0, 'new': 31.5}, at=D(2026, 6, 1))
    assert at_limit.allowed and not at_limit.requires_approval


def test_grants_can_live_in_the_store():
    s = Store()
    s.assert_('c1', 'grant:g1', 'grant.principal', 'agent', D(2026, 1, 1), evidence='owner letter')
    s.assert_('c1', 'grant:g1', 'grant.action', 'change_price', D(2026, 1, 1), evidence='owner letter')
    s.assert_('c1', 'grant:g1', 'grant.scope', {}, D(2026, 1, 1), evidence='owner letter')
    s.assert_('c1', 'grant:g1', 'grant.limits', {}, D(2026, 1, 1), evidence='owner letter')
    m = au.Monitor.from_store(s, 'c1', [au.price_change_rule()], at=D(2026, 6, 1))
    assert m.check('agent', 'change_price', {'old': 10.0, 'new': 10.2}, at=D(2026, 6, 1)).allowed


def test_a_missing_or_null_limited_field_is_refused_not_zero():
    m = _monitor()
    gone = m.check('agent', 'place_order', {'supplier': 'supplier:s1'}, at=D(2026, 6, 1))
    assert not gone.allowed and 'amount missing' in gone.reason
    null = m.check('agent', 'place_order', {'supplier': 'supplier:s1', 'amount': None}, at=D(2026, 6, 1))
    assert not null.allowed and 'missing' in null.reason
