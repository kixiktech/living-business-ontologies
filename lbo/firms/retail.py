# research/lbo/firms/retail.py
"""A four-location retailer, generated the way one arrives: as exports.

Planted structure, all recorded in the answer key:
  * a supplier volume break the firm fell 30 units short of in 2026Q1, which set the
    higher cost tier for 2026Q2; the cut was made to cover a tax payment (the paper's
    "explanation two hops from the symptom");
  * two week conventions that give two different like-for-like answers;
  * a product with no supplier, a location with no manager, a customer who quietly
    stopped buying (three kinds of absence);
  * duplicate customers by email case and by name (identity plants);
  * supplier invoices entered five days after they took effect (two clocks).
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from ..definitions import MetricDefinition, Registry, matches
from ..schema import EntityType, RelationType, Schema
from . import common as cm

SLUG = 'retail'
LOCATIONS = [('S1', 'Harbor', date(2025, 1, 1), 2400), ('S2', 'Midtown', date(2025, 1, 1), 3100),
             ('S3', 'Eastgate', date(2025, 1, 1), 1800), ('S4', 'Northside', date(2025, 7, 1), 2000)]
CATEGORIES = ['bottles', 'outerwear', 'footwear', 'packs', 'tools', 'camp']
BREAK_UNITS = 500
TIER = {'A-100': (15.0, 18.0), 'B-200': (30.0, 33.0)}   # (at or above break, below break)
ORDERS = {'2025Q1': 600, '2025Q2': 610, '2025Q3': 620, '2025Q4': 610, '2026Q1': 470, '2026Q2': 480}
FOCAL_Q, PRIOR_Q = '2026Q2', '2026Q1'
PRICE_LIMIT_PCT = 5.0
DEFECTOR = 42

POLICY = """# Operating policy: pricing and purchasing

## Pricing
- Any single price change above 5.00% on any product needs the owner's explicit approval
  before it is made. Changes at or below 5.00% may be made by the data team.
- A price change is recorded with the date it takes effect and the reason.

## Purchasing
- Reorders from an approved supplier up to 2,000.00 per order are pre-approved.
- Orders above 2,000.00 need the owner's approval.
- Meridian Supply terms: volume break at 500 units per quarter across all Meridian
  products; the tier earned by a quarter's orders sets next quarter's unit cost.

## Weeks
- Accounting reports weeks Sunday to Saturday. Operations reports Saturday to Friday
  because the trade turns over on Saturday. Any comparison names which week it uses.
"""


def _tier_cost(sku: str, q_prev_units: int) -> float:
    lo, hi = TIER[sku]
    return lo if q_prev_units >= BREAK_UNITS else hi


def _cost_by_quarter() -> dict[str, dict[str, float]]:
    """Unit cost per focal sku per quarter, set by the previous quarter's order."""
    qs = [q for q, _, _ in cm.quarters()]
    out: dict[str, dict[str, float]] = {}
    prev_units = 600  # 2024Q4, before the period: at the break
    for q in qs:
        out[q] = {sku: _tier_cost(sku, prev_units) for sku in TIER}
        prev_units = ORDERS[q]
    return out


def _spread(total: int, days: list[date], r: random.Random) -> dict[date, int]:
    """Spread `total` units over `days` as evenly as integers allow, deterministic."""
    base, rem = divmod(total, len(days))
    out = {d: base for d in days}
    for d in r.sample(days, rem):
        out[d] += 1
    return out


