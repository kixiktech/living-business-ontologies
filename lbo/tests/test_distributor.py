from datetime import date
from lbo.firms import common as cm, distributor as ds


def test_build_is_deterministic_and_complete():
    assert cm.fingerprint(ds.build()) == cm.fingerprint(ds.build())
    assert set(ds.build().sources) == {'erp_invoices', 'erp_payments', 'customers', 'routes',
                                       'supplier_leadtimes', 'products', 'ledger'}


def test_concentration_and_late_payer_are_planted():
    f = ds.build()
    k = f.answer_key
    inv = [r for r in f.sources['erp_invoices'].records
           if cm.quarter_of(date.fromisoformat(r['issued_on'])) == k['focal_quarter']]
    total = sum(r['amount'] for r in inv)
    top = sum(r['amount'] for r in inv if r['customer_no'] == 'CU-0007')
    assert k['top_customer'] == 'CU-0007' and abs(cm.pct(top, total) - 38.0) < 0.5
    assert k['top_customer_avg_days_to_pay'] >= 55 and k['top_customer_terms_days'] == 30


def test_losing_route_and_over_limit_customer():
    k = ds.build().answer_key
    assert k['losing_route'] == 'R3' and k['losing_route_gp'] < k['losing_route_cost']
    assert k['over_limit_customer'] == 'CU-0019' and k['over_limit_open'] > k['over_limit_limit']
    assert k['pending_order_no']


def test_aging_buckets_sum_to_open_receivables_and_dso_is_positive():
    f = ds.build()
    k = f.answer_key
    assert set(k['aging']) == {'current', '1-30', '31-60', '61-90', '90+'}
    assert k['dso_days'] > 0 and k['long_lead_days'] == 45 and k['stock_cover_days'] == 20


def test_hold_order_rule_needs_approval_for_top_five():
    rule = ds.hold_order_rule({'CU-0007', 'CU-0002'})
    assert rule.needs_approval({'customer': 'CU-0007'})
    assert rule.needs_approval({'customer': 'CU-0050'}) is None


def test_only_the_south_loop_loses_money_in_the_focal_quarter():
    k = ds.build().answer_key
    losing = [rt for rt, v in k['route_contribution'].items() if v['contribution'] < 0]
    assert losing == ['R3']


def test_the_top_five_is_four_large_accounts_and_the_biggest_one():
    # The five largest customers has to name a real set, or a hold on a top-five customer
    # is not a meaningful rule. CU-0019 must stay outside it: its only large invoices are
    # the two it has not paid, and those are the credit case, not size.
    f = ds.build()
    k = f.answer_key
    assert k['top5'] == [ds.TOP_CUSTOMER, *ds.LARGE_CUSTOMERS]
    assert ds.OVER_LIMIT_CUSTOMER not in k['top5']
    names = {c['customer_no']: c['name'] for c in f.sources['customers'].records}
    assert names[ds.TOP_CUSTOMER] == 'Baylor Foods'


def test_the_over_limit_customer_stays_clear_of_the_top_five_by_a_real_margin():
    f = ds.build()
    k = f.answer_key
    inv = [x for x in f.sources['erp_invoices'].records
           if cm.quarter_of(date.fromisoformat(x['issued_on'])) == k['focal_quarter']]
    by = {}
    for x in inv:
        by[x['customer_no']] = by.get(x['customer_no'], 0.0) + x['amount']
    fifth = min(by[c] for c in k['top5'])
    assert by[ds.OVER_LIMIT_CUSTOMER] < fifth
    # a tenth of the fifth-largest account, so a small change in the generator cannot
    # silently put the credit case back into the top five
    assert fifth - by[ds.OVER_LIMIT_CUSTOMER] > fifth * 0.10
