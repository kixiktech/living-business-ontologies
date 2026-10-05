# research/lbo/closure.py
"""Competency questions, and the satisfaction relation that says whether the model can
answer one.

    satisfies(q, B_{c,t,u})  ->  which declared requirements are present, absent or stale

This is closure under DECLARED dependencies. It terminates because the requirements are
finite and named, and it never completes the picture with a plausible account of the
business: an absent requirement is reported as a gap, and the caller narrows, asks or
stops.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .store import Store

KINDS = ('assertion', 'definition', 'grant')


@dataclass(frozen=True)
class Requirement:
    kind: str
    predicate: str = ''
    subject: str = ''
    definition: str = ''
    action: str = ''
    covers: tuple[date, date] | None = None
    max_age_days: int | None = None

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f'kind must be one of {KINDS}')


@dataclass(frozen=True)
class CompetencyQuestion:
    id: str
    text: str
    requires: tuple[Requirement, ...]


@dataclass(frozen=True)
class Satisfaction:
    present: tuple[Requirement, ...]
    absent: tuple[Requirement, ...]
    stale: tuple[Requirement, ...]
    gaps: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.absent and not self.stale


def _covered(rows, window: tuple[date, date]) -> tuple[bool, str]:
    """Do the validity intervals of `rows` cover [start, end) without a hole?"""
    ivs = sorted((r.valid_from, r.valid_to or date.max) for r in rows)
    cursor = window[0]
    for a, b in ivs:
        if a > cursor:
            return False, f'no value from {cursor} to {a}'
        cursor = max(cursor, b)
        if cursor >= window[1]:
            return True, ''
    return False, f'no value from {cursor} to {window[1]}'


def _check_assertion(r: Requirement, store: Store, client: str, as_of: date,
                     known_at: datetime | None) -> tuple[str, str]:
    """Both clocks. A requirement with a window is read over the whole window, so every
    row is fetched and coverage is checked. A requirement without one asks whether the
    fact holds on the question's date, so the read is as of that date: a certification
    that expired last year does not satisfy a question asked this year, whatever the
    knowledge clock says. Knowledge age is measured from the knowledge clock when one is
    given and otherwise from the question's date, never from the machine's clock, which
    has nothing to do with the firm.
    """
    rows = store.query(client, r.subject or None, r.predicate,
                       as_of=None if r.covers is not None else as_of, known_at=known_at)
    where = f'{r.predicate}{" on " + r.subject if r.subject else ""}'
    if not rows:
        if r.covers is None and store.query(client, r.subject or None, r.predicate, known_at=known_at):
            return 'absent', f'{where}: nothing valid on {as_of}'
        return 'absent', f'{where}: nothing recorded'
    if r.covers is not None:
        ok, why = _covered(rows, r.covers)
        if not ok:
            return 'absent', f'{where}: {why}'
    if r.max_age_days is not None:
        ref = known_at or datetime.combine(as_of, datetime.min.time())
        newest = max(x.recorded_at for x in rows)
        if ref - newest > timedelta(days=r.max_age_days):
            return 'stale', f'{r.predicate}: last recorded {newest.date()}, older than {r.max_age_days} days'
    return 'present', ''


def satisfies(q: CompetencyQuestion, store: Store, client: str, *, as_of: date,
              known_at: datetime | None = None, registry=None, monitor=None,
              principal: str = '') -> Satisfaction:
    present, absent, stale, gaps = [], [], [], []
    for r in q.requires:
        if r.kind == 'assertion':
            state, why = _check_assertion(r, store, client, as_of, known_at)
        elif r.kind == 'definition':
            try:
                registry.get(r.definition, as_of)
                state, why = 'present', ''
            except (KeyError, AttributeError):
                state, why = 'absent', f'no definition of {r.definition} effective on {as_of}'
        else:
            # Whether a live grant exists for this principal and this verb, never whether
            # some particular payload would pass. Scope, limits and the approval rules are
            # `check`'s business at the moment an action is proposed; the model's question
            # is only whether the firm has delegated the verb at all.
            live = monitor is not None and monitor.has_grant(principal, r.action, as_of)
            if live:
                state, why = 'present', ''
            else:
                state, why = 'absent', f'no grant lets {principal or "(nobody)"} {r.action}'
        {'present': present, 'absent': absent, 'stale': stale}[state].append(r)
        if why:
            gaps.append(why)
    return Satisfaction(tuple(present), tuple(absent), tuple(stale), tuple(gaps))


def dependency_closure(q: CompetencyQuestion, store: Store, client: str, *, as_of: date,
                       known_at: datetime | None = None, registry=None) -> set[int]:
    ids: set[int] = set()
    for r in q.requires:
        if r.kind == 'assertion':
            ids |= {a.id for a in store.query(client, r.subject or None, r.predicate,
                                              as_of=None if r.covers is not None else as_of,
                                              known_at=known_at)}
        elif r.kind == 'definition' and registry is not None:
            windows = [x.covers for x in q.requires if x.covers] or [(as_of, as_of + timedelta(days=1))]
            for w in windows:
                try:
                    m = registry.compute(r.definition, store, client, w, known_at=known_at, as_of=as_of)
                    ids |= set(m.inputs)
                except KeyError:
                    pass
    return ids
