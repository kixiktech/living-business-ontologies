# research/lbo/actions.py
"""Verbs are part of the model. An action is a typed business transition with a contract:

    a = (I, Pre, Delta, Post, F, Gamma, rho)

The model distinguishes an action type, a proposed action, an approved request and an
execution attempt. Approval binds to a specific payload and the versions it was computed
under: editing the payload after approval invalidates the approval. Before execution the
preconditions are refreshed against current state, because an approval is evidence of an
approval and not of the business state intended.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable

from .store import Store

STATUSES = ('executed', 'refused', 'blocked', 'failed')


@dataclass(frozen=True)
class ActionContract:
    name: str
    inputs: tuple[str, ...]
    pre: Callable[[Store, str, dict, date], list[str]]
    delta: Callable[[Store, str, dict, date, datetime], list[int]]
    post: Callable[[Store, str, dict, date], list[str]]
    forbidden: Callable[[Store, str, dict, date], list[str]]
    authority: str
    reversible: bool
    risk: str
    recovery: str


@dataclass(frozen=True)
class Proposal:
    contract: str
    payload: dict
    computed_under: dict
    created_at: datetime

    def hash(self) -> str:
        canon = json.dumps({'c': self.contract, 'p': self.payload, 'u': self.computed_under},
                           sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canon.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class Approval:
    proposal_hash: str
    principal: str
    at: datetime


@dataclass(frozen=True)
class Execution:
    status: str
    reason: str
    assertion_ids: tuple[int, ...]
    proposal_hash: str


class Registry:
    def __init__(self):
        self._c: dict[str, ActionContract] = {}

    def register(self, c: ActionContract) -> None:
        self._c[c.name] = c

    def get(self, name: str) -> ActionContract:
        return self._c[name]

    def all(self) -> list[ActionContract]:
        """Every registered contract, in registration order: what a caller may name."""
        return list(self._c.values())


def propose(contract: ActionContract, payload: dict, computed_under: dict,
            created_at: datetime | None = None) -> Proposal:
    missing = [k for k in contract.inputs if k not in payload]
    if missing:
        raise ValueError(f'{contract.name}: payload missing {missing}')
    return Proposal(contract.name, dict(payload), dict(computed_under), created_at or datetime.now())


def _journal(store: Store, client: str, p: Proposal, principal: str, status: str, reason: str,
             at: date, now: datetime, run_id: str) -> None:
    subj = f'action:{p.hash()}'
    ev = f'execution journal{(" run " + run_id) if run_id else ""}'
    for pred, val in (('action.contract', p.contract), ('action.payload', p.payload),
                      ('action.principal', principal), ('action.status', status),
                      ('action.reason', reason)):
        store.assert_(client, subj, pred, val, at, evidence=ev, recorded_at=now)


def execute(p: Proposal, *, registry: Registry, store: Store, client: str, monitor, principal: str,
            at: date, now: datetime, approval: Approval | None = None, run_id: str = '') -> Execution:
    c = registry.get(p.contract)

    def done(status: str, reason: str, ids: tuple[int, ...] = ()) -> Execution:
        _journal(store, client, p, principal, status, reason, at, now, run_id)
        return Execution(status, reason, ids, p.hash())

    d = monitor.check(principal, c.authority, p.payload, at=at)
    if not d.allowed:
        return done('refused', d.reason)
    if d.requires_approval:
        if approval is None:
            return done('blocked', f'{d.reason}; no approval')
        if approval.proposal_hash != p.hash():
            return done('blocked', f'{d.reason}; approval {approval.proposal_hash} is for a different payload')
    payload = dict(p.payload, _hash=p.hash())
    f = c.forbidden(store, client, payload, at)
    if f:
        return done('refused', 'forbidden effect: ' + '; '.join(f))
    pre = c.pre(store, client, payload, at)
    if pre:
        return done('failed', 'precondition no longer holds: ' + '; '.join(pre))
    ids = tuple(c.delta(store, client, payload, at, now))
    post = c.post(store, client, payload, at)
    if post:
        return done('failed', 'postcondition failed after execution; reconcile before retrying: '
                    + '; '.join(post), ids)
    return done('executed', d.reason or 'within grant', ids)


# ---- two contracts the paper uses ----------------------------------------------------

def change_price_contract() -> ActionContract:
    def pre(store, client, p, at):
        cur = store.query(client, p['product'], 'product.list_price', as_of=at)
        if not cur:
            return [f'{p["product"]} has no list price on {at}']
        if abs(cur[0].value - p['old']) > 1e-9:
            return [f'{p["product"]} list price is {cur[0].value}, proposal assumed {p["old"]}']
        return []

    def delta(store, client, p, at, now):
        cur = store.query(client, p['product'], 'product.list_price', as_of=at)[0]
        closed = store.supersede(cur.id, valid_to=at, evidence='price change executed', recorded_at=now)
        opened = store.assert_(client, p['product'], 'product.list_price', p['new'], at,
                               evidence='price change executed', recorded_at=now)
        return [closed, opened]

    def post(store, client, p, at):
        cur = store.query(client, p['product'], 'product.list_price', as_of=at)
        return [] if cur and cur[0].value == p['new'] else ['price did not take']

    def forbidden(store, client, p, at):
        return ['price must be positive'] if p['new'] <= 0 else []

    return ActionContract('change_price', ('product', 'old', 'new'), pre, delta, post, forbidden,
                          authority='change_price', reversible=True, risk='medium',
                          recovery='restore the previous list price with a new assertion')


def place_order_contract() -> ActionContract:
    def pre(store, client, p, at):
        sup = store.query(client, p['product'], 'product.supplied_by', as_of=at)
        if not sup or sup[0].value != p['supplier']:
            return [f'{p["product"]} is not supplied by {p["supplier"]} on {at}']
        return []

    def delta(store, client, p, at, now):
        subj = f'purchase_order:{p["_hash"]}'
        ids = []
        for k in ('supplier', 'product', 'qty', 'amount'):
            ids.append(store.assert_(client, subj, f'purchase_order.{k}', p[k], at,
                                     evidence='purchase order placed', recorded_at=now))
        ids.append(store.assert_(client, subj, 'purchase_order.status', 'placed', at,
                                 evidence='purchase order placed', recorded_at=now))
        return ids

    def post(store, client, p, at):
        rows = store.query(client, f'purchase_order:{p["_hash"]}', 'purchase_order.status')
        return [] if rows and rows[0].value == 'placed' else ['order not recorded']

    def forbidden(store, client, p, at):
        return ['quantity must be positive'] if p['qty'] <= 0 else []

    return ActionContract('place_order', ('supplier', 'product', 'qty', 'amount'), pre, delta, post,
                          forbidden, authority='place_order', reversible=False, risk='medium',
                          recovery='compensate by cancelling with the supplier; the order cannot be un-sent')
