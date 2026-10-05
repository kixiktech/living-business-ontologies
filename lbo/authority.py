# research/lbo/authority.py
"""Authority is a constraint, not a suggestion.

Policies are approved by responsible people and enforced here, outside whatever reasons
about them. The agent's write tools call `Monitor.check` and cannot proceed without it;
a persuasive proposal changes nothing. This is access control and is built as such.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from .store import Store


@dataclass(frozen=True)
class Grant:
    principal: str
    action: str
    scope: dict
    limits: dict
    valid_from: date
    valid_to: date | None = None

    def live(self, at: date) -> bool:
        return self.valid_from <= at and (self.valid_to is None or at <= self.valid_to)


@dataclass(frozen=True)
class Rule:
    action: str
    describe: str
    needs_approval: Callable[[dict], str | None]


@dataclass(frozen=True)
class Decision:
    allowed: bool
    requires_approval: bool
    reason: str
    grant: Grant | None = None


class Monitor:
    def __init__(self, grants: list[Grant], rules: list[Rule]):
        self.grants, self.rules = list(grants), list(rules)

    @classmethod
    def from_store(cls, store: Store, client: str, rules: list[Rule], at: date) -> 'Monitor':
        subjects = {a.subject for a in store.query(client, predicate='grant.principal', as_of=at)}
        grants = []
        for g in subjects:
            def one(pred, default=None):
                rows = store.query(client, g, pred, as_of=at)
                return rows[0].value if rows else default
            row = store.query(client, g, 'grant.principal', as_of=at)[0]
            grants.append(Grant(one('grant.principal'), one('grant.action'), one('grant.scope', {}) or {},
                                one('grant.limits', {}) or {}, row.valid_from, row.valid_to))
        return cls(grants, rules)

    def has_grant(self, principal: str, action: str, at: date | None = None) -> bool:
        """Is this verb delegated to this principal at all on that date?

        A different question from `check`, and conflating the two is a mistake worth
        naming. `check` asks whether one specific payload may go through, so it reads
        scope, limits and the approval rules; asked with an empty payload it answers no
        for reasons that have nothing to do with authority, because an empty payload sits
        outside every scope and trips every rule that needs a value. What a competency
        question wants to know is whether the firm has delegated the verb, which is this.
        Scope, limits and rules are deliberately ignored here.
        """
        at = at or date.today()
        return any(g.principal == principal and g.action == action and g.live(at)
                   for g in self.grants)

    def check(self, principal: str, action: str, payload: dict, at: date | None = None) -> Decision:
        at = at or date.today()
        matching = [g for g in self.grants if g.principal == principal and g.action == action and g.live(at)]
        if not matching:
            return Decision(False, False, f'no grant lets {principal} {action} on {at}')
        reasons = []
        for g in matching:
            bad = [k for k, v in g.scope.items() if payload.get(k) != v]
            if bad:
                reasons.append(f'scope: {", ".join(f"{k} must be {g.scope[k]}" for k in bad)}')
                continue
            missing = [k[4:] for k in g.limits if k.startswith('max_') and payload.get(k[4:]) is None]
            if missing:
                reasons.append(f'limits: {", ".join(missing)} missing')
                continue
            over = [k for k, v in g.limits.items() if k.startswith('max_') and payload[k[4:]] > v]
            if over:
                reasons.append(f'limits: {", ".join(f"{k}={g.limits[k]}" for k in over)}')
                continue
            approval = [r.needs_approval(payload) for r in self.rules if r.action == action]
            approval = [x for x in approval if x]
            return Decision(True, bool(approval), '; '.join(approval), g)
        return Decision(False, False, '; '.join(reasons))


def price_change_rule(limit_pct: float = 5.0) -> Rule:
    def needs(payload: dict) -> str | None:
        old, new = payload.get('old'), payload.get('new')
        if old in (None, 0) or new is None:
            return 'a price change needs old and new'
        pct = abs(new / old - 1) * 100
        if pct > limit_pct + 1e-9:
            return f'increase of {pct:.2f}% exceeds the {limit_pct:.2f}% limit without explicit approval'
        return None
    return Rule('change_price', f'any single price change above {limit_pct:.2f}% needs explicit approval', needs)
