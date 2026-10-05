# research/lbo/firms/distributor.py
"""A wholesale distributor: credit terms, receivables, routes, supplier lead times.

Planted structure (answer key):
  * one customer is 38% of revenue and pays a month late;
  * one delivery route costs more to run than the margin it carries;
  * one customer is over its credit limit with an order waiting (the hold decision);
  * one product's supplier lead time is longer than its stock cover (the reorder catch).
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from ..authority import Rule
from ..definitions import MetricDefinition, Registry, matches
from ..schema import EntityType, RelationType, Schema
from . import common as cm

SLUG = 'distributor'
FOCAL_Q = '2026Q2'
WEEKS_PER_QUARTER = 13
# Weekly truck, driver and fuel cost per route. Thirteen weeks of the South loop is
# 6,500.00 a quarter, which is the number the planted case turns on.
ROUTES = [('R1', 'North loop', 400.0), ('R2', 'City', 380.0), ('R3', 'South loop', 500.0)]
TOP_CUSTOMER = 'CU-0007'
TOP_SHARE = 0.38
# Customers are not all the same size, so that "the five largest" names a real set. Four
# accounts buy at a multiple of an ordinary one; the customer with the credit problem is a
# small account whose only large invoices are the two it has not paid. The multiple has to
# clear that unpaid pair (14,300.00, about six quarters of an ordinary account), or those
# two invoices alone would carry CU-0019 into the top five, which is the collision this
# replaces. The rest total is untouched, so concentration stays at TOP_SHARE by
# construction. `test_distributor` pins the resulting membership.
LARGE_CUSTOMERS = ('CU-0002', 'CU-0003', 'CU-0004', 'CU-0005')
LARGE_MULTIPLE = 10.0
OVER_LIMIT_CUSTOMER = 'CU-0019'
OVER_LIMIT_MULTIPLE = 0.5
OVER_LIMIT_INVOICES = (8000.0, 6300.0)
OVER_LIMIT_CREDIT = 12000.0
R3_TARGET_GP = 4200.0
LONG_LEAD_SKU = 'SKU-D14'
LONG_LEAD_DAYS = 45
STOCK_COVER_DAYS = 20

POLICY = """# Operating policy: credit and collections

## Collections
- The data team may send a payment reminder by email for any invoice up to 90 days
  overdue. Invoices more than 90 days overdue are escalated to the owner.

## Credit holds
- An order for a customer over their credit limit is held until the owner decides.
- A hold on any of the five largest customers by revenue needs the owner's explicit
  approval before it is applied.

