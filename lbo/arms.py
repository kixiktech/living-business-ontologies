# research/lbo/arms.py
"""What each arm can see.

Arm A sees the sources as tables, exactly as exported. Arm B sees the same tables plus
normalised views and approved metric definitions. Arm C sees the ontology. The agent,
the policy and the prompt are identical across arms; only these surfaces differ.
"""
from __future__ import annotations

import json
import re
import sqlite3

from .firms.common import Firm
from .store import Store


def snapshot_store(store: Store) -> Store:
    """A full, independent copy: the run writes to it and the build's store is untouched."""
    out = Store()
    store.db.backup(out.db)
    return out


def _col(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return v


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _is_lines(v) -> bool:
    return isinstance(v, list) and bool(v) and isinstance(v[0], dict)


def _columns(records: list[dict]) -> tuple[list[str], list[str]]:
    """The union of the records' own keys, in first-seen order, split into the flat
    columns and the columns of the nested line table."""
    cols: list[str] = []
    child: list[str] = []
    for rec in records:
        for k, v in rec.items():
            if _is_lines(v):
                for ck in v[0]:
                    if ck not in child:
                        child.append(ck)
            elif k not in cols:
                cols.append(k)
    return cols, child


def _load(firm: Firm) -> sqlite3.Connection:
    conn = sqlite3.connect(':memory:')
    for name, src in firm.sources.items():
        cols, child_cols = _columns(src.records)
        conn.execute(f'CREATE TABLE {_q(name)} ({", ".join(_q(c) for c in cols)})')
        if child_cols:
            conn.execute(f'CREATE TABLE {_q(name + "_lines")} '
                         f'("parent_id", {", ".join(_q(c) for c in child_cols)})')
        for rec in src.records:
            conn.execute(f'INSERT INTO {_q(name)} VALUES ({",".join("?" * len(cols))})',
                         [_col(rec.get(c)) for c in cols])
            for v in rec.values():
                if not _is_lines(v):
                    continue
                for line in v:
                    conn.execute(
                        f'INSERT INTO {_q(name + "_lines")} '
                        f'VALUES ({",".join("?" * (len(child_cols) + 1))})',
                        [rec.get(src.id_field)] + [_col(line.get(c)) for c in child_cols])
    conn.commit()
    return conn


def _lock(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.commit()
    conn.execute('PRAGMA query_only = ON')
    return conn


def raw_db(firm: Firm) -> sqlite3.Connection:
    """One table per source, named after the source, columns from the union of record
    keys. Nested line lists go to `<source>_lines` with a parent_id."""
    return _lock(_load(firm))


def normalised_db(firm: Firm) -> sqlite3.Connection:
    """The raw tables plus the joins and the de-duplication a careful analyst would do
    once and keep: what a semantic layer over the warehouse gives you."""
    conn = _load(firm)
    tables = set(describe(conn))
    if 'customers' in tables:
        idcol = 'cust_id' if 'cust_id' in describe(conn)['customers'] else 'customer_no'
        conn.execute(f'''CREATE VIEW customers_n AS
            SELECT MIN({idcol}) AS id, LOWER(email) AS email, MIN(name) AS name, COUNT(*) AS duplicates
            FROM customers GROUP BY LOWER(email)''')
    if {'pos_sales', 'fulfillment', 'product_master'} <= tables:
        conn.execute('''CREATE VIEW sales_n AS
            SELECT p.line_id, p.order_id, p.sold_on, p.store AS rang_up_at, f.shipped_from AS fulfilled_from,
                   p.cust_id, p.item_no, m.name AS item_name, m.category, m.supplier, p.qty, p.unit_price,
                   p.qty * p.unit_price AS amount
            FROM pos_sales p LEFT JOIN fulfillment f ON f.order_id = p.order_id
            LEFT JOIN product_master m ON m.item_no = p.item_no''')
    if {'jobs', 'crm_leads'} <= tables:
        conn.execute('''CREATE VIEW jobs_n AS
            SELECT j.*, l.created_on AS lead_created_on, l.status AS lead_status,
                   j.revenue - j.direct_cost AS job_margin
            FROM jobs j LEFT JOIN crm_leads l ON l.lead_id = j.lead_id''')
    if {'erp_invoices', 'erp_payments'} <= tables:
        conn.execute('''CREATE VIEW invoices_n AS
            SELECT i.invoice_no, i.customer_no, i.issued_on, i.due_on, i.amount, i.route, i.status,
                   MAX(p.paid_on) AS paid_on
            FROM erp_invoices i LEFT JOIN erp_payments p ON p.invoice_no = i.invoice_no
            GROUP BY i.invoice_no''')
    return _lock(conn)


def describe(conn: sqlite3.Connection) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name")
    for (name,) in rows.fetchall():
        out[name] = [r[1] for r in conn.execute(f'PRAGMA table_info({_q(name)})')]
    return out


_ALLOWED = re.compile(r'^\s*(SELECT|WITH)\b', re.I)


def run_sql(conn: sqlite3.Connection, sql: str, limit: int = 200) -> dict:
    """One read-only statement. Wrapping it as a subquery is what makes the guarantee
    structural rather than a promise: a PRAGMA or a DELETE will not parse there."""
    s = sql.strip().rstrip(';')
    if ';' in s or not _ALLOWED.match(s):
        return {'columns': [], 'rows': [], 'truncated': False,
                'error': 'only a single SELECT or WITH statement is allowed'}
    try:
        cur = conn.execute(f'SELECT * FROM ({s}) LIMIT {int(limit) + 1}')
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
    except sqlite3.Error as e:
        return {'columns': [], 'rows': [], 'truncated': False, 'error': str(e)}
    return {'columns': cols, 'rows': [list(r) for r in rows[:limit]],
            'truncated': len(rows) > limit, 'error': None}
