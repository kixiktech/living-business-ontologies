# research/lbo/ingest.py
"""Build a firm's ontology from its source exports. One pipeline, three industries.

Each source record passes through the resolver (source id -> entity), and every field
and relation becomes an assertion carrying the record's own recorded time and a
citation to the row it came from. The build is logged as a trajectory so the paper can
print exactly what happened when a firm's data arrived.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from . import questions as qmod
from .authority import Monitor, price_change_rule
from .definitions import Registry, core_registry
from .firms import FIRMS, common as cm
from .firms.distributor import hold_order_rule
from .identity import Resolver
from .schema import Schema, core
from .store import Store
from .trajectory import Trajectory, Turn


@dataclass
class Build:
    firm: cm.Firm
    store: Store
    schema: Schema
    registry: Registry
    resolver: Resolver
    monitor: Monitor
    stats: dict
    log: Trajectory
    problems: list[str] = field(default_factory=list)
    questions: dict = field(default_factory=dict)
    # later exports applied on top of the committed ones, by source name, so the watch's
    # freshness check can see that a feed arrived after the build
    exports: dict = field(default_factory=dict)


def client_id(firm: cm.Firm) -> str:
    return firm.slug


class Ctx:
    """What a mapping handler gets: the store, the resolver, and the current record's
    evidence and recorded time already filled in."""

    def __init__(self, store: Store, resolver: Resolver, client: str, source: cm.Source):
        self.store, self.resolver, self.client, self.source = store, resolver, client, source
        self.evidence = ''
        self.recorded_at = source.exported_at
        self.entities: dict[str, int] = {}
        self.n_assert = 0
        # shared across one firm's sources: the lines of an order, so a fulfilment or a
        # stock movement keyed by order can reach them
        self.lines_by_order: dict[str, list[tuple[str, date]]] = {}
        self.counted_in: dict[str, str] = {}
        self.pending_cut: str | None = None
        self.tax_payment: str | None = None

    def begin(self, rec: dict) -> None:
        rid = rec.get(self.source.id_field, '?')
        self.evidence = f'{self.source.name} row {rid} (export {self.source.exported_at.date()})'
        stamp = rec.get('entered_on') or rec.get('synced_at')
        self.recorded_at = datetime.fromisoformat(stamp) if stamp else self.source.exported_at

    def entity(self, source: str, source_id: str, etype: str, attrs: dict, at: date) -> str:
        eid = self.resolver.register(source, str(source_id), etype, attrs, at,
                                     recorded_at=self.recorded_at, evidence=self.evidence)
        self.entities[eid] = self.entities.get(eid, 0) + 1
        return eid

    def assert_(self, subject: str, predicate: str, value, at: date, until: date | None = None,
                status: str = 'observed') -> int:
        self.n_assert += 1
        return self.store.assert_(self.client, subject, predicate, value, at, until, evidence=self.evidence,
                                  status=status, recorded_at=self.recorded_at)

    def relate(self, subject: str, predicate: str, obj: str, at: date, until: date | None = None) -> int:
        return self.assert_(subject, predicate, obj, at, until)

    def replace(self, subject: str, predicate: str, value, at: date) -> int:
        """Close any open value at `at` and open the new one (a cost that changed)."""
        for old in self.store.query(self.client, subject, predicate):
            if old.valid_to is None and old.valid_from < at:
                self.store.supersede(old.id, valid_to=at, evidence=self.evidence, recorded_at=self.recorded_at)
        return self.assert_(subject, predicate, value, at)


# ---- retail ---------------------------------------------------------------------------

def _r_store_map(rec, ctx: Ctx):
    loc = f'location:{rec["store"]}'
    opened = date.fromisoformat(rec['opened_on'])
    ctx.assert_(loc, 'location.name', rec['name'], opened)
    ctx.assert_(loc, 'location.sqft', rec['sqft'], opened)


def _r_product_master(rec, ctx: Ctx):
    pid = ctx.entity('product_master', rec['item_no'], 'product',
                     {'sku': rec['sku'], 'name': rec['name'], 'category': rec['category'],
                      'list_price': rec['list_price']}, cm.START)
    if rec.get('supplier'):
        sid = ctx.entity('product_master', rec['supplier'], 'supplier', {'name': rec['supplier']}, cm.START)
        ctx.relate(pid, 'product.supplied_by', sid, cm.START)
    if rec.get('unit_cost') is not None:
        ctx.assert_(pid, 'product.unit_cost', rec['unit_cost'], cm.START)


def _r_customers(rec, ctx: Ctx):
    ctx.entity('customers', rec['cust_id'], 'party',
               {'name': rec['name'], 'email': rec['email'], 'phone': rec['phone']},
               date.fromisoformat(rec['created_on']))


def _r_staff(rec, ctx: Ctx):
    hired = date.fromisoformat(rec['hired_on'])
    pid = ctx.entity('staff', rec['employee_id'], 'person',
                     {'name': rec['name'], 'role': rec['role'], 'hourly_cost': rec['hourly_cost']}, hired)
    ctx.relate(pid, 'person.works_at', f'location:{rec["store"]}', hired)
    if rec['role'] == 'manager':
        ctx.relate(f'location:{rec["store"]}', 'location.manager', pid, hired)


def _r_pos(rec, ctx: Ctx):
    d = date.fromisoformat(rec['sold_on'])
    ln = f'order_line:{rec["line_id"]}'
    order = f'order:{rec["order_id"]}'
    prod = ctx.resolver.lookup('product_master', rec['item_no'])
    ctx.assert_(ln, 'order_line.qty', rec['qty'], d)
    ctx.assert_(ln, 'order_line.unit_price', rec['unit_price'], d)
    ctx.assert_(ln, 'order_line.sold_at', rec['sold_on'], d)
    ctx.relate(ln, 'order_line.of_order', order, d)
    if prod:
        ctx.relate(ln, 'order_line.of_product', prod, d)
    ctx.relate(ln, 'order_line.rang_up_at', f'location:{rec["store"]}', d)
    cashier = ctx.resolver.lookup('staff', rec['cashier'])
    if cashier:
        ctx.relate(ln, 'order_line.credited_to', cashier, d)
    counted = ctx.counted_in.get(rec['store'], rec['store']) if d.year == 2025 else rec['store']
    ctx.relate(ln, 'order_line.counted_in', f'location:{counted}', d)
    ctx.assert_(order, 'order.placed_at', rec['sold_on'], d)
    cust = ctx.resolver.lookup('customers', rec['cust_id'])
    if cust:
        ctx.relate(order, 'order.placed_by', cust, d)
    ctx.lines_by_order.setdefault(rec['order_id'], []).append((ln, d))


def _r_fulfillment(rec, ctx: Ctx):
    for ln, d in ctx.lines_by_order.get(rec['order_id'], []):
        ctx.relate(ln, 'order_line.fulfilled_from', f'location:{rec["shipped_from"]}', d)


def _r_moves(rec, ctx: Ctx):
    oid = 'O' + rec['move_id'][1:]
    for ln, d in ctx.lines_by_order.get(oid, []):
        ctx.relate(ln, 'order_line.stock_drawn_from', f'location:{rec["from_store"]}', d)


def _r_terms(rec, ctx: Ctx):
    sid = ctx.entity('product_master', rec['supplier'], 'supplier', {'name': rec['supplier']}, cm.START)
    ctx.assert_(sid, 'supplier.terms',
                {'break_units_per_quarter': rec['break_units_per_quarter'], 'tiers': rec['tiers'],
                 'rule': rec['rule']}, date.fromisoformat(rec['effective_on']))


def _r_ledger(rec, ctx: Ctx):
    eff = date.fromisoformat(rec['effective_on'])
    if rec['kind'] == 'supplier_invoice':
        prod = ctx.resolver.lookup('product_master', rec['item_no'])
        ctx.replace(prod, 'product.unit_cost', rec['unit_cost'], eff)
    elif rec['kind'] == 'purchase_order':
        po = f'purchase_order:{rec["journal_id"]}'
        ctx.assert_(po, 'purchase_order.qty', rec['units'], eff)
        ctx.assert_(po, 'purchase_order.units_a', rec['units_a'], eff)
        ctx.assert_(po, 'purchase_order.units_b', rec['units_b'], eff)
        ctx.assert_(po, 'purchase_order.amount', rec['amount'], eff)
        ctx.assert_(po, 'purchase_order.placed_on', rec['effective_on'], eff)
        ctx.assert_(po, 'purchase_order.status', 'placed', eff)
        sid = ctx.entity('product_master', rec['supplier'], 'supplier', {'name': rec['supplier']}, cm.START)
        ctx.relate(po, 'purchase_order.from_supplier', sid, eff)
        if 'reduced' in rec['memo']:
            ctx.pending_cut = po
    elif rec['kind'] == 'payment':
        pay = f'payment:{rec["journal_id"]}'
        ctx.assert_(pay, 'payment.paid_at', rec['effective_on'], eff)
        ctx.assert_(pay, 'payment.amount', rec['amount'], eff)
        ctx.assert_(pay, 'payment.method', rec.get('account', 'bank'), eff)
        if 'tax' in rec['memo']:
            ctx.tax_payment = pay


def _r_payroll(rec, ctx: Ctx):
    pid = ctx.resolver.lookup('staff', rec['employee_id'])
    if pid:
        ws = date.fromisoformat(rec['week_start'])
        ctx.assert_(f'schedule:{rec["employee_id"]}-{rec["week_start"]}', 'schedule.hours',
                    {'tech': pid, 'day': rec['week_start'], 'hours': rec['hours']}, ws)


RETAIL_MAP = [('store_map', _r_store_map), ('product_master', _r_product_master), ('customers', _r_customers),
              ('staff', _r_staff), ('pos_sales', _r_pos), ('fulfillment', _r_fulfillment),
              ('inventory_moves', _r_moves), ('supplier_terms', _r_terms), ('ledger', _r_ledger),
              ('payroll', _r_payroll)]


# ---- field service ----------------------------------------------------------------------

def _f_technicians(rec, ctx: Ctx):
    hired = date.fromisoformat(rec['hired_on'])
    left = date.fromisoformat(rec['left_on']) if rec.get('left_on') else None
    pid = ctx.entity('technicians', rec['tech_id'], 'person',
                     {'name': rec['name'], 'role': 'technician', 'hourly_cost': rec['hourly_cost']}, hired)
    ctx.assert_(pid, 'person.employed', True, hired, left)
    ctx.relate(pid, 'person.in_crew', f'crew:{rec["crew"]}', hired, left)
    ctx.assert_(f'crew:{rec["crew"]}', 'crew.name', rec['crew'], cm.START)


def _f_certifications(rec, ctx: Ctx):
    pid = ctx.resolver.lookup('technicians', rec['tech'])
    cert = f'certification:{rec["certification"]}'
    ctx.assert_(cert, 'certification.name', rec['certification'], cm.START)
    if pid:
        ctx.relate(pid, 'person.holds', cert, date.fromisoformat(rec['issued_on']))


def _f_policy_requirements(ctx: Ctx):
    ctx.evidence = 'policy.md, Scheduling: certified service lines'
    ctx.recorded_at = cm.NOW
    ctx.assert_('service_line:backflow', 'service_line.name', 'backflow', cm.START)
    ctx.relate('service_line:backflow', 'service_line.requires', 'certification:backflow-tester', cm.START)


def _f_leads(rec, ctx: Ctx):
    d = date.fromisoformat(rec['created_on'])
    lead = f'lead:{rec["lead_id"]}'
    ctx.assert_(lead, 'lead.created_on', rec['created_on'], d)
    ctx.assert_(lead, 'lead.channel', rec['channel'], d)
    ctx.assert_(lead, 'lead.status', rec['status'], d)
    ctx.assert_(f'channel:{rec["channel"]}', 'channel.name', rec['channel'], cm.START)
    ctx.relate(lead, 'lead.via_channel', f'channel:{rec["channel"]}', d)


def _f_jobs(rec, ctx: Ctx):
    d = date.fromisoformat(rec['performed_on'])
    job = f'job:{rec["job_id"]}'
    for k in ('scheduled_on', 'performed_on', 'revenue', 'direct_cost', 'hours', 'service_line'):
        ctx.assert_(job, f'job.{k}', rec[k], d)
    ctx.relate(job, 'job.from_lead', f'lead:{rec["lead_id"]}', d)
    ctx.relate(job, 'job.scheduled_for', f'crew:{rec["scheduled_crew"]}', d)
    ctx.relate(job, 'job.performed_by', f'crew:{rec["performed_crew"]}', d)
    ctx.assert_(f'service_line:{rec["service_line"]}', 'service_line.name', rec['service_line'], cm.START)
    ctx.relate(job, 'job.in_service_line', f'service_line:{rec["service_line"]}', d)
    tech = ctx.resolver.lookup('technicians', rec['tech'])
    if tech:
        ctx.relate(job, 'job.assigned_tech', tech, d)


def _f_schedule(rec, ctx: Ctx):
    tech = ctx.resolver.lookup('technicians', rec['tech'])
    d = date.fromisoformat(rec['day'])
    ctx.assert_(f'schedule:{rec["entry_id"]}', 'schedule.hours',
                {'tech': tech, 'day': rec['day'], 'hours': rec['hours']}, d)


def _f_ledger(rec, ctx: Ctx):
    eff = date.fromisoformat(rec['effective_on'])
    ctx.assert_(f'channel:{rec["channel"]}', 'channel.spend_on',
                {'effective_on': rec['effective_on'], 'amount': rec['amount']}, eff)


def _f_payroll(rec, ctx: Ctx):
    pass  # paid hours are not used by any competency question; the admission rule keeps them out


FIELDSERVICE_MAP = [('technicians', _f_technicians), ('certifications', _f_certifications), ('crm_leads', _f_leads),
                    ('jobs', _f_jobs), ('schedule', _f_schedule), ('ledger', _f_ledger), ('payroll', _f_payroll)]


# ---- distributor ---------------------------------------------------------------------

def _d_customers(rec, ctx: Ctx):
    pid = ctx.entity('customers', rec['customer_no'], 'party',
                     {'name': rec['name'], 'email': rec['email'], 'phone': ''}, cm.START)
    ctx.relate(pid, 'party.on_route', f'route:{rec["route"]}', cm.START)
    terms = f'credit_terms:{rec["customer_no"]}'
    ctx.assert_(terms, 'credit_terms.days', rec['terms_days'], cm.START)
    ctx.assert_(terms, 'credit_terms.limit', rec['credit_limit'], cm.START)
    ctx.relate(pid, 'party.has_terms', terms, cm.START)


def _d_routes(rec, ctx: Ctx):
    ctx.assert_(f'route:{rec["route"]}', 'route.name', rec['name'], cm.START)
    ctx.assert_(f'route:{rec["route"]}', 'route.weekly_cost', rec['weekly_cost'], cm.START)


def _d_products(rec, ctx: Ctx):
    pid = ctx.entity('products', rec['sku'], 'product',
                     {'sku': rec['sku'], 'name': rec['name'], 'category': 'case goods',
                      'unit_cost': rec['unit_cost'], 'list_price': rec['unit_price']}, cm.START)
    sid = ctx.entity('products', rec['supplier'], 'supplier', {'name': rec['supplier']}, cm.START)
    ctx.relate(pid, 'product.supplied_by', sid, cm.START)
    sp = f'stock_position:{rec["sku"]}'
    ctx.assert_(sp, 'stock_position.qty', rec['on_hand'], date(2026, 6, 30))
    ctx.assert_(sp, 'stock_position.daily_demand', rec['daily_demand'], date(2026, 6, 30))
    ctx.relate(sp, 'stock_position.of_product', pid, date(2026, 6, 30))


def _d_leadtimes(rec, ctx: Ctx):
    pid = ctx.resolver.lookup('products', rec['sku'])
    lt = f'supplier_lead_time:{rec["sku"]}'
    ctx.assert_(lt, 'supplier_lead_time.days', rec['lead_time_days'], date.fromisoformat(rec['as_of']))
    if pid:
        ctx.relate(lt, 'supplier_lead_time.for_product', pid, date.fromisoformat(rec['as_of']))


def _d_invoices(rec, ctx: Ctx):
    d = date.fromisoformat(rec['issued_on'])
    inv = f'invoice:{rec["invoice_no"]}'
    ctx.assert_(inv, 'invoice.issued_at', rec['issued_on'], d)
    ctx.assert_(inv, 'invoice.due_at', rec['due_on'], d)
    ctx.assert_(inv, 'invoice.amount', rec['amount'], d)
    ctx.assert_(inv, 'invoice.currency', 'usd', d)
    ctx.assert_(inv, 'invoice.state', rec['status'], d)
    gp = cm.money(sum((x['unit_price'] - x['unit_cost']) * x['qty'] for x in rec['lines']))
    ctx.assert_(inv, 'invoice.gross_profit', gp, d)
    who = ctx.resolver.lookup('customers', rec['customer_no'])
    if who:
        ctx.relate(inv, 'invoice.billed_to', who, d)
    ctx.relate(inv, 'invoice.delivered_on_route', f'route:{rec["route"]}', d)


def _d_payments(rec, ctx: Ctx):
    d = date.fromisoformat(rec['paid_on'])
    pay = f'payment:{rec["payment_no"]}'
    ctx.assert_(pay, 'payment.paid_at', rec['paid_on'], d)
    ctx.assert_(pay, 'payment.amount', rec['amount'], d)
    ctx.assert_(pay, 'payment.method', 'bank', d)
    ctx.relate(pay, 'payment.settles', f'invoice:{rec["invoice_no"]}', d)


def _d_ledger(rec, ctx: Ctx):
    eff = date.fromisoformat(rec['effective_on'])
    if rec['kind'] == 'route_cost':
        ctx.assert_(f'route:{rec["route"]}', 'route.quarter_cost',
                    {'effective_on': rec['effective_on'], 'amount': rec['amount']}, eff)
    elif rec['kind'] == 'pending_order':
        so = f'sales_order:{rec["order_no"]}'
        ctx.assert_(so, 'sales_order.amount', rec['amount'], eff)
        ctx.assert_(so, 'sales_order.placed_on', rec['placed_on'], eff)
        ctx.assert_(so, 'sales_order.status', rec['status'], eff)
        who = ctx.resolver.lookup('customers', rec['customer_no'])
        if who:
            ctx.relate(so, 'sales_order.for_party', who, eff)


DISTRIBUTOR_MAP = [('customers', _d_customers), ('routes', _d_routes), ('products', _d_products),
                   ('supplier_leadtimes', _d_leadtimes), ('erp_invoices', _d_invoices),
                   ('erp_payments', _d_payments), ('ledger', _d_ledger)]

MAPS = {'retail': RETAIL_MAP, 'fieldservice': FIELDSERVICE_MAP, 'distributor': DISTRIBUTOR_MAP}


def _supplier_entity(store: Store, client: str, resolver: Resolver, name: str) -> str | None:
    """The supplier an owner's letter names, as an entity.

    A letter of authority names a supplier the way a person does, by name, because the
    entity it will be checked against does not exist until the item master has been read.
    Resolving it at load time is the same move as resolving any other source identifier,
    and it has to happen here: the monitor compares a grant's scope against an action's
    payload key for key, and an action carries its supplier as an entity, not as a name.
    """
    eid = resolver.lookup('product_master', name)
    if eid:
        return eid
    rows = store.query(client, predicate='supplier.name', value=name)
    return rows[0].subject if rows else None


def _grants(firm: cm.Firm, store: Store, client: str, resolver: Resolver) -> int:
    n = 0
    for i, g in enumerate(firm.grants):
        subj = f'grant:g{i + 1}'
        vf = date.fromisoformat(g['valid_from'])
        scope = dict(g['scope'])
        name = scope.pop('supplier_name', None)
        if name is not None:
            eid = _supplier_entity(store, client, resolver, name)
            # Unresolved, the letter's own words stay in the scope rather than becoming a
            # grant that matches everything: a supplier we cannot find is a refusal.
            scope['supplier' if eid else 'supplier_name'] = eid or name
        for k, value in (('principal', g['principal']), ('action', g['action']),
                         ('scope', scope), ('limits', g['limits'])):
            store.assert_(client, subj, f'grant.{k}', value, vf,
                          evidence='owner letter of authority', recorded_at=cm.NOW)
        n += 1
    return n


def ingest(firm: cm.Firm, *, store: Store | None = None, known_at: datetime = cm.NOW,
           identity_keys: dict | None = None) -> Build:
    _build_fn, extension, definitions = FIRMS[firm.slug]
    schema = extension(core())
    registry = definitions(core_registry())
    store = store or Store()
    client = client_id(firm)
    resolver = Resolver(store, client, keys=identity_keys)
    lines_by_order: dict[str, list[tuple[str, date]]] = {}
    counted_in = ({r['store']: r['counted_in_2025'] for r in firm.sources['store_map'].records}
                  if 'store_map' in firm.sources else {})
    turns: list[Turn] = []
    for source_name, handler in MAPS[firm.slug]:
        src = firm.sources[source_name]
        ctx = Ctx(store, resolver, client, src)
        ctx.lines_by_order = lines_by_order       # shared across this firm's sources
        ctx.counted_in = counted_in
        before = store.count(client)
        for rec in src.records:
            ctx.begin(rec)
            handler(rec, ctx)
        if firm.slug == 'retail' and source_name == 'ledger' and ctx.pending_cut and ctx.tax_payment:
            store.assert_(client, ctx.pending_cut, 'purchase_order.cut_for', ctx.tax_payment, date(2026, 1, 10),
                          evidence='ledger memo: reduced from 620 to 470 per cash plan; tax payment 2026-01-08',
                          recorded_at=cm.NOW)
        turns.append(Turn(role='tool', kind='tool_result', name=source_name,
                          text=f'{len(src.records)} records -> {len(ctx.entities)} entities, '
                               f'{store.count(client) - before} assertions'))
    if firm.slug == 'fieldservice':
        _f_policy_requirements(Ctx(store, resolver, client, firm.sources['jobs']))
    n_grants = _grants(firm, store, client, resolver)
    rules = []
    if firm.slug == 'retail':
        rules.append(price_change_rule(5.0))
    if firm.slug == 'distributor':
        focal = next(x for x in cm.quarters() if x[0] == '2026Q2')
        conc = registry.compute('customer_concentration', store, client, (focal[1], focal[2]))
        rules.append(hold_order_rule(set(conc.value['top5'])))
    monitor = Monitor.from_store(store, client, rules, at=known_at.date())
    problems = schema.validate(store, client)
    queue = resolver.review_queue()
    by_type: dict[str, int] = {}
    for a in store.query(client):
        by_type[a.subject.split(':', 1)[0]] = by_type.get(a.subject.split(':', 1)[0], 0) + 1
    stats = {'assertions': store.count(client), 'assertions_by_subject_type': by_type,
             'relation_types_used': len({a.predicate for a in store.query(client)
                                         if a.predicate in schema.relations}),
             'review_queue': len(queue), 'sources': len(firm.sources),
             'records_per_source': {k: len(v.records) for k, v in firm.sources.items()},
             'schema_counts': schema.counts(), 'grants': n_grants, 'problems': len(problems)}
    turns.append(Turn(role='reflect', kind='message', name='identity review',
                      text='\n'.join(f'{c.a} ~ {c.b}: {c.reason}' for c in queue) or 'no ambiguous matches'))
    turns.append(Turn(role='monitor', kind='message', name='grants',
                      text='\n'.join(f'{g["principal"]} may {g["action"]} scope={g["scope"]} limits={g["limits"]}'
                                     for g in firm.grants)))
    turns.append(Turn(role='agent', kind='message', text=(
        f'{firm.name}: {stats["assertions"]} assertions from {stats["sources"]} sources; '
        f'{stats["relation_types_used"]} relation types in use; {stats["review_queue"]} identity candidates '
        f'for review; {len(problems)} schema problems')))
    log = Trajectory(firm=firm.slug, arm='build', task='ingest', model='none', date=known_at.date().isoformat(),
                     turns=turns, score={}, meta={'fingerprint': cm.fingerprint(firm)})
    return Build(firm, store, schema, registry, resolver, monitor, stats, log, problems,
                 questions=qmod.for_firm(firm.slug))
