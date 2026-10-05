# research/lbo/firms/fieldservice.py
"""A field-service contractor: six technicians, two crews, two lead channels.

Planted structure (answer key):
  * channel B looks twice as good per lead as channel A and cannot grow, because every
    channel-B job needs a certification one technician holds and he is 94% committed
    (the paper's "recommendation that inverts");
  * a technician who left in February still holds a certification on the spreadsheet
    (a relation the world falsified with no event in any system);
  * two jobs scheduled for one crew and performed by another.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from ..definitions import MetricDefinition, Registry, matches
from ..schema import EntityType, RelationType, Schema
from . import common as cm

SLUG = 'fieldservice'
FOCAL_Q = '2026Q2'
TECHS = [('T1', 'Owen Marsh', 'C1'), ('T2', 'Pia Lund', 'C1'), ('T3', 'Rafa Osei', 'C2'),
         ('T4', 'Sam Iyer', 'C2'), ('T5', 'Tomas Bell', 'C1'), ('T6', 'Uma Sato', 'C2')]
LINES = ['hvac-service', 'plumbing', 'backflow', 'electrical', 'install']
HOURS_PER_DAY = 8.0
TARGET_UTILISATION = 0.94
DIVERGENT_JOBS = (4, 9)      # channel-A job indices scheduled for C1 and performed by C2

POLICY = """# Operating policy: field service

## Customer contact
- No message to a customer goes out without the owner's approval. Internal notes and
  drafts may be prepared by the data team.

## Scheduling
- Any single job over 8 hours needs the owner's approval before it is scheduled.
- A technician may only be scheduled to a job in a service line he is certified for.

