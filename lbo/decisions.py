# research/lbo/decisions.py
"""What was proposed, what was decided, and the distance between them.

Most systems keep the decision. The correction is the gap, and it is only a measurement
when the proposal is kept beside it with the conditions the owner gave. Every decision,
declined ones included, is a subject in the store with the same predicates, so the
history of one class of decision can be read back in one query.

The record is the contract; the lookup is the convenience. `decision.question` is written
as `<contract>: <rationale>` (or the bare contract when no rationale was given) so that a
declined proposal, which never reaches the execution journal and so never carries an
`action.contract` row, can still be found by the action it proposed.
"""
from __future__ import annotations

from datetime import datetime

from .actions import Proposal
from .store import Store


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def gap(proposed: dict, decided: dict | None) -> dict:
    """Owner minus agent, per numeric field present in both; a declined decision is
    `{'declined': True}`; fields that differ non-numerically, or that the owner added,
    are listed under `'changed'`."""
    if decided is None:
        return {'declined': True}
    out: dict = {}
    changed: list[str] = []
    for k, v in proposed.items():
        if k not in decided:
            continue
        a, b = v, decided[k]
        if _is_number(a) and _is_number(b):
            out[k] = round(float(b) - float(a), 4)
        elif a != b:
            changed.append(k)
    changed += [k for k in decided if k not in proposed]
    if changed:
        out['changed'] = sorted(changed)
    return out


def question_for(contract: str, rationale: str = '') -> str:
    """The `decision.question` text: the contract first, then the rationale."""
    return f'{contract}: {rationale}' if rationale else contract


def _asks_about(question: str | None, action: str) -> bool:
    return isinstance(question, str) and (question == action or question.startswith(f'{action}:'))


def record_decision(store: Store, client: str, proposal: Proposal, kind: str, decided: dict | None,
                    note: str, now: datetime, *, rationale: str = '') -> str:
    """Write the decision as a subject beside the action it answers; return the subject."""
    subj = f'decision:{proposal.hash()}'
    ev = f'owner reply to proposal {proposal.hash()}'
    at = now.date()
    for pred, val in (('decision.question', question_for(proposal.contract, rationale)),
                      ('decision.proposed', dict(proposal.payload)),
                      ('decision.decided', dict(decided) if decided is not None else None),
                      ('decision.kind', kind),
                      ('decision.gap', gap(proposal.payload, decided)),
                      ('decision.conditions', note),
                      ('decision.taken_at', now.isoformat(timespec='minutes'))):
        store.assert_(client, subj, pred, val, at, evidence=ev, recorded_at=now)
    store.assert_(client, f'action:{proposal.hash()}', 'action.of_decision', subj, at, evidence=ev,
                  recorded_at=now)
    return subj


def decisions_for(store: Store, client: str, action: str, known_at: datetime | None = None) -> list[dict]:
    """Every decision taken on `action`, oldest first, as known at `known_at`. Matches the
    execution journal's `action.contract` where one exists, and otherwise the contract
    written first into `decision.question`."""
    out = []
    for link in store.query(client, predicate='action.of_decision', known_at=known_at):
        subj = link.value
        rows = {a.predicate: a.value for a in store.query(client, subj, known_at=known_at)}
        if not rows or rows.get('decision.proposed') is None:
            continue
        contract = store.query(client, link.subject, 'action.contract', known_at=known_at)
        journaled = contract[0].value == action if contract else False
        if not journaled and not _asks_about(rows.get('decision.question'), action):
            continue
        out.append({'proposed': rows['decision.proposed'], 'decided': rows.get('decision.decided'),
                    'kind': rows.get('decision.kind'), 'gap': rows.get('decision.gap'),
                    'conditions': rows.get('decision.conditions'), 'taken_at': rows.get('decision.taken_at')})
    return sorted(out, key=lambda d: d['taken_at'] or '')
