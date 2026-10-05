# research/lbo/contracts_extra.py
"""Four more verbs: send a message, schedule a job, chase a payment, hold an order.

Each is a contract like the two in actions.py: preconditions read current state, the
delta writes assertions, the postcondition confirms the write, and the forbidden set
names what the action must never do whatever the authority says.
"""
from __future__ import annotations

from datetime import date

from .actions import ActionContract


def _send_message() -> ActionContract:
    def pre(store, client, p, at):
        return [] if p.get('to') else ['a message needs a recipient']

    def delta(store, client, p, at, now):
        subj = f'message:{p["_hash"]}'
        ids = [store.assert_(client, subj, f'message.{k}', p[k], at, evidence='message sent',
                             recorded_at=now)
               for k in ('audience', 'to', 'text')]
        ids.append(store.assert_(client, subj, 'message.sent_on', at.isoformat(), at,
                                 evidence='message sent', recorded_at=now))
        return ids

    def post(store, client, p, at):
        return [] if store.query(client, f'message:{p["_hash"]}', 'message.sent_on') \
            else ['message not recorded']

    def forbidden(store, client, p, at):
        return ['a message needs text'] if not p.get('text') else []

    return ActionContract('send_message', ('audience', 'to', 'text'), pre, delta, post, forbidden,
                          authority='send_message', reversible=False, risk='high',
                          recovery='a sent message cannot be unsent; send a correction')


def _schedule_job() -> ActionContract:
    def pre(store, client, p, at):
        day = date.fromisoformat(p['day'])
        emp = store.query(client, p['tech'], 'person.employed', as_of=day)
        return [] if emp and emp[0].value else [f'{p["tech"]} is not employed on {day}']

    def delta(store, client, p, at, now):
        day = date.fromisoformat(p['day'])
        return [store.assert_(client, f'schedule:{p["_hash"]}', 'schedule.hours',
                              {'tech': p['tech'], 'day': p['day'], 'hours': p['hours'], 'job': p['job']},
                              day, evidence='scheduled by the data team', recorded_at=now)]

    def post(store, client, p, at):
        return [] if store.query(client, f'schedule:{p["_hash"]}', 'schedule.hours') \
            else ['schedule entry not recorded']

    def forbidden(store, client, p, at):
        return ['hours must be positive'] if p['hours'] <= 0 else []

    return ActionContract('schedule_job', ('job', 'tech', 'day', 'hours'), pre, delta, post, forbidden,
                          authority='schedule_job', reversible=True, risk='low',
                          recovery='close the schedule entry')


def _chase_payment() -> ActionContract:
    def pre(store, client, p, at):
        inv = store.query(client, p['invoice'], 'invoice.amount')
        if not inv:
            return [f'{p["invoice"]} does not exist']
        paid = store.query(client, predicate='payment.settles', value=p['invoice'])
        return [f'{p["invoice"]} is already settled'] if paid else []

    def delta(store, client, p, at, now):
        return [store.assert_(client, p['invoice'], 'invoice.chased_on', at.isoformat(), at,
                              evidence=f'reminder sent by {p["channel"]}', recorded_at=now)]

    def post(store, client, p, at):
        return [] if store.query(client, p['invoice'], 'invoice.chased_on') else ['chase not recorded']

    def forbidden(store, client, p, at):
        return []

    return ActionContract('chase_payment', ('invoice', 'channel', 'days_overdue'), pre, delta, post,
                          forbidden, authority='chase_payment', reversible=False, risk='medium',
                          recovery='a reminder cannot be unsent; follow with an apology if wrong')


def _hold_order() -> ActionContract:
    def pre(store, client, p, at):
        st = store.query(client, p['sales_order'], 'sales_order.status', as_of=at)
        return [] if st and st[0].value == 'pending' else [f'{p["sales_order"]} is not pending']

    def delta(store, client, p, at, now):
        st = store.query(client, p['sales_order'], 'sales_order.status', as_of=at)[0]
        return [store.supersede(st.id, value='held', evidence=f'hold: {p["reason"]}', recorded_at=now)]

    def post(store, client, p, at):
        st = store.query(client, p['sales_order'], 'sales_order.status', as_of=at)
        return [] if st and st[0].value == 'held' else ['hold did not take']

    def forbidden(store, client, p, at):
        return []

    return ActionContract('hold_order', ('sales_order', 'customer', 'reason'), pre, delta, post,
                          forbidden, authority='hold_order', reversible=True, risk='medium',
                          recovery='release the hold with a new status assertion')


def extra_contracts() -> list[ActionContract]:
    return [_send_message(), _schedule_job(), _chase_payment(), _hold_order()]