## Certifications
- Every certification is verified against the issuing body every 12 months.
"""


def build(seed: int = 11) -> cm.Firm:
    r = random.Random(seed)
    qs = cm.quarters()
    focal = next(x for x in qs if x[0] == FOCAL_Q)
    weekdays = [cm.START + timedelta(days=i) for i in range((cm.END - cm.START).days)]
    weekdays = [d for d in weekdays if d.weekday() < 5]

    technicians = [{'tech_id': t, 'name': n, 'crew': c, 'hourly_cost': 38.0,
                    'hired_on': '2023-05-01', 'left_on': '2026-02-28' if t == 'T5' else None}
                   for t, n, c in TECHS]
    certs = [{'tech': 'T3', 'certification': 'backflow-tester', 'issued_on': '2024-03-11'},
             {'tech': 'T5', 'certification': 'backflow-tester', 'issued_on': '2023-09-02'},
             {'tech': 'T1', 'certification': 'epa-608', 'issued_on': '2022-01-15'},
             {'tech': 'T2', 'certification': 'epa-608', 'issued_on': '2022-06-20'},
             {'tech': 'T4', 'certification': 'journeyman-electrician', 'issued_on': '2021-11-30'}]

    leads: list[dict] = []
    jobs: list[dict] = []
    schedule: list[dict] = []
    ledger: list[dict] = []
    lid = jid = sid = 0

    def add_job(day: date, channel: str, line: str, tech: str, revenue: float, cost: float, hours: float,
                sched_crew: str, perf_crew: str, lead_id: str):
        nonlocal jid, sid
        jid += 1
        sid += 1
        jobs.append({'job_id': f'J{jid:05d}', 'lead_id': lead_id, 'channel': channel, 'service_line': line,
                     'tech': tech, 'scheduled_crew': sched_crew, 'performed_crew': perf_crew,
                     'scheduled_on': day.isoformat(), 'performed_on': day.isoformat(),
                     'entered_on': day.isoformat(),
                     'revenue': cm.money(revenue), 'direct_cost': cm.money(cost), 'hours': hours})
        schedule.append({'entry_id': f'S{sid:05d}', 'tech': tech, 'day': day.isoformat(), 'hours': hours,
                         'entered_on': day.isoformat(), 'job_id': f'J{jid:05d}'})

    def add_lead(day: date, channel: str, status: str) -> str:
        nonlocal lid
        lid += 1
        leads.append({'lead_id': f'LD{lid:05d}', 'created_on': day.isoformat(), 'entered_on': day.isoformat(),
                      'channel': channel, 'status': status})
        return f'LD{lid:05d}'

    def spend_row(q: str, day: date, channel: str, amount: float):
        ledger.append({'journal_id': f'J-{q}-{channel}', 'kind': 'channel_spend', 'channel': channel,
                       'amount': amount, 'effective_on': day.isoformat(),
                       'entered_on': (day + timedelta(days=3)).isoformat(), 'memo': f'Channel {channel} ads'})

    # every quarter gets background work; the focal quarter is planted exactly
    for q, qs_, qe in qs:
        days = [d for d in weekdays if qs_ <= d < qe]
        if q == FOCAL_Q:
            a_days = [days[i * len(days) // 20] for i in range(20)]
            b_days = [days[i * len(days) // 18] for i in range(18)]
            # channel A: 100 leads, 20 jobs, 8,000 margin
            for i in range(100):
                d = days[i * len(days) // 100]
                won = i % 5 == 0
                lead_id = add_lead(d, 'A', 'won' if won else 'lost')
                if won:
                    j = i // 5
                    line = LINES[j % 2]                      # hvac or plumbing
                    tech = ['T1', 'T2', 'T4', 'T6'][j % 4]
                    crew = 'C1' if tech in ('T1', 'T2') else 'C2'
                    perf = 'C2' if j in DIVERGENT_JOBS and crew == 'C1' else crew   # two divergences
                    add_job(a_days[j], 'A', line, tech, 1000.0, 600.0, 4.0, crew, perf, lead_id)
            # channel B: 40 leads, 18 jobs, 10,800 margin, all backflow, all T3
            for i in range(40):
                d = days[i * len(days) // 40]
                won = i < 18
                lead_id = add_lead(d, 'B', 'won' if won else 'lost')
                if won:
                    add_job(b_days[i], 'B', 'backflow', 'T3', 1500.0, 900.0, 6.0, 'C2', 'C2', lead_id)
            # T3's utilisation: fill to exactly 94.00% of available hours with other backflow
            # work, up to 8 hours on any one day, because a day cannot hold more than a day.
            avail = HOURS_PER_DAY * len(days)
            target = round(avail * TARGET_UTILISATION, 2)
            used = {d: 0.0 for d in days}
            for d in b_days:
                used[d] += 6.0
            booked = round(sum(used.values()), 2)
            for d in days:
                if booked >= target - 1e-9:
                    break
                h = round(min(HOURS_PER_DAY - used[d], target - booked), 2)
                if h <= 0:
                    continue
                lead_id = add_lead(d, 'referral', 'won')
                add_job(d, 'referral', 'backflow', 'T3', 250.0 * h, 150.0 * h, h, 'C2', 'C2', lead_id)
                used[d] += h
                booked = round(booked + h, 2)
            spend_row(q, qs_, 'A', 1000.0)
            spend_row(q, qs_, 'B', 800.0)
        else:
            for i in range(r.randint(60, 90)):
                d = days[i * len(days) // 90 % len(days)]
                ch = 'A' if i % 3 else 'B'
                won = r.random() < (0.2 if ch == 'A' else 0.4)
                lead_id = add_lead(d, ch, 'won' if won else 'lost')
                if won:
                    line = 'backflow' if ch == 'B' else LINES[r.randint(0, 4)]
                    tech = ('T3' if line == 'backflow' and d > date(2026, 2, 28)
                            else ('T5' if line == 'backflow' and r.random() < 0.4
                                  else ['T1', 'T2', 'T4', 'T6', 'T3'][r.randint(0, 4)]))
                    if tech == 'T5' and d > date(2026, 2, 28):
                        tech = 'T3'
                    crew = next(c for t, _, c in TECHS if t == tech)
                    add_job(d, ch, line, tech, r.uniform(700, 1800), r.uniform(400, 1000),
                            r.choice([4.0, 6.0, 8.0]), crew, crew, lead_id)
            spend_row(q, qs_, 'A', 1000.0)
            spend_row(q, qs_, 'B', 800.0)

    payroll = [{'tech': t, 'week_start': ws.isoformat(), 'hours': 40.0}
               for ws, we in cm.weeks(cm.START, cm.END, week_starts=6) for t, _, _ in TECHS
               if not (t == 'T5' and ws > date(2026, 2, 28))]

    focal_days = [d for d in weekdays if focal[1] <= d < focal[2]]
    avail = HOURS_PER_DAY * len(focal_days)
    t3_hours = sum(s['hours'] for s in schedule
                   if s['tech'] == 'T3' and focal[1] <= date.fromisoformat(s['day']) < focal[2])
    util = cm.pct(t3_hours, avail)
    remaining = avail - t3_hours

    def channel_key(ch: str) -> dict:
        n_leads = sum(1 for x in leads if x['channel'] == ch
                      and focal[1] <= date.fromisoformat(x['created_on']) < focal[2])
        focal_jobs = [x for x in jobs if x['channel'] == ch
                      and focal[1] <= date.fromisoformat(x['performed_on']) < focal[2]]
        margin = cm.money(sum(x['revenue'] - x['direct_cost'] for x in focal_jobs))
        spend = cm.money(sum(x['amount'] for x in ledger if x['kind'] == 'channel_spend'
                             and x['channel'] == ch
                             and focal[1] <= date.fromisoformat(x['effective_on']) < focal[2]))
        return {'leads': n_leads, 'jobs': len(focal_jobs), 'job_margin': margin, 'spend': spend,
                'net_contribution': cm.money(margin - spend),
                'net_per_lead': cm.money((margin - spend) / n_leads) if n_leads else 0.0,
                'job_margin_per_job': cm.money(margin / len(focal_jobs)) if focal_jobs else 0.0}

    key = {
        'focal_quarter': FOCAL_Q,
        'channels': {'A': channel_key('A'), 'B': channel_key('B')},
        'constraint_tech': 'T3', 'constraint_certification': 'backflow-tester',
        'constraint_service_line': 'backflow',
        'utilisation_pct': util, 'remaining_hours': round(remaining, 2),
        'remaining_jobs_capacity': int(remaining // 6.0), 'marginal_job_margin': 600.0,
        'projected_naive_return_on_800': 10000.0,
        'realistic_return_on_800': cm.money(600.0 * min(1, int(remaining // 6.0)) - 800.0),
        'stale_certification_tech': 'T5', 'stale_certification_left_on': '2026-02-28',
        'scheduled_vs_performed_divergences': [j['job_id'] for j in jobs
                                               if j['scheduled_crew'] != j['performed_crew']],
        'available_hours': avail, 't3_scheduled_hours': round(t3_hours, 2),
    }
    grants = [{'principal': 'agent', 'action': 'send_message', 'scope': {'audience': 'internal'},
               'limits': {}, 'valid_from': '2026-01-01'},
              {'principal': 'agent', 'action': 'schedule_job', 'scope': {},
               'limits': {'max_hours': 8.0}, 'valid_from': '2026-01-01'}]
    return cm.Firm(SLUG, 'Ridgeline Mechanical', 'field service', seed, {
        'crm_leads': cm.Source('crm_leads', cm.NOW, leads, 'lead_id', 'leads from the CRM with channel and outcome'),
        'jobs': cm.Source('jobs', cm.NOW, jobs, 'job_id',
                          'jobs from the field-service system: scheduled crew, performed crew, revenue, direct cost'),
        'schedule': cm.Source('schedule', cm.NOW, schedule, 'entry_id', 'technician hours by day'),
        'technicians': cm.Source('technicians', cm.NOW, technicians, 'tech_id',
                                 'the technician roster with hire and leave dates'),
        'certifications': cm.Source('certifications', datetime(2026, 1, 15, 9, 0), certs, 'tech',
                                    'a spreadsheet of certifications; it has no end-date column'),
        'ledger': cm.Source('ledger', cm.NOW, ledger, 'journal_id', 'channel spend by quarter'),
        'payroll': cm.Source('payroll', cm.NOW, payroll, 'tech', 'weekly paid hours'),
    }, POLICY, grants, key, notes=['T5 left 2026-02-28 and is still on the certifications sheet'])


def extension(core: Schema) -> Schema:
    E, R = EntityType, RelationType
    return core.extend('fieldservice', [
        E('lead', 'extension', ('created_on', 'channel', 'status'), ('channel_questions',)),
        E('job', 'extension', ('scheduled_on', 'performed_on', 'revenue', 'direct_cost', 'hours', 'service_line'),
          ('channel_questions', 'capacity')),
        E('crew', 'extension', ('name',), ('capacity',)),
        E('certification', 'extension', ('name',), ('capacity',)),
        E('channel', 'extension', ('name', 'spend_on'), ('channel_questions',)),
        E('service_line', 'extension', ('name',), ('capacity',)),
    ], [
        R('job.from_lead', 'job', 'lead', 'extension', ('channel_questions',)),
        R('job.scheduled_for', 'job', 'crew', 'extension', ('divergence',)),
        R('job.performed_by', 'job', 'crew', 'extension', ('divergence', 'capacity')),
        R('job.in_service_line', 'job', 'service_line', 'extension', ('capacity',)),
        R('job.assigned_tech', 'job', 'person', 'extension', ('capacity',)),
        R('lead.via_channel', 'lead', 'channel', 'extension', ('channel_questions',)),
        R('person.in_crew', 'person', 'crew', 'extension', ('capacity',)),
        R('person.holds', 'person', 'certification', 'extension', ('capacity',)),
        R('service_line.requires', 'service_line', 'certification', 'extension', ('capacity',)),
    ])


def _jobs_in(store, client, window, known_at, filters=None):
    for a in store.query(client, predicate='job.performed_on', known_at=known_at):
        d = date.fromisoformat(a.value)
        if window[0] <= d < window[1] and matches(store, client, a.subject, filters, known_at):
            yield a.subject, d


def _job_margin(store, client, window, known_at, filters=None):
    total, inputs = 0.0, []
    for j, d in _jobs_in(store, client, window, known_at, filters):
        rev = store.query(client, j, 'job.revenue', known_at=known_at)
        cost = store.query(client, j, 'job.direct_cost', known_at=known_at)
        if rev and cost:
            total += rev[0].value - cost[0].value
            inputs += [rev[0].id, cost[0].id]
    return cm.money(total), tuple(inputs), ()


def _channel_spend(store, client, window, known_at, filters=None):
    out, inputs = {}, []
    for a in store.query(client, predicate='channel.spend_on', known_at=known_at):
        d = date.fromisoformat(a.value['effective_on'])
        if window[0] <= d < window[1]:
            out[a.subject] = cm.money(out.get(a.subject, 0.0) + a.value['amount'])
            inputs.append(a.id)
    return out, tuple(inputs), ()


def _net_contribution(store, client, window, known_at, filters=None):
    margin, inputs = {}, []
    for j, d in _jobs_in(store, client, window, known_at, filters):
        lead = store.query(client, j, 'job.from_lead', known_at=known_at)
        ch = store.query(client, lead[0].value, 'lead.via_channel', known_at=known_at) if lead else []
        rev = store.query(client, j, 'job.revenue', known_at=known_at)
        cost = store.query(client, j, 'job.direct_cost', known_at=known_at)
        if ch and rev and cost:
            margin[ch[0].value] = margin.get(ch[0].value, 0.0) + rev[0].value - cost[0].value
            inputs += [lead[0].id, ch[0].id, rev[0].id, cost[0].id]
    spend, sp_inputs, _ = _channel_spend(store, client, window, known_at, filters)
    out = {c: cm.money(margin.get(c, 0.0) - spend.get(c, 0.0)) for c in set(margin) | set(spend)}
    return out, tuple(inputs) + sp_inputs, ()


def _tech_utilisation_pct(store, client, window, known_at, filters=None):
    days = sum(1 for i in range((window[1] - window[0]).days) if (window[0] + timedelta(days=i)).weekday() < 5)
    avail = HOURS_PER_DAY * days
    hours, inputs = {}, []
    for a in store.query(client, predicate='schedule.hours', known_at=known_at):
        d = date.fromisoformat(a.value['day'])
        if window[0] <= d < window[1]:
            hours[a.value['tech']] = hours.get(a.value['tech'], 0.0) + a.value['hours']
            inputs.append(a.id)
    return ({t: cm.pct(h, avail) for t, h in hours.items()}, tuple(inputs),
            (f'available hours per technician: {avail}',))


def definitions(reg: Registry) -> Registry:
    reg.register(MetricDefinition('job_margin', 'v1', 'job', 'usd',
                                  'revenue less directly assigned job cost, before channel spend',
                                  ('jobs performed in the window',), date(2000, 1, 1), _job_margin))
    reg.register(MetricDefinition('channel_spend', 'v1', 'channel', 'usd',
                                  'ledger spend by channel, effective in the window',
                                  ('channel_spend ledger rows',), date(2000, 1, 1), _channel_spend))
    reg.register(MetricDefinition('net_contribution', 'v1', 'channel', 'usd',
                                  'job margin less channel spend, by channel',
                                  ('jobs traced to a lead with a channel',), date(2000, 1, 1), _net_contribution))
    reg.register(MetricDefinition('tech_utilisation_pct', 'v1', 'technician', 'percent',
                                  'scheduled hours as a percentage of 8 hours per weekday in the window',
                                  ('schedule entries in the window',), date(2000, 1, 1), _tech_utilisation_pct))
    return reg