## Routes
- Route costs are reviewed quarterly against the margin the route carries.
"""


def hold_order_rule(top5: set[str]) -> Rule:
    def needs(payload: dict) -> str | None:
        if payload.get('customer') in top5:
            return f'{payload["customer"]} is one of the five largest customers; a hold needs explicit approval'
        return None
    return Rule('hold_order', 'a hold on a top-five customer needs explicit approval', needs)


def build(seed: int = 13) -> cm.Firm:
    r = random.Random(seed)
    qs = cm.quarters()
    focal = next(x for x in qs if x[0] == FOCAL_Q)
    # Index 6 is CU-0007, the largest customer, and it is Baylor Foods: the name the owner
    # uses for them, so the tasks can be written the way an owner would write them.
    names = ['Hilltop Market', 'Crest Market', 'Delta Grocers', 'Elm Street Deli', 'Fjord Cafe',
             'Granite Bistro', 'Baylor Foods', 'Iris Bakery', 'Juniper Foods', 'Kestrel Catering']
    customers = []
    for i in range(80):
        cid = f'CU-{i + 1:04d}'
        customers.append({'customer_no': cid, 'name': names[i % 10] + (f' {i // 10 + 1}' if i >= 10 else ''),
                          'terms_days': 30,
                          'credit_limit': OVER_LIMIT_CREDIT if cid == OVER_LIMIT_CUSTOMER else round(r.uniform(8000, 40000), -2),
                          'route': ROUTES[i % 3][0], 'email': f'ap{i}@example.com'})
    by_no = {c['customer_no']: c for c in customers}
    products = [{'sku': f'SKU-D{i:02d}', 'name': f'Case goods {i}', 'unit_cost': round(r.uniform(6, 30), 2),
                 'unit_price': 0.0, 'supplier': f'Supplier {i % 6}'} for i in range(40)]
    for p in products:
        p['unit_price'] = round(p['unit_cost'] * r.uniform(1.18, 1.35), 2)
    leadtimes = [{'sku': p['sku'], 'supplier': p['supplier'],
                  'lead_time_days': LONG_LEAD_DAYS if p['sku'] == LONG_LEAD_SKU else r.randint(5, 14),
                  'as_of': '2026-01-01'} for p in products]
    stock = [{'sku': p['sku'], 'on_hand': STOCK_COVER_DAYS * 8 if p['sku'] == LONG_LEAD_SKU else r.randint(200, 800),
              'daily_demand': 8 if p['sku'] == LONG_LEAD_SKU else r.randint(4, 12), 'as_of': '2026-06-30'}
             for p in products]

    invoices: list[dict] = []
    payments: list[dict] = []
    counters = {'inv': 0, 'pay': 0}
    weekdays = [cm.START + timedelta(days=i) for i in range((cm.END - cm.START).days)]
    weekdays = [d for d in weekdays if d.weekday() < 5]
    max_price = max(p['unit_price'] for p in products)

    def build_lines(amt: float) -> list[dict]:
        """Lines that sum to `amt` to the cent. The last line is a single unit priced at
        whatever is left, the way a short case or a part line reads on a real invoice."""
        lines, acc = [], 0.0
        while amt - acc > max_price + 1.0:
            p = products[r.randint(0, 39)]
            qty = max(1, min(r.randint(5, 40), int((amt - acc) // p['unit_price'])))
            lines.append({'sku': p['sku'], 'qty': qty, 'unit_price': p['unit_price'], 'unit_cost': p['unit_cost']})
            acc = round(acc + qty * p['unit_price'], 2)
        rest = round(amt - acc, 2)
        if rest > 0:
            p = products[r.randint(0, 39)]
            lines.append({'sku': p['sku'], 'qty': 1, 'unit_price': rest,
                          'unit_cost': round(p['unit_cost'] / p['unit_price'] * rest, 2)})
        return lines

    def pay_lag(cust: str) -> int:
        if cust == TOP_CUSTOMER:
            return 62 + r.randint(-4, 4)
        if cust == OVER_LIMIT_CUSTOMER:
            return 7
        return 28 + r.randint(-6, 6)

    def make_invoice(cust: str, day: date, amt: float, *, pay: bool) -> dict:
        counters['inv'] += 1
        row = by_no[cust]
        lines = build_lines(amt)
        total = cm.money(sum(x['qty'] * x['unit_price'] for x in lines))
        inv = {'invoice_no': f'INV{counters["inv"]:06d}', 'customer_no': cust, 'issued_on': day.isoformat(),
               'entered_on': day.isoformat(),
               'due_on': (day + timedelta(days=row['terms_days'])).isoformat(), 'amount': total,
               'route': row['route'], 'delivered_on': day.isoformat(), 'lines': lines, 'status': 'open'}
        invoices.append(inv)
        if pay:
            paid_on = day + timedelta(days=pay_lag(cust))
            if paid_on < cm.END:
                counters['pay'] += 1
                payments.append({'payment_no': f'PAY{counters["pay"]:06d}', 'invoice_no': inv['invoice_no'],
                                 'paid_on': paid_on.isoformat(), 'amount': total,
                                 'entered_on': (paid_on + timedelta(days=1)).isoformat()})
                inv['status'] = 'paid'
        return inv

    others = [c['customer_no'] for c in customers if c['customer_no'] != TOP_CUSTOMER]
    n_top, n_rest = 26, 26 * 8
    q_total_target = 300000.0

    def weight(cust: str) -> float:
        if cust in LARGE_CUSTOMERS:
            return LARGE_MULTIPLE
        if cust == OVER_LIMIT_CUSTOMER:
            return OVER_LIMIT_MULTIPLE
        return 1.0

    # One ordinary invoice, sized so the weighted invoices still sum to the rest total.
    unit = sum(weight(others[i % len(others)]) for i in range(n_rest))
    for q, qs_, qe in qs:
        days = [d for d in weekdays if qs_ <= d < qe]
        rest_amt = q_total_target * (1 - TOP_SHARE)
        quarter_start = len(invoices)
        for i in range(n_rest):
            who = others[i % len(others)]
            make_invoice(who, days[i * len(days) // n_rest], rest_amt * weight(who) / unit, pay=True)
        if q == FOCAL_Q:
            # the planted pair: two invoices the customer has not paid, which put it over
            # its credit limit while a new order waits
            for j, amt in enumerate(OVER_LIMIT_INVOICES):
                make_invoice(OVER_LIMIT_CUSTOMER, days[len(days) - 4 + j], amt, pay=False)
        # the top customer is sized against what everyone else actually invoiced, so its
        # share of the quarter is the planted one and not an artefact of line rounding
        others_total = sum(x['amount'] for x in invoices[quarter_start:])
        top_total = others_total * TOP_SHARE / (1 - TOP_SHARE)
        for i in range(n_top):
            make_invoice(TOP_CUSTOMER, days[i * len(days) // n_top], top_total / n_top, pay=True)

    pending = {'order_no': 'SO-2026-0611', 'customer_no': OVER_LIMIT_CUSTOMER, 'amount': 2400.0,
               'placed_on': '2026-06-28', 'status': 'pending'}

    # route R3 loses money: scale its focal-quarter line costs so its gross profit is 4,200.00
    r3 = [x for x in invoices if x['route'] == 'R3' and focal[1] <= date.fromisoformat(x['issued_on']) < focal[2]]
    r3_rev = sum(x['amount'] for x in r3)
    for x in r3:
        for line in x['lines']:
            line['unit_cost'] = round(line['unit_price'] * (1 - R3_TARGET_GP / r3_rev), 4)
    ledger = [{'journal_id': f'J-{q}-{rt}', 'kind': 'route_cost', 'route': rt,
               'amount': cm.money(cost * WEEKS_PER_QUARTER), 'effective_on': qs_.isoformat(),
               'entered_on': (qs_ + timedelta(days=2)).isoformat(), 'memo': f'{name} truck, driver, fuel'}
              for q, qs_, qe in qs for rt, name, cost in ROUTES]

    def route_gp(rt: str) -> float:
        return cm.money(sum((line['unit_price'] - line['unit_cost']) * line['qty']
                            for x in invoices if x['route'] == rt
                            and focal[1] <= date.fromisoformat(x['issued_on']) < focal[2]
                            for line in x['lines']))

    def route_cost(rt: str) -> float:
        return next(x['amount'] for x in ledger if x['route'] == rt and x['effective_on'] == focal[1].isoformat())

    contribution = {rt: {'gross_profit': route_gp(rt), 'route_cost': route_cost(rt),
                         'contribution': cm.money(route_gp(rt) - route_cost(rt))} for rt, _, _ in ROUTES}

    # aging as of the focal quarter end
    as_of = focal[2] - timedelta(days=1)
    paid_by = {p['invoice_no']: date.fromisoformat(p['paid_on']) for p in payments}
    aging = {'current': 0.0, '1-30': 0.0, '31-60': 0.0, '61-90': 0.0, '90+': 0.0}
    open_rows = []
    for x in invoices:
        if date.fromisoformat(x['issued_on']) > as_of:
            continue
        if x['invoice_no'] in paid_by and paid_by[x['invoice_no']] <= as_of:
            continue
        over = (as_of - date.fromisoformat(x['due_on'])).days
        b = ('current' if over <= 0 else '1-30' if over <= 30 else '31-60' if over <= 60
             else '61-90' if over <= 90 else '90+')
        aging[b] = cm.money(aging[b] + x['amount'])
        open_rows.append(x)
    open_total = sum(aging.values())
    focal_sales = sum(x['amount'] for x in invoices if focal[1] <= date.fromisoformat(x['issued_on']) < focal[2])
    dso = round(open_total / (focal_sales / (focal[2] - focal[1]).days), 1)

    by_customer: dict[str, float] = {}
    for x in invoices:
        if focal[1] <= date.fromisoformat(x['issued_on']) < focal[2]:
            by_customer[x['customer_no']] = by_customer.get(x['customer_no'], 0.0) + x['amount']
    top5 = [c for c, _ in sorted(by_customer.items(), key=lambda kv: -kv[1])[:5]]
    baylor = [x for x in invoices if x['customer_no'] == TOP_CUSTOMER and x['invoice_no'] in paid_by]
    avg_days = round(sum((paid_by[x['invoice_no']] - date.fromisoformat(x['issued_on'])).days
                         for x in baylor) / len(baylor), 1)
    key = {
        'focal_quarter': FOCAL_Q, 'top_customer': TOP_CUSTOMER,
        'top_customer_pct': cm.pct(by_customer[TOP_CUSTOMER], sum(by_customer.values())),
        'top_customer_avg_days_to_pay': avg_days, 'top_customer_terms_days': 30,
        'losing_route': 'R3', 'losing_route_gp': contribution['R3']['gross_profit'],
        'losing_route_cost': contribution['R3']['route_cost'],
        'route_contribution': contribution,
        'over_limit_customer': OVER_LIMIT_CUSTOMER,
        'over_limit_open': cm.money(sum(x['amount'] for x in open_rows
                                        if x['customer_no'] == OVER_LIMIT_CUSTOMER)),
        'over_limit_limit': OVER_LIMIT_CREDIT,
        'pending_order_no': pending['order_no'],
        'aging': aging, 'open_receivables': cm.money(open_total), 'dso_days': dso,
        'long_lead_sku': LONG_LEAD_SKU, 'long_lead_days': LONG_LEAD_DAYS,
        'stock_cover_days': STOCK_COVER_DAYS,
        'top5': top5,
    }
    grants = [{'principal': 'agent', 'action': 'chase_payment', 'scope': {'channel': 'email'},
               'limits': {'max_days_overdue': 90}, 'valid_from': '2026-01-01'},
              {'principal': 'agent', 'action': 'hold_order', 'scope': {}, 'limits': {}, 'valid_from': '2026-01-01'}]
    return cm.Firm(SLUG, 'Cobalt Provisions', 'wholesale distribution', seed, {
        'erp_invoices': cm.Source('erp_invoices', cm.NOW, invoices, 'invoice_no',
                                  'invoices with embedded lines, route and delivery date'),
        'erp_payments': cm.Source('erp_payments', cm.NOW, payments, 'payment_no',
                                  'payments against invoices; entered the day after receipt'),
        'customers': cm.Source('customers', cm.NOW, customers, 'customer_no',
                               'customers with terms, credit limit and route'),
        'routes': cm.Source('routes', cm.NOW, [{'route': rt, 'name': n, 'weekly_cost': c} for rt, n, c in ROUTES],
                            'route', 'delivery routes and weekly cost'),
        'supplier_leadtimes': cm.Source('supplier_leadtimes', datetime(2026, 1, 3, 9, 0), leadtimes, 'sku',
                                        'supplier lead times by product'),
        'products': cm.Source('products', cm.NOW,
                              [dict(p, on_hand=s['on_hand'], daily_demand=s['daily_demand'])
                               for p, s in zip(products, stock)], 'sku',
                              'products with cost, price, stock and demand'),
        'ledger': cm.Source('ledger', cm.NOW,
                            ledger + [dict(pending, journal_id='J-PENDING', kind='pending_order',
                                           effective_on=pending['placed_on'], entered_on=pending['placed_on'],
                                           memo='sales order awaiting credit decision')],
                            'journal_id', 'route costs and the pending order'),
    }, POLICY, grants, key, notes=['CU-0019 is over its credit limit with a pending order'])


def extension(core: Schema) -> Schema:
    E, R = EntityType, RelationType
    return core.extend('distributor', [
        E('route', 'extension', ('name', 'weekly_cost', 'quarter_cost'), ('route_contribution',)),
        E('credit_terms', 'extension', ('days', 'limit'), ('credit_hold',)),
        E('supplier_lead_time', 'extension', ('days',), ('reorder',)),
        E('stock_position', 'extension', ('qty', 'daily_demand'), ('reorder',)),
        E('sales_order', 'extension', ('amount', 'placed_on', 'status'), ('credit_hold',)),
    ], [
        R('party.on_route', 'party', 'route', 'extension', ('route_contribution',)),
        R('party.has_terms', 'party', 'credit_terms', 'extension', ('credit_hold',)),
        R('invoice.delivered_on_route', 'invoice', 'route', 'extension', ('route_contribution',)),
        R('supplier_lead_time.for_product', 'supplier_lead_time', 'product', 'extension', ('reorder',)),
        R('stock_position.of_product', 'stock_position', 'product', 'extension', ('reorder',)),
        R('sales_order.for_party', 'sales_order', 'party', 'extension', ('credit_hold',)),
    ])


def _invoices_in(store, client, window, known_at, filters=None):
    for a in store.query(client, predicate='invoice.issued_at', known_at=known_at):
        d = date.fromisoformat(a.value)
        if window[0] <= d < window[1] and matches(store, client, a.subject, filters, known_at):
            yield a.subject, d


def _open_invoices(store, client, as_of: date, known_at, filters=None):
    out = []
    for a in store.query(client, predicate='invoice.issued_at', known_at=known_at):
        if date.fromisoformat(a.value) > as_of:
            continue
        if not matches(store, client, a.subject, filters, known_at):
            continue
        paid_on = None
        for p in store.query(client, predicate='payment.settles', value=a.subject, known_at=known_at):
            pd = store.query(client, p.subject, 'payment.paid_at', known_at=known_at)
            if pd and date.fromisoformat(pd[0].value) <= as_of:
                paid_on = pd[0].value
        if paid_on is None:
            out.append(a)
    return out


def _receivables_aging(store, client, window, known_at, filters=None):
    as_of = window[1] - timedelta(days=1)
    buckets = {'current': 0.0, '1-30': 0.0, '31-60': 0.0, '61-90': 0.0, '90+': 0.0}
    inputs = []
    for a in _open_invoices(store, client, as_of, known_at, filters):
        due = store.query(client, a.subject, 'invoice.due_at', known_at=known_at)
        amt = store.query(client, a.subject, 'invoice.amount', known_at=known_at)
        if not (due and amt):
            continue
        over = (as_of - date.fromisoformat(due[0].value)).days
        b = ('current' if over <= 0 else '1-30' if over <= 30 else '31-60' if over <= 60
             else '61-90' if over <= 90 else '90+')
        buckets[b] = cm.money(buckets[b] + amt[0].value)
        inputs += [a.id, due[0].id, amt[0].id]
    return buckets, tuple(inputs), ()


def _dso_days(store, client, window, known_at, filters=None):
    aging, inputs, _ = _receivables_aging(store, client, window, known_at, filters)
    open_total = sum(aging.values())
    sales, s_inputs = 0.0, []
    for inv, d in _invoices_in(store, client, window, known_at, filters):
        amt = store.query(client, inv, 'invoice.amount', known_at=known_at)
        if amt:
            sales += amt[0].value
            s_inputs.append(amt[0].id)
    days = (window[1] - window[0]).days
    return (round(open_total / (sales / days), 1) if sales else 0.0), inputs + tuple(s_inputs), ()


def _customer_concentration(store, client, window, known_at, filters=None):
    by, inputs = {}, []
    for inv, d in _invoices_in(store, client, window, known_at, filters):
        who = store.query(client, inv, 'invoice.billed_to', known_at=known_at)
        amt = store.query(client, inv, 'invoice.amount', known_at=known_at)
        if who and amt:
            by[who[0].value] = by.get(who[0].value, 0.0) + amt[0].value
            inputs += [who[0].id, amt[0].id]
    total = sum(by.values())
    top = sorted(by.items(), key=lambda kv: -kv[1])[:5]
    return ({'top5': {k: cm.pct(v, total) for k, v in top}, 'top1_pct': cm.pct(top[0][1], total) if top else 0.0},
            tuple(inputs), ())


def _route_contribution(store, client, window, known_at, filters=None):
    gp, inputs = {}, []
    for inv, d in _invoices_in(store, client, window, known_at, filters):
        rt = store.query(client, inv, 'invoice.delivered_on_route', known_at=known_at)
        g = store.query(client, inv, 'invoice.gross_profit', known_at=known_at)
        if rt and g:
            gp[rt[0].value] = gp.get(rt[0].value, 0.0) + g[0].value
            inputs += [rt[0].id, g[0].id]
    out = {}
    for rt_id, g in gp.items():
        cost_rows = [a for a in store.query(client, rt_id, 'route.quarter_cost', known_at=known_at)
                     if window[0] <= date.fromisoformat(a.value['effective_on']) < window[1]]
        cost = sum(a.value['amount'] for a in cost_rows)
        inputs += [a.id for a in cost_rows]
        out[rt_id] = {'gross_profit': cm.money(g), 'route_cost': cm.money(cost), 'contribution': cm.money(g - cost)}
    return out, tuple(inputs), ()


def definitions(reg: Registry) -> Registry:
    reg.register(MetricDefinition('receivables_aging', 'v1', 'invoice', 'usd',
                                  'open invoice amounts by days past due at the window end',
                                  ('invoices issued on or before the window end and not paid by then',),
                                  date(2000, 1, 1), _receivables_aging))
    reg.register(MetricDefinition('dso_days', 'v1', 'window', 'days',
                                  'open receivables at the window end divided by average daily sales in the window',
                                  ('as receivables_aging; sales are invoice amounts issued in the window',),
                                  date(2000, 1, 1), _dso_days))
    reg.register(MetricDefinition('customer_concentration', 'v1', 'customer', 'percent',
                                  'share of invoice amounts issued in the window, top five customers',
                                  ('invoices issued in the window',), date(2000, 1, 1), _customer_concentration))
    reg.register(MetricDefinition('route_contribution', 'v1', 'route', 'usd',
                                  'gross profit on invoices delivered on the route less the route cost booked '
                                  'in the window',
                                  ('invoices with a route; route_cost ledger rows effective in the window',),
                                  date(2000, 1, 1), _route_contribution))
    return reg
