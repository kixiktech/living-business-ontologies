# research/lbo/identity.py
"""Identity precedes everything, and it is a decision, not a fact.

Source identifiers are not identities. Deterministic matches on approved keys resolve
automatically. Ambiguous matches enter a review queue with their candidates, which is
what the classical record-linkage result prescribes. A merge is an assertion (same_as),
so it is recorded, replayable and reversible; a split supersedes it.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime

from .store import Assertion, Store

KEYS: dict[str, list[tuple[str, ...]]] = {
    'party': [('email',), ('phone',)],
    'person': [('email',), ('name', 'role')],
    'product': [('sku',)],
    'supplier': [('name',)],
    'location': [('name',)],
}


def _norm(v) -> str:
    return ' '.join(str(v).strip().lower().split())


@dataclass(frozen=True)
class Candidate:
    a: str
    b: str
    reason: str


class Resolver:
    def __init__(self, store: Store, client: str, keys: dict | None = None):
        self.store, self.client = store, client
        # An explicitly empty mapping means no deterministic keys at all, which is the
        # no_identity ablation; only an omitted mapping falls back to the standard keys.
        self.keys = KEYS if keys is None else keys
        self._by_key: dict[tuple, str] = {}          # (type, keyfields, values) -> entity
        self._by_name: dict[tuple[str, str], list[str]] = {}
        self._by_source: dict[tuple[str, str], str] = {}
        self._queue: list[Candidate] = []

    def _new_id(self, entity_type: str, source: str, source_id: str) -> str:
        h = hashlib.sha1(f'{self.client}|{source}|{source_id}'.encode()).hexdigest()[:8]
        return f'{entity_type}:{h}'

    def register(self, source: str, source_id: str, entity_type: str, attrs: dict, at: date,
                 recorded_at: datetime | None = None, evidence: str = '') -> str:
        evidence = evidence or f'{source} export'
        if (source, source_id) in self._by_source:
            return self._by_source[(source, source_id)]
        match = None
        for fields in self.keys.get(entity_type, []):
            if all(attrs.get(f) not in (None, '') for f in fields):
                k = (entity_type, fields, tuple(_norm(attrs[f]) for f in fields))
                if k in self._by_key:
                    match = self._by_key[k]
                    break
        if match is None:
            match = self._new_id(entity_type, source, source_id)
            name = attrs.get('name')
            if name is not None:
                for other in self._by_name.get((entity_type, _norm(name)), []):
                    self._queue.append(Candidate(other, match, f'same name {name!r}, no key in common'))
                self._by_name.setdefault((entity_type, _norm(name)), []).append(match)
        # Assert each attribute on the matched (or newly created) entity, but only when it
        # is not already one of that entity's current values for the predicate: a source
        # that agrees with what we already know adds nothing, and a source that disagrees
        # is recorded as a second observed value with its own evidence, never dropped.
        for f, v in attrs.items():
            current = {a.value for a in self.store.query(self.client, match, f'{entity_type}.{f}')}
            if v not in current:
                self.store.assert_(self.client, match, f'{entity_type}.{f}', v, at,
                                   evidence=evidence, recorded_at=recorded_at)
        for fields in self.keys.get(entity_type, []):
            if all(attrs.get(f) not in (None, '') for f in fields):
                self._by_key[(entity_type, fields, tuple(_norm(attrs[f]) for f in fields))] = match
        self._by_source[(source, source_id)] = match
        self.store.assert_(self.client, match, 'identity.source_id', f'{source}:{source_id}', at,
                           evidence=evidence, recorded_at=recorded_at)
        return match

    def lookup(self, source: str, source_id: str) -> str | None:
        return self._by_source.get((source, source_id))

    def review_queue(self) -> list[Candidate]:
        return list(self._queue)

    def merge(self, keep: str, drop: str, *, reason: str, evidence: str,
              recorded_at: datetime | None = None) -> None:
        self.store.assert_(self.client, drop, 'identity.same_as', keep, date.min,
                           evidence=f'{evidence}: {reason}', status='inferred', recorded_at=recorded_at)
        self._queue = [c for c in self._queue if {c.a, c.b} != {keep, drop}]

    def split(self, entity: str, *, reason: str, evidence: str,
              recorded_at: datetime | None = None) -> None:
        for a in self.store.query(self.client, entity, 'identity.same_as'):
            self.store.supersede(a.id, valid_to=date.min, evidence=f'{evidence}: {reason}',
                                 recorded_at=recorded_at, status='corrected')

    def canonical(self, entity: str, known_at: datetime | None = None) -> str:
        seen = {entity}
        while True:
            rows = [a for a in self.store.query(self.client, entity, 'identity.same_as', known_at=known_at)
                    if a.valid_to is None]
            if not rows or rows[-1].value in seen:
                return entity
            entity = rows[-1].value
            seen.add(entity)

    def dependents(self, entity: str) -> list[Assertion]:
        out = self.store.query(self.client, subject=entity)
        out += self.store.query(self.client, value=entity)
        return [a for a in out if not a.predicate.startswith('identity.')]
