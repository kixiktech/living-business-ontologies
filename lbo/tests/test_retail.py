from datetime import date
from lbo.firms import common as cm, retail


def test_build_is_deterministic_and_has_every_source():
    a, b = retail.build(), retail.build()
    assert cm.fingerprint(a) == cm.fingerprint(b)
    assert set(a.sources) == {'pos_sales', 'fulfillment', 'inventory_moves', 'product_master', 'customers',
                              'ledger', 'payroll', 'supplier_terms', 'store_map', 'staff'}
    assert cm.fingerprint(retail.build(seed=8)) != cm.fingerprint(a)


def test_focal_products_sell_exactly_the_planted_volumes():
    f = retail.build()
    pos = f.sources['pos_sales'].records

    def units(item, q):
        return sum(r['qty'] for r in pos
                   if r['item_no'] == item and cm.quarter_of(date.fromisoformat(r['sold_on'])) == q)

    assert units('A-100', '2026Q1') == 400 and units('A-100', '2026Q2') == 400
    assert units('B-200', '2026Q1') == 200 and units('B-200', '2026Q2') == 200
    assert all(r['unit_price'] == 30.0 for r in pos if r['item_no'] == 'A-100')


def test_supplier_orders_and_the_tax_cut_are_planted():
    f = retail.build()
    k = f.answer_key
    assert k['units_ordered_by_quarter'] == {'2025Q1': 600, '2025Q2': 610, '2025Q3': 620, '2025Q4': 610,
                                             '2026Q1': 470, '2026Q2': 480}
    assert k['break_units'] == 500 and k['shortfall_units'] == 30
    assert k['tax_payment'] == 9800.0 and k['tax_payment_date'] == '2026-01-08'
    memos = [r['memo'] for r in f.sources['ledger'].records]
    assert any('reduced from 620 to 470' in m for m in memos)
    assert any('estimated tax' in m for m in memos)


def test_cost_invoices_are_entered_after_they_take_effect():
    f = retail.build()
    rows = [r for r in f.sources['ledger'].records
            if r.get('kind') == 'supplier_invoice' and r['effective_on'] == '2026-04-01']
    assert rows and all(r['entered_on'] == '2026-04-06' for r in rows)


def test_answer_key_gross_profit_numbers():
    k = retail.build().answer_key
    assert k['gp_prior'] == 10000.0 and k['gp_focal'] == 8200.0 and k['gp_gap'] == 1800.0
    assert k['margin_prior_pct'] == 45.45 and k['margin_focal_pct'] == 37.27
    assert k['restore_order_cost'] == 540.0 and k['tier_value_per_quarter'] == 1800.0


def test_absence_and_identity_plants_are_present():
    f = retail.build()
    k = f.answer_key
    pm = {r['item_no']: r for r in f.sources['product_master'].records}
    assert pm[k['absent_supplier_sku']]['supplier'] in (None, '')
    staff = f.sources['staff'].records
    assert not any(r['role'] == 'manager' and r['store'] == k['location_without_manager'] for r in staff)
    emails = [r['email'] for r in f.sources['customers'].records]
    assert len(k['duplicate_email_pairs']) == 12 and len(k['same_name_pairs']) == 4
    assert len({e.lower() for e in emails}) < len(emails)


def test_like_for_like_differs_by_week_convention():
    k = retail.build().answer_key
    assert k['like_for_like_pct_sunday'] != k['like_for_like_pct_saturday']