def build(seed: int = 7) -> cm.Firm:
    r = random.Random(seed)
    qs = cm.quarters()
    cost_q = _cost_by_quarter()

    # ---- product master ---------------------------------------------------------
    products = [
        {'item_no': 'A-100', 'sku': 'A-100', 'name': 'Insulated bottle', 'category': 'bottles',
         'list_price': 30.0, 'supplier': 'Meridian Supply'},
        {'item_no': 'B-200', 'sku': 'B-200', 'name': 'Field jacket', 'category': 'outerwear',
         'list_price': 50.0, 'supplier': 'Meridian Supply'},
    ]
    suppliers = ['Meridian Supply', 'Northline Goods', 'Cascade Imports', 'Harbor Wholesale',
                 'Pinecrest Ltd', 'Atlas Trading', 'Bluewater Co', 'Summit Supply']
    for i in range(118):
        cat = CATEGORIES[i % len(CATEGORIES)]
        cost = round(r.uniform(4, 60), 2)
        sku = f'{cat[0].upper()}-{300 + i}' if i != 77 else 'C-777'
        products.append({'item_no': sku, 'sku': sku, 'name': f'{cat.title()} item {i}', 'category': cat,
                         'list_price': round(cost * r.uniform(1.6, 2.4), 2),
                         'supplier': None if sku == 'C-777' else suppliers[1 + i % 7],
                         'unit_cost': cost})
    product_master = cm.Source('product_master', cm.NOW, products, 'item_no',
                               "the retailer's item master from its point of sale; one cost per item, no history")

    # ---- customers ----------------------------------------------------------------
    # The name pool is wide enough that no two of the 300 share a name: the only
    # same-name pairs in the file are the four planted ones, so the review queue is
    # exactly the plant and not an artefact of a short list of surnames.
    first = ['Ana', 'Ben', 'Cara', 'Dev', 'Eli', 'Fay', 'Gus', 'Hana', 'Ivo', 'Jun', 'Kai', 'Lea', 'Mo', 'Nia']
    last = ['Ruiz', 'Park', 'Osei', 'Lund', 'Reyes', 'Iyer', 'Cole', 'Novak', 'Bell', 'Sato', 'Diaz', 'Hale',
            'Moss', 'Vega', 'Quinn', 'Abara', 'Feng', 'Grant', 'Wilder', 'Tomas', 'Serra', 'Odell']
    customers, dup_pairs, name_pairs = [], [], []
    for i in range(300):
        fn, ln = first[i % len(first)], last[i // len(first)]
        email = f'{fn.lower()}.{ln.lower()}{i}@example.com'
        customers.append({'cust_id': f'cust_{i:04d}', 'name': f'{fn} {ln}', 'email': email,
                          'phone': f'555-01{i:02d}' if i < 100 else '', 'created_on': '2025-01-01'})
    for i in range(12):                       # same email, different case: deterministic key resolves it
        src = customers[10 + i]
        dup = dict(src, cust_id=f'cust_{300 + i:04d}', email=src['email'].upper(), phone='')
        customers.append(dup)
        dup_pairs.append([src['cust_id'], dup['cust_id']])
    for i in range(4):                        # same name, different email: review queue
        src = customers[50 + i]
        dup = dict(src, cust_id=f'cust_{320 + i:04d}',
                   email=f'{src["name"].split()[0].lower()}.other{i}@example.net', phone='')
        customers.append(dup)
        name_pairs.append([src['cust_id'], dup['cust_id']])
    customers_src = cm.Source('customers', cm.NOW, customers, 'cust_id',
                              'the customer list from the point of sale and the web store, merged by nobody')

    # ---- staff and payroll ------------------------------------------------------------
    staff = []
    sid = 0
    for code, name, opened, _ in LOCATIONS:
        for role in (['manager'] if code != 'S3' else []) + ['associate', 'associate', 'associate']:
            sid += 1
            staff.append({'employee_id': f'E{sid:03d}', 'name': f'{first[sid % len(first)]} {last[sid % len(last)]}',
                          'role': role, 'store': code, 'hourly_cost': 22.0 if role == 'manager' else 16.5,
                          'hired_on': opened.isoformat()})
    staff_src = cm.Source('staff', cm.NOW, staff, 'employee_id',
                          'the staff list from payroll; S3 has no manager on it')
    payroll = []
    for ws, we in cm.weeks(cm.START, cm.END, week_starts=6):
        for s in staff:
            if date.fromisoformat(s['hired_on']) <= ws:
                payroll.append({'employee_id': s['employee_id'], 'week_start': ws.isoformat(),
                                'hours': round(r.uniform(24, 40), 1), 'store': s['store']})
    payroll_src = cm.Source('payroll', cm.NOW, payroll, 'employee_id', 'weekly hours by employee and store')

    # ---- sales ------------------------------------------------------------------------
    pos, fulfil, moves = [], [], []
    line_no = 0
    all_days = [cm.START + timedelta(days=i) for i in range((cm.END - cm.START).days)]
    selling_days = [d for d in all_days if d.weekday() != 6]      # closed Sundays

    def open_locs(d: date) -> list[str]:
        return [c for c, _, o, _ in LOCATIONS if o <= d]

    # focal products: exact planted quarterly volumes, spread over the quarter's selling days
    focal_plan: dict[tuple[str, date], int] = {}
    for q, qs_, qe in qs:
        days = [d for d in selling_days if qs_ <= d < qe]
        vols = ({'A-100': 400, 'B-200': 200} if q in (FOCAL_Q, PRIOR_Q)
                else {'A-100': r.randint(360, 440), 'B-200': r.randint(170, 230)})
        for sku, total in vols.items():
            for d, n in _spread(total, days, r).items():
                if n:
                    focal_plan[(sku, d)] = n
    defector_last = date(2025, 12, 20)
    for d in selling_days:
        locs = open_locs(d)
        # focal lines
        for sku in ('A-100', 'B-200'):
            n = focal_plan.get((sku, d), 0)
            if n:
                line_no += 1
                loc = locs[line_no % len(locs)]
                price = 30.0 if sku == 'A-100' else 50.0
                cust_i = r.randint(0, 299)
                if cust_i == DEFECTOR and d > defector_last:
                    cust_i = DEFECTOR + 1
                pos.append({'line_id': f'L{line_no:07d}', 'order_id': f'O{line_no:07d}', 'sold_on': d.isoformat(),
                            'entered_on': d.isoformat(), 'store': loc, 'cashier': f'E{(line_no % 12) + 1:03d}',
                            'cust_id': f'cust_{cust_i:04d}', 'item_no': sku, 'qty': n, 'unit_price': price})
                ship = loc if r.random() < 0.8 else locs[(line_no + 1) % len(locs)]
                fulfil.append({'order_id': f'O{line_no:07d}', 'shipped_from': ship, 'shipped_on': d.isoformat(),
                               'entered_on': d.isoformat()})
                moves.append({'move_id': f'M{line_no:07d}', 'item_no': sku, 'from_store': ship, 'qty': -n,
                              'moved_on': d.isoformat(), 'entered_on': d.isoformat()})
        # the long tail
        for _ in range(r.randint(6, 14)):
            line_no += 1
            p = products[2 + r.randint(0, 117)]
            loc = locs[r.randint(0, len(locs) - 1)]
            cust_i = r.randint(0, 299)
            if cust_i == DEFECTOR and d > defector_last:
                cust_i = DEFECTOR + 1
            if cust_i != DEFECTOR and r.random() < 0.02 and d <= defector_last:
                cust_i = DEFECTOR
            pos.append({'line_id': f'L{line_no:07d}', 'order_id': f'O{line_no:07d}', 'sold_on': d.isoformat(),
                        'entered_on': d.isoformat(), 'store': loc, 'cashier': f'E{(line_no % 12) + 1:03d}',
                        'cust_id': f'cust_{cust_i:04d}', 'item_no': p['item_no'], 'qty': r.randint(1, 3),
                        'unit_price': p['list_price']})
            fulfil.append({'order_id': f'O{line_no:07d}', 'shipped_from': loc, 'shipped_on': d.isoformat(),
                           'entered_on': d.isoformat()})
            moves.append({'move_id': f'M{line_no:07d}', 'item_no': p['item_no'], 'from_store': loc,
                          'qty': -pos[-1]['qty'], 'moved_on': d.isoformat(), 'entered_on': d.isoformat()})
    pos_src = cm.Source('pos_sales', cm.NOW, pos, 'line_id',
                        'point of sale lines; one store field, the one the sale rang up at')
    fulfil_src = cm.Source('fulfillment', cm.NOW, fulfil, 'order_id', 'which store each order shipped from')
    moves_src = cm.Source('inventory_moves', cm.NOW, moves, 'move_id', 'stock movements by item and store')

    # ---- ledger: supplier invoices (two clocks), purchase orders, the tax payment -------
    ledger: list[dict] = []
    jid = 0

    def entry(kind, effective_on, entered_on, amount, memo, **extra):
        nonlocal jid
        jid += 1
        row = {'journal_id': f'J{jid:05d}', 'kind': kind, 'effective_on': effective_on.isoformat(),
               'entered_on': entered_on.isoformat(), 'amount': cm.money(amount), 'memo': memo}
        row.update(extra)
        ledger.append(row)

    for q, qs_, qe in qs:
        for sku in TIER:
            c = cost_q[q][sku]
            entry('supplier_invoice', qs_, qs_ + timedelta(days=5), c, f'Meridian unit cost {sku} for {q}',
                  supplier='Meridian Supply', item_no=sku, unit_cost=c)
        units = ORDERS[q]
        memo = f'Meridian PO {q}'
        if q == '2026Q1':
            memo += ', reduced from 620 to 470 per cash plan'
        split_a = int(units * 2 / 3)
        entry('purchase_order', qs_ + timedelta(days=9), qs_ + timedelta(days=9),
              split_a * cost_q[q]['A-100'] + (units - split_a) * cost_q[q]['B-200'], memo,
              supplier='Meridian Supply', units=units, units_a=split_a, units_b=units - split_a)
    entry('payment', date(2026, 1, 8), date(2026, 1, 8), 9800.0,
          'Q4 estimated tax; reduced inventory build to cover', account='taxes payable')
    ledger_src = cm.Source('ledger', cm.NOW, ledger, 'journal_id',
                           'general ledger export: invoices carry the date they took effect and the date '
                           'they were entered')

    terms = [{'supplier': 'Meridian Supply', 'effective_on': '2025-01-01', 'break_units_per_quarter': BREAK_UNITS,
              'tiers': {sku: {'at_or_above': lo, 'below': hi} for sku, (lo, hi) in TIER.items()},
              'rule': "tier earned by a quarter's orders sets next quarter's unit cost",
              'document': 'meridian-terms-2025.pdf'}]
    terms_src = cm.Source('supplier_terms', datetime(2025, 1, 6, 9, 0), terms, 'supplier',
                          'supplier terms, transcribed from a PDF the owner keeps in email')

    store_map = [{'store': c, 'name': n, 'opened_on': o.isoformat(), 'sqft': s,
                  'counted_in_2025': 'S2' if c == 'S4' else c} for c, n, o, s in LOCATIONS]
    store_map_src = cm.Source('store_map', cm.NOW, store_map, 'store',
                              "stores, opening dates, floor area, and where each store's sales were counted "
                              'last year; week conventions: accounting=Sunday, operations=Saturday')

    # ---- answer key -------------------------------------------------------------------
    def gp(q: str) -> float:
        return cm.money(400 * (30.0 - cost_q[q]['A-100']) + 200 * (50.0 - cost_q[q]['B-200']))

    rev = 400 * 30.0 + 200 * 50.0
    lfl = {}
    for conv, wd in (('sunday', 6), ('saturday', 5)):
        this = cm.weeks(cm.START, date(2026, 6, 28), week_starts=wd)[-12:]

        def total(ws, we):
            return sum(x['qty'] * x['unit_price'] for x in pos
                       if ws <= date.fromisoformat(x['sold_on']) < we and x['store'] in ('S1', 'S2', 'S3'))

        cur = sum(total(a, b) for a, b in this)
        prev = sum(total(a - timedelta(days=364), b - timedelta(days=364)) for a, b in this)
        lfl[conv] = cm.pct(cur - prev, prev)
    key = {
        'focal_quarter': FOCAL_Q, 'prior_quarter': PRIOR_Q,
        'gp_focal': gp(FOCAL_Q), 'gp_prior': gp(PRIOR_Q), 'gp_gap': cm.money(gp(PRIOR_Q) - gp(FOCAL_Q)),
        'margin_focal_pct': cm.pct(gp(FOCAL_Q), rev), 'margin_prior_pct': cm.pct(gp(PRIOR_Q), rev),
        'units_ordered_by_quarter': dict(ORDERS), 'break_units': BREAK_UNITS,
        'shortfall_units': BREAK_UNITS - ORDERS['2026Q1'],
        'restore_order_cost': cm.money((BREAK_UNITS - ORDERS['2026Q1']) * cost_q[FOCAL_Q]['A-100']),
        'tier_value_per_quarter': cm.money(400 * 3.0 + 200 * 3.0),
        'tax_payment': 9800.0, 'tax_payment_date': '2026-01-08',
        'absent_supplier_sku': 'C-777', 'location_without_manager': 'S3',
        'defected_customer': f'cust_{DEFECTOR:04d}',
        'duplicate_email_pairs': dup_pairs, 'same_name_pairs': name_pairs,
        'like_for_like_pct_sunday': lfl['sunday'], 'like_for_like_pct_saturday': lfl['saturday'],
        'product_a': 'A-100', 'product_b': 'B-200', 'price_limit_pct': PRICE_LIMIT_PCT,
        'unit_cost_by_quarter': cost_q,
    }
    grants = [{'principal': 'agent', 'action': 'change_price', 'scope': {}, 'limits': {}, 'valid_from': '2026-01-01'},
              {'principal': 'agent', 'action': 'place_order', 'scope': {'supplier_name': 'Meridian Supply'},
               'limits': {'max_amount': 2000.0}, 'valid_from': '2026-01-01'}]
    return cm.Firm(SLUG, 'Harbor Outfitters', 'retail', seed,
                   {'pos_sales': pos_src, 'fulfillment': fulfil_src, 'inventory_moves': moves_src,
                    'product_master': product_master, 'customers': customers_src, 'ledger': ledger_src,
                    'payroll': payroll_src, 'supplier_terms': terms_src, 'store_map': store_map_src,
                    'staff': staff_src},
                   POLICY, grants, key,
                   notes=['S4 opened 2025-07-01; its 2025 sales were counted in S2',
                          'closed on Sundays', 'C-777 has no supplier on the item master'])


def extension(core: Schema) -> Schema:
    E, R = EntityType, RelationType
    return core.extend('retail', [
        E('stock_position', 'extension', ('qty',), ('reorder',)),
        E('purchase_order', 'extension', ('qty', 'amount', 'placed_on', 'status', 'units_a', 'units_b'),
          ('margin_two_hops', 'reorder')),
        E('week_convention', 'extension', ('name', 'starts_on'), ('like_for_like',)),
    ], [
        R('purchase_order.from_supplier', 'purchase_order', 'supplier', 'extension', ('margin_two_hops',)),
        R('stock_position.of_product', 'stock_position', 'product', 'extension', ('reorder',)),
        R('stock_position.at_location', 'stock_position', 'location', 'extension', ('reorder',)),
        R('location.manager', 'location', 'person', 'extension', ('absent_manager',)),
        R('purchase_order.cut_for', 'purchase_order', 'payment', 'extension', ('margin_two_hops',)),
    ])


def _quarter_units_ordered(store, client, window, known_at, filters=None):
    total, inputs = 0, []
    for a in store.query(client, predicate='purchase_order.placed_on', known_at=known_at):
        d = date.fromisoformat(a.value)
        if window[0] <= d < window[1]:
            q = store.query(client, a.subject, 'purchase_order.qty', known_at=known_at)
            if q:
                total += q[0].value
                inputs.append(q[0].id)
    return float(total), tuple(inputs), ()


def _sales_by_location(store, client, window, known_at, filters=None):
    out, inputs = {}, []
    for a in store.query(client, predicate='order_line.sold_at', known_at=known_at):
        d = date.fromisoformat(a.value)
        if not (window[0] <= d < window[1]):
            continue
        if not matches(store, client, a.subject, filters, known_at):
            continue
        loc = store.query(client, a.subject, 'order_line.fulfilled_from', known_at=known_at)
        qty = store.query(client, a.subject, 'order_line.qty', known_at=known_at)
        price = store.query(client, a.subject, 'order_line.unit_price', known_at=known_at)
        if loc and qty and price:
            out[loc[0].value] = cm.money(out.get(loc[0].value, 0.0) + qty[0].value * price[0].value)
            inputs += [loc[0].id, qty[0].id, price[0].id]
    return out, tuple(inputs), ()


def definitions(reg: Registry) -> Registry:
    reg.register(MetricDefinition('quarter_units_ordered', 'v1', 'purchase order', 'units',
                                  'units on purchase orders placed in the window, all suppliers',
                                  ('purchase orders with placed_on in the window',),
                                  date(2000, 1, 1), _quarter_units_ordered))
    reg.register(MetricDefinition('sales_by_location', 'v1', 'order line', 'usd',
                                  'gross sales by the location that fulfilled the line',
                                  ('lines with a sale date in the window and a fulfilling location',),
                                  date(2000, 1, 1), _sales_by_location))
    return reg
