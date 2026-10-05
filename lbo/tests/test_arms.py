from datetime import date

from lbo import arms
from lbo.firms import FIRMS
from lbo.store import Store


def test_snapshot_is_independent():
    s = Store()
    s.assert_('c', 'x:1', 'x.f', 1, date(2026, 1, 1), evidence='e')
    t = arms.snapshot_store(s)
    t.assert_('c', 'x:2', 'x.f', 2, date(2026, 1, 1), evidence='e')
    assert s.count('c') == 1 and t.count('c') == 2


def test_raw_db_has_one_table_per_source_and_child_tables_for_lines():
    f = FIRMS['distributor'][0]()
    c = arms.raw_db(f)
    d = arms.describe(c)
    assert set(f.sources) <= set(d)
    assert 'erp_invoices_lines' in d and 'parent_id' in d['erp_invoices_lines']
    out = arms.run_sql(c, 'SELECT COUNT(*) FROM erp_invoices')
    assert out['error'] is None and out['rows'][0][0] == len(f.sources['erp_invoices'].records)


def test_run_sql_refuses_writes_and_multiple_statements():
    f = FIRMS['retail'][0]()
    c = arms.raw_db(f)
    assert arms.run_sql(c, 'DELETE FROM pos_sales')['error']
    assert arms.run_sql(c, 'SELECT 1; SELECT 2')['error']
    assert arms.run_sql(c, 'PRAGMA table_info(pos_sales)')['error']
    out = arms.run_sql(c, 'SELECT * FROM pos_sales', limit=5)
    assert len(out['rows']) == 5 and out['truncated']


def test_normalised_db_dedupes_customers_by_email():
    f = FIRMS['retail'][0]()
    c = arms.normalised_db(f)
    raw = arms.run_sql(c, 'SELECT COUNT(*) FROM customers')['rows'][0][0]
    norm = arms.run_sql(c, 'SELECT COUNT(*) FROM customers_n')['rows'][0][0]
    assert norm == raw - 12
    assert arms.run_sql(c, 'SELECT COUNT(*) FROM sales_n')['error'] is None
