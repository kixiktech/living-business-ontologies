from datetime import date, datetime

from lbo import actions as ac
from lbo import arms
from lbo import contracts_extra as ce
from lbo.firms import FIRMS
from lbo.ingest import ingest

D, T = date, datetime


def test_extra_contracts_register():
    names = {c.name for c in ce.extra_contracts()}
    assert names == {'send_message', 'schedule_job', 'chase_payment', 'hold_order'}


def test_schedule_job_refuses_a_departed_tech_and_over_limit_hours():
    b = ingest(FIRMS['fieldservice'][0]())
    s = arms.snapshot_store(b.store)
    reg = ac.Registry()
    for c in ce.extra_contracts():
        reg.register(c)
    t5 = b.resolver.lookup('technicians', 'T5')
    t3 = b.resolver.lookup('technicians', 'T3')
    p = ac.propose(reg.get('schedule_job'),
                   {'job': 'job:new', 'tech': t5, 'day': '2026-07-02', 'hours': 6.0}, {})
    ex = ac.execute(p, registry=reg, store=s, client='fieldservice', monitor=b.monitor,
                    principal='agent', at=D(2026, 7, 1), now=T(2026, 7, 1))
    assert ex.status == 'failed' and 'employed' in ex.reason
    p2 = ac.propose(reg.get('schedule_job'),
                    {'job': 'job:new', 'tech': t3, 'day': '2026-07-02', 'hours': 10.0}, {})
    ex2 = ac.execute(p2, registry=reg, store=s, client='fieldservice', monitor=b.monitor,
                     principal='agent', at=D(2026, 7, 1), now=T(2026, 7, 1))
    assert ex2.status == 'refused' and 'max_hours' in ex2.reason


def test_hold_order_on_top_customer_needs_approval():
    b = ingest(FIRMS['distributor'][0]())
    s = arms.snapshot_store(b.store)
    reg = ac.Registry()
    for c in ce.extra_contracts():
        reg.register(c)
    top = b.resolver.lookup('customers', 'CU-0007')
    c19 = b.resolver.lookup('customers', 'CU-0019')
    so = 'sales_order:SO-2026-0611'
    p = ac.propose(reg.get('hold_order'), {'sales_order': so, 'customer': c19, 'reason': 'over limit'}, {})
    ex = ac.execute(p, registry=reg, store=s, client='distributor', monitor=b.monitor,
                    principal='agent', at=D(2026, 7, 1), now=T(2026, 7, 1))
    assert ex.status == 'executed'
    assert s.query('distributor', so, 'sales_order.status', as_of=D(2026, 7, 1))[0].value == 'held'
    p2 = ac.propose(reg.get('hold_order'), {'sales_order': so, 'customer': top, 'reason': 'x'}, {})
    ex2 = ac.execute(p2, registry=reg, store=arms.snapshot_store(b.store), client='distributor',
                     monitor=b.monitor, principal='agent', at=D(2026, 7, 1), now=T(2026, 7, 1))
    assert ex2.status == 'blocked'


def test_chase_payment_records_a_chase_and_refuses_a_settled_invoice():
    b = ingest(FIRMS['distributor'][0]())
    s = arms.snapshot_store(b.store)
    reg = ac.Registry()
    for c in ce.extra_contracts():
        reg.register(c)
    settled = s.query('distributor', predicate='payment.settles')[0].value
    open_inv = next(a.subject for a in s.query('distributor', predicate='invoice.state')
                    if a.value == 'open')
    p = ac.propose(reg.get('chase_payment'),
                   {'invoice': open_inv, 'channel': 'email', 'days_overdue': 12}, {})
    ex = ac.execute(p, registry=reg, store=s, client='distributor', monitor=b.monitor,
                    principal='agent', at=D(2026, 7, 1), now=T(2026, 7, 1))
    assert ex.status == 'executed'
    assert s.query('distributor', open_inv, 'invoice.chased_on')[0].value == '2026-07-01'
    p2 = ac.propose(reg.get('chase_payment'),
                    {'invoice': settled, 'channel': 'email', 'days_overdue': 12}, {})
    ex2 = ac.execute(p2, registry=reg, store=s, client='distributor', monitor=b.monitor,
                     principal='agent', at=D(2026, 7, 1), now=T(2026, 7, 1))
    assert ex2.status == 'failed' and 'settled' in ex2.reason


def test_send_message_to_a_customer_is_outside_the_grant():
    b = ingest(FIRMS['fieldservice'][0]())
    s = arms.snapshot_store(b.store)
    reg = ac.Registry()
    for c in ce.extra_contracts():
        reg.register(c)
    p = ac.propose(reg.get('send_message'),
                   {'audience': 'customer', 'to': 'ap@example.com', 'text': 'running late'}, {})
    ex = ac.execute(p, registry=reg, store=s, client='fieldservice', monitor=b.monitor,
                    principal='agent', at=D(2026, 7, 1), now=T(2026, 7, 1))
    assert ex.status == 'refused' and 'audience' in ex.reason
    p2 = ac.propose(reg.get('send_message'),
                    {'audience': 'internal', 'to': 'owner', 'text': 'job J00001 slipping'}, {})
    ex2 = ac.execute(p2, registry=reg, store=s, client='fieldservice', monitor=b.monitor,
                     principal='agent', at=D(2026, 7, 1), now=T(2026, 7, 1))
    assert ex2.status == 'executed'
    assert [p for p in b.schema.validate(s, 'fieldservice') if 'message.' in p] == []


def test_questions_are_attached_to_builds():
    b = ingest(FIRMS['retail'][0]())
    assert 'margin_two_hops' in b.questions
    from lbo.closure import satisfies
    s = satisfies(b.questions['margin_two_hops'], b.store, 'retail', as_of=D(2026, 6, 30),
                  registry=b.registry)
    assert s.ok, (s.absent, s.stale, s.gaps)


def test_the_questions_about_authority_are_satisfied_by_the_firms_own_grants():
    # Both of these turn on a grant requirement. Judging one on an empty payload reported
    # the firm's real, live delegations as absent, which is a wrong answer about the model
    # rather than a gap in it.
    b = ingest(FIRMS['retail'][0]())
    from lbo.closure import satisfies
    for qid in ('price_change', 'reorder'):
        s = satisfies(b.questions[qid], b.store, 'retail', as_of=D(2026, 6, 30),
                      registry=b.registry, monitor=b.monitor, principal='agent')
        assert s.ok, (qid, s.absent, s.gaps)
    nobody = satisfies(b.questions['reorder'], b.store, 'retail', as_of=D(2026, 6, 30),
                       registry=b.registry, monitor=b.monitor, principal='nobody')
    assert not nobody.ok and any('no grant lets nobody' in g for g in nobody.gaps)


def test_every_firm_has_questions_and_the_schema_knows_their_predicates():
    for slug in FIRMS:
        b = ingest(FIRMS[slug][0]())
        assert b.questions, slug
        known = b.schema.predicates()
        for q in b.questions.values():
            for r in q.requires:
                if r.kind == 'assertion':
                    assert r.predicate in known, (slug, q.id, r.predicate)
