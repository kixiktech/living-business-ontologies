from datetime import date, datetime

import pytest

from lbo import ingest as ig
from lbo.firms import FIRMS, common as cm

D, T = date, datetime


@pytest.fixture(scope='module')
def builds():
    return {slug: ig.ingest(FIRMS[slug][0]()) for slug in FIRMS}


def test_registry_has_three_firms():
    assert set(FIRMS) == {'retail', 'fieldservice', 'distributor'}


def test_every_build_validates_against_its_schema(builds):
    for slug, b in builds.items():
        assert b.problems == [], (slug, b.problems[:5])
        assert b.stats['assertions'] > 1000, slug
        assert b.log.arm == 'build' and any(t.role == 'tool' for t in b.log.turns)


def test_retail_case_one_reproduces_from_the_ingested_store(builds):
    b = builds['retail']
    k = b.firm.answer_key
    c = b.firm.slug
    a = b.resolver.lookup('product_master', 'A-100')
    p_b = b.resolver.lookup('product_master', 'B-200')
    qs = {q: (s, e) for q, s, e in cm.quarters()}

    def gp_for(q):
        w = qs[q]
        total = 0.0
        for prod, price in ((a, 30.0), (p_b, 50.0)):
            lines = [x for x in b.store.query(c, predicate='order_line.of_product', value=prod)]
            for ln in lines:
                sold = b.store.query(c, ln.subject, 'order_line.sold_at')[0].value
                d = date.fromisoformat(sold)
                if w[0] <= d < w[1]:
                    qty = b.store.query(c, ln.subject, 'order_line.qty')[0].value
                    cost = b.store.query(c, prod, 'product.unit_cost', as_of=d)[0].value
                    total += qty * (price - cost)
        return round(total, 2)

    assert gp_for(k['prior_quarter']) == k['gp_prior'] and gp_for(k['focal_quarter']) == k['gp_focal']
    units = b.registry.compute('quarter_units_ordered', b.store, c, qs['2026Q1'])
    assert units.value == 470.0
    # two clocks: on 2026-04-03 the Q2 cost was not yet known
    assert b.store.query(c, a, 'product.unit_cost', as_of=D(2026, 4, 2), known_at=T(2026, 4, 3))[0].value == 15.0
    assert b.store.query(c, a, 'product.unit_cost', as_of=D(2026, 4, 2), known_at=T(2026, 4, 7))[0].value == 18.0
    # the cash decision two hops away
    po = [x for x in b.store.query(c, predicate='purchase_order.cut_for')]
    assert len(po) == 1 and po[0].value.startswith('payment:')


def test_retail_identity_plants_resolve_as_designed(builds):
    b = builds['retail']
    k = b.firm.answer_key
    for src, dup in k['duplicate_email_pairs']:
        assert b.resolver.lookup('customers', src) == b.resolver.lookup('customers', dup)
    q = b.resolver.review_queue()
    assert len(q) == len(k['same_name_pairs'])


def test_retail_absences_are_visible_as_absences(builds):
    b = builds['retail']
    k = b.firm.answer_key
    c = 'retail'
    sku = b.resolver.lookup('product_master', k['absent_supplier_sku'])
    assert b.store.query(c, sku, 'product.supplied_by') == []
    s3 = f'location:{k["location_without_manager"]}'
    assert b.store.query(c, s3, 'location.manager') == []


def test_fieldservice_capacity_reproduces(builds):
    b = builds['fieldservice']
    k = b.firm.answer_key
    c = 'fieldservice'
    qs = {q: (s, e) for q, s, e in cm.quarters()}
    util = b.registry.compute('tech_utilisation_pct', b.store, c, qs[k['focal_quarter']])
    t3 = b.resolver.lookup('technicians', 'T3')
    assert util.value[t3] == k['utilisation_pct']
    net = b.registry.compute('net_contribution', b.store, c, qs[k['focal_quarter']])
    assert net.value['channel:A'] == 7000.0 and net.value['channel:B'] == 10000.0
    t5 = b.resolver.lookup('technicians', 'T5')
    assert b.store.query(c, t5, 'person.holds')                      # still holds it on paper
    assert b.store.query(c, t5, 'person.employed', as_of=D(2026, 4, 1)) == []   # but is gone


def test_distributor_numbers_reproduce(builds):
    b = builds['distributor']
    k = b.firm.answer_key
    c = 'distributor'
    qs = {q: (s, e) for q, s, e in cm.quarters()}
    w = qs[k['focal_quarter']]
    conc = b.registry.compute('customer_concentration', b.store, c, w)
    top = b.resolver.lookup('customers', 'CU-0007')
    assert conc.value['top1_pct'] == k['top_customer_pct']
    aging = b.registry.compute('receivables_aging', b.store, c, w)
    assert aging.value == k['aging']
    rc = b.registry.compute('route_contribution', b.store, c, w)
    assert rc.value['route:R3']['contribution'] < 0
    assert b.monitor.check('agent', 'hold_order', {'customer': top}, at=D(2026, 6, 30)).requires_approval


def test_a_grant_naming_a_supplier_by_name_is_loaded_as_the_supplier_entity(builds):
    # The owner's letter says "Meridian Supply" because that is what a person writes. The
    # monitor compares a scope against an action payload key for key, and an action
    # carries the supplier as an entity, so the name is resolved when the grant is loaded.
    b = builds['retail']
    meridian = b.resolver.lookup('product_master', 'Meridian Supply')
    assert meridian and meridian.startswith('supplier:')
    scopes = [a.value for a in b.store.query('retail', predicate='grant.scope')]
    assert {'supplier': meridian} in scopes
    assert not any('supplier_name' in s for s in scopes)
    a = b.resolver.lookup('product_master', 'A-100')
    d = b.monitor.check('agent', 'place_order',
                        {'supplier': meridian, 'product': a, 'qty': 30, 'amount': 540.0},
                        at=D(2026, 7, 1))
    assert d.allowed and not d.requires_approval, d.reason
    other = b.monitor.check('agent', 'place_order',
                            {'supplier': 'supplier:somebody-else', 'product': a, 'qty': 30,
                             'amount': 540.0}, at=D(2026, 7, 1))
    assert not other.allowed and 'supplier' in other.reason
    over = b.monitor.check('agent', 'place_order',
                           {'supplier': meridian, 'product': a, 'qty': 30, 'amount': 5400.0},
                           at=D(2026, 7, 1))
    assert not over.allowed and 'max_amount' in over.reason
