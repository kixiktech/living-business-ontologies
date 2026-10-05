# research/lbo/store.py
"""The assertion store: every fact the ontology holds, under two clocks.

    x = (c, s, p, v, I_v, I_o, e, sigma)

Business time (valid_from, valid_to) says when the fact was true of the firm. Knowledge
time (recorded_at, recorded_until) says when the system believed it. A replay asks for
both and gets only what could have been known. Nothing is deleted: a correction closes
the old row's knowledge interval and inserts a new row that points back at it.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

STATUSES = ('observed', 'inferred', 'disputed', 'corrected', 'superseded')

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assertions (
  id INTEGER PRIMARY KEY,
  client TEXT NOT NULL,
  subject TEXT NOT NULL,
  predicate TEXT NOT NULL,
  value TEXT NOT NULL,
  valid_from TEXT NOT NULL,
  valid_to TEXT,
  recorded_at TEXT NOT NULL,
  recorded_until TEXT,
  evidence TEXT NOT NULL,
  status TEXT NOT NULL,
  supersedes INTEGER
);
CREATE INDEX IF NOT EXISTS ix_spv ON assertions(client, subject, predicate);
CREATE INDEX IF NOT EXISTS ix_pv ON assertions(client, predicate, value);
CREATE TABLE IF NOT EXISTS contradictions (
  id INTEGER PRIMARY KEY,
  assertion_id INTEGER NOT NULL,
  run_id TEXT NOT NULL,
  note TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Assertion:
    id: int
    client: str
    subject: str
    predicate: str
    value: Any
    valid_from: date
    valid_to: date | None
    recorded_at: datetime
    recorded_until: datetime | None
    evidence: str
    status: str
    supersedes: int | None


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _t(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def _row(r: sqlite3.Row) -> Assertion:
    return Assertion(
        id=r['id'], client=r['client'], subject=r['subject'], predicate=r['predicate'],
        value=json.loads(r['value']), valid_from=_d(r['valid_from']), valid_to=_d(r['valid_to']),
        recorded_at=_t(r['recorded_at']), recorded_until=_t(r['recorded_until']),
        evidence=r['evidence'], status=r['status'], supersedes=r['supersedes'])


class Store:
    def __init__(self, path: str = ':memory:'):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)

    # -- writes -------------------------------------------------------------------
    def assert_(self, client: str, subject: str, predicate: str, value: Any,
                valid_from: date, valid_to: date | None = None, *, evidence: str,
                status: str = 'observed', recorded_at: datetime | None = None,
                supersedes: int | None = None) -> int:
        if not evidence:
            raise ValueError('an assertion needs evidence')
        if status not in STATUSES:
            raise ValueError(f'status must be one of {STATUSES}')
        recorded_at = recorded_at or datetime.now()
        cur = self.db.execute(
            'INSERT INTO assertions (client, subject, predicate, value, valid_from, valid_to,'
            ' recorded_at, recorded_until, evidence, status, supersedes)'
            ' VALUES (?,?,?,?,?,?,?,NULL,?,?,?)',
            (client, subject, predicate, json.dumps(value), valid_from.isoformat(),
             valid_to.isoformat() if valid_to else None, recorded_at.isoformat(),
             evidence, status, supersedes))
        self.db.commit()
        return int(cur.lastrowid)

    _UNSET = object()

    def supersede(self, old_id: int, *, value: Any = _UNSET, valid_from: Any = _UNSET,
                  valid_to: Any = _UNSET, evidence: str, recorded_at: datetime | None = None,
                  status: str = 'corrected') -> int:
        old = self.get(old_id)
        recorded_at = recorded_at or datetime.now()
        new_id = self.assert_(
            old.client, old.subject, old.predicate,
            old.value if value is Store._UNSET else value,
            old.valid_from if valid_from is Store._UNSET else valid_from,
            old.valid_to if valid_to is Store._UNSET else valid_to,
            evidence=evidence, status=status, recorded_at=recorded_at, supersedes=old_id)
        self.db.execute('UPDATE assertions SET recorded_until=?, status=? WHERE id=?',
                        (recorded_at.isoformat(), 'superseded', old_id))
        self.db.commit()
        return new_id

    def record_contradiction(self, assertion_ids: list[int], run_id: str, note: str) -> None:
        now = datetime.now().isoformat()
        self.db.executemany(
            'INSERT INTO contradictions (assertion_id, run_id, note, recorded_at) VALUES (?,?,?,?)',
            [(i, run_id, note, now) for i in assertion_ids])
        self.db.commit()

    # -- reads --------------------------------------------------------------------
    def get(self, id: int) -> Assertion:
        r = self.db.execute('SELECT * FROM assertions WHERE id=?', (id,)).fetchone()
        if r is None:
            raise KeyError(id)
        return _row(r)

    def query(self, client: str, subject: str | None = None, predicate: str | None = None,
              value: Any = None, as_of: date | None = None, known_at: datetime | None = None,
              include_superseded: bool = False) -> list[Assertion]:
        sql, args = ['client=?'], [client]
        if subject is not None:
            sql.append('subject=?'); args.append(subject)
        if predicate is not None:
            sql.append('predicate=?'); args.append(predicate)
        if value is not None:
            if isinstance(value, bool):
                sql.append('value=?'); args.append(json.dumps(value))
            elif isinstance(value, int):
                sql.append('(value=? OR value=?)')
                args += [json.dumps(value), json.dumps(float(value))]
            elif isinstance(value, float) and value.is_integer():
                sql.append('(value=? OR value=?)')
                args += [json.dumps(value), json.dumps(int(value))]
            else:
                sql.append('value=?'); args.append(json.dumps(value))
        if as_of is not None:
            sql.append('valid_from<=? AND (valid_to IS NULL OR valid_to>?)')
            args += [as_of.isoformat(), as_of.isoformat()]
        if known_at is not None:
            sql.append('recorded_at<=? AND (recorded_until IS NULL OR recorded_until>?)')
            args += [known_at.isoformat(), known_at.isoformat()]
        elif not include_superseded:
            sql.append('recorded_until IS NULL')
        rows = self.db.execute('SELECT * FROM assertions WHERE ' + ' AND '.join(sql)
                               + ' ORDER BY id', args).fetchall()
        return [_row(r) for r in rows]

    def history(self, client: str, subject: str, predicate: str) -> list[Assertion]:
        rows = self.db.execute(
            'SELECT * FROM assertions WHERE client=? AND subject=? AND predicate=? ORDER BY recorded_at, id',
            (client, subject, predicate)).fetchall()
        return [_row(r) for r in rows]

    def contradiction_counts(self, client: str) -> dict[int, int]:
        rows = self.db.execute(
            'SELECT c.assertion_id AS i, COUNT(*) AS n FROM contradictions c'
            ' JOIN assertions a ON a.id=c.assertion_id WHERE a.client=? GROUP BY c.assertion_id',
            (client,)).fetchall()
        return {r['i']: r['n'] for r in rows}

    def count(self, client: str) -> int:
        return self.db.execute('SELECT COUNT(*) FROM assertions WHERE client=?', (client,)).fetchone()[0]
